"""
Socket.IO handler for real-time chat functionality.
"""
import logging
from typing import Optional
import socketio
import uuid
from datetime import datetime, timedelta
import asyncio

from .database import get_db
from .models import Conversation, Message, User
from .config import settings
from .ai_service import generate_ai_response

logger = logging.getLogger(__name__)

# Socket.IO server instance
sio = socketio.AsyncServer(
    cors_allowed_origins=settings.allowed_origins,  # CORS ayarları config'den alınıyor
    async_mode='asgi'
)

# Misafir kullanıcılar için geçici conversation'lar (memory'de tutuluyor)
# Format: {guest_id: {conversation_id: str, messages: list, last_activity: datetime}}
guest_conversations: dict[str, dict] = {}

# Misafir verilerinin otomatik temizlenme süresi (30 dakika)
GUEST_DATA_TIMEOUT_MINUTES = 30


async def get_user_from_token(token: Optional[str]) -> Optional[User]:
    """Token'dan kullanıcıyı alır."""
    if not token:
        return None
    
    try:
        from jose import JWTError, jwt
        from .config import settings
        
        # Token'ı decode et (HTTPException fırlatmadan)
        try:
            payload = jwt.decode(
                token, 
                settings.jwt_secret, 
                algorithms=[settings.jwt_algorithm]
            )
        except JWTError as e:
            logger.error(f"JWT decode error: {e}")
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        # Database session oluştur
        db = next(get_db())
        try:
            user = db.get(User, int(user_id))
            return user
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        return None


@sio.event
async def connect(sid, environ, auth):
    """Client bağlandığında çağrılır."""
    token = auth.get('token') if auth else None
    user = await get_user_from_token(token)
    
    if user:
        # Kayıtlı kullanıcı
        logger.info(f"User {user.username} connected with socket {sid}")
        await sio.save_session(sid, {
            'user_id': user.id,
            'username': user.username,
            'is_guest': False
        })
    else:
        # Misafir kullanıcı
        guest_id = str(uuid.uuid4())
        logger.info(f"Guest user connected with socket {sid}, guest_id: {guest_id}")
        await sio.save_session(sid, {
            'guest_id': guest_id,
            'username': f'Misafir-{guest_id[:8]}',
            'is_guest': True
        })
        # Misafir için boş conversation oluştur
        guest_conversations[guest_id] = {
            'conversation_id': f'guest_{guest_id}',
            'messages': [],
            'last_activity': datetime.now()
        }
    
    return True


@sio.event
async def disconnect(sid):
    """Client bağlantısı kesildiğinde çağrılır."""
    try:
        session = await sio.get_session(sid)
        username = session.get('username', 'Unknown')
        is_guest = session.get('is_guest', False)
        
        if is_guest:
            guest_id = session.get('guest_id')
            if guest_id:
                # Misafir conversation'ını ve tüm verilerini kalıcı olarak sil
                if guest_id in guest_conversations:
                    del guest_conversations[guest_id]
                    logger.info(f"Guest {username} (ID: {guest_id}) disconnected - All data permanently deleted")
                else:
                    logger.info(f"Guest {username} (ID: {guest_id}) disconnected - No data found to delete")
            else:
                logger.info(f"Guest {username} disconnected (socket {sid})")
        else:
            logger.info(f"User {username} disconnected (socket {sid})")
    except Exception as e:
        logger.error(f"Error in disconnect handler: {e}")


@sio.event
async def user_message(sid, data):
    """Kullanıcı mesajı geldiğinde çağrılır."""
    session = await sio.get_session(sid)
    is_guest = session.get('is_guest', False)
    
    conversation_id = data.get('conversation_id')
    message_text = data.get('message', '')
    image_url = data.get('image_url')
    
    if is_guest:
        # Misafir kullanıcı için işlem
        guest_id = session.get('guest_id')
        if not guest_id or guest_id not in guest_conversations:
            await sio.emit('error', {'message': 'Guest session not found'}, room=sid)
            return
        
        guest_conv = guest_conversations[guest_id]
        guest_conv_id = guest_conv['conversation_id']
        
        # Son aktivite zamanını güncelle
        guest_conv['last_activity'] = datetime.now()
        
        # Eğer frontend'den conversation_id gelmemişse veya null ise, guest_conv_id kullan
        if not conversation_id:
            conversation_id = guest_conv_id
        
        # Kullanıcı mesajını memory'ye ekle
        user_msg = {
            'id': f'guest_msg_{len(guest_conv["messages"]) + 1}',
            'sender': 'user',
            'content': message_text,
            'image_url': image_url,
            'created_at': datetime.now().isoformat()
        }
        guest_conv['messages'].append(user_msg)
        
        # AI yanıtını üret
        try:
            # Görsel üretimi: Sadece kullanıcı görsel istediğinde veya kıyafet fikri sorduğunda
            # generate_ai_response fonksiyonu mesajı analiz edip otomatik karar verecek
            generate_images = False  # Varsayılan olarak False, fonksiyon içinde analiz edilecek
            ai_response = await generate_ai_response(message_text, generate_images=generate_images)
            ai_response_text = ai_response['content']
            ai_image_urls = ai_response.get('image_urls', [])
        except Exception as e:
            logger.error(f"AI yanıt üretme hatası: {e}", exc_info=True)
            ai_response_text = f"Mesajınızı aldım: {message_text}"
            if image_url:
                ai_response_text += f"\nGörsel URL: {image_url}"
            ai_image_urls = []
        
        # AI mesajını memory'ye ekle
        ai_msg = {
            'id': f'guest_msg_{len(guest_conv["messages"]) + 1}',
            'sender': 'ai',
            'content': ai_response_text,
            'image_urls': ai_image_urls,
            'created_at': datetime.now().isoformat()
        }
        guest_conv['messages'].append(ai_msg)
        
        # Kullanıcıya AI yanıtını gönder (tüm görselleri gönder)
        await sio.emit('ai_message', {
            'id': ai_msg['id'],
            'conversation_id': guest_conv_id,
            'content': ai_msg['content'],
            'image_url': ai_image_urls[0] if ai_image_urls else None,  # Backward compatibility için
            'image_urls': ai_image_urls,  # Tüm görselleri gönder
            'created_at': ai_msg['created_at']
        }, room=sid)
        
        logger.info(f"Guest message processed: {guest_id}")
        return
    
    # Kayıtlı kullanıcı için işlem
    user_id = session.get('user_id')
    if not user_id:
        await sio.emit('error', {'message': 'Unauthorized'}, room=sid)
        return
    
    if not conversation_id:
        await sio.emit('error', {'message': 'conversation_id is required'}, room=sid)
        return
    
    # Database session oluştur
    db = next(get_db())
    try:
        # Konuşmanın kullanıcıya ait olduğunu kontrol et
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id
            )
            .first()
        )
        
        if not conversation:
            await sio.emit('error', {'message': 'Conversation not found'}, room=sid)
            return
        
        # Kullanıcı mesajını kaydet
        user_message = Message(
            conversation_id=conversation_id,
            sender='user',
            content=message_text,
            image_url=image_url
        )
        db.add(user_message)
        db.commit()
        db.refresh(user_message)
        
        logger.info(f"User message saved: {user_message.id}")
        
        # AI yanıtını üret
        try:
            # Görsel üretimi: Sadece kullanıcı görsel istediğinde veya kıyafet fikri sorduğunda
            # generate_ai_response fonksiyonu mesajı analiz edip otomatik karar verecek
            generate_images = False  # Varsayılan olarak False, fonksiyon içinde analiz edilecek
            ai_response = await generate_ai_response(message_text, generate_images=generate_images)
            ai_response_text = ai_response['content']
            ai_image_urls = ai_response.get('image_urls', [])
        except Exception as e:
            logger.error(f"AI yanıt üretme hatası: {e}", exc_info=True)
            ai_response_text = f"Mesajınızı aldım: {message_text}"
            if image_url:
                ai_response_text += f"\nGörsel URL: {image_url}"
            ai_image_urls = []
        
        # İlk görsel URL'ini database için kullan (backward compatibility)
        ai_image_url = ai_image_urls[0] if ai_image_urls else None
        
        # AI mesajını kaydet
        ai_message = Message(
            conversation_id=conversation_id,
            sender='ai',
            content=ai_response_text,
            image_url=ai_image_url
        )
        db.add(ai_message)
        db.commit()
        db.refresh(ai_message)
        
        # Kullanıcıya AI yanıtını gönder (tüm görselleri gönder)
        await sio.emit('ai_message', {
            'id': ai_message.id,
            'conversation_id': conversation_id,
            'content': ai_message.content,
            'image_url': ai_message.image_url,  # Backward compatibility için
            'image_urls': ai_image_urls,  # Tüm görselleri gönder
            'created_at': ai_message.created_at.isoformat() if ai_message.created_at else None
        }, room=sid)
        
        logger.info(f"AI response sent: {ai_message.id}")
        
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await sio.emit('error', {'message': 'Internal server error'}, room=sid)
        db.rollback()
    finally:
        db.close()


async def cleanup_old_guest_data():
    """Eski misafir verilerini otomatik temizler."""
    while True:
        try:
            await asyncio.sleep(300)  # Her 5 dakikada bir kontrol et
            now = datetime.now()
            expired_guests = []
            
            for guest_id, conv_data in guest_conversations.items():
                last_activity = conv_data.get('last_activity')
                if last_activity:
                    time_diff = now - last_activity
                    if time_diff > timedelta(minutes=GUEST_DATA_TIMEOUT_MINUTES):
                        expired_guests.append(guest_id)
            
            for guest_id in expired_guests:
                del guest_conversations[guest_id]
                logger.info(f"Guest data expired and deleted: {guest_id}")
                
        except Exception as e:
            logger.error(f"Error in cleanup_old_guest_data: {e}")

