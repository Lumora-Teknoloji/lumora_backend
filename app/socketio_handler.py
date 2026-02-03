"""
Socket.IO handler for real-time chat functionality.
"""
import logging
from typing import Optional
import socketio
import uuid
from datetime import datetime, timedelta
import asyncio
from pydantic import ValidationError as PydanticValidationError

from .database import get_db
from .models import Conversation, Message, User
from .config import settings
from .ai_services import generate_ai_response
from .schemas_socketio import UserMessageInput, GuestGetConversationInput

logger = logging.getLogger(__name__)

sio = socketio.AsyncServer(
    cors_allowed_origins=settings.allowed_origins if settings.cors_origins != "*" else "*",
    async_mode='asgi',
    logger=True,  # Debug için logging aktif
    engineio_logger=True  # Engine.IO debug için
)

guest_conversations: dict[str, dict] = {}
GUEST_DATA_TIMEOUT_MINUTES = 30


def _create_guest_conversation(guest_id: str, alias: str | None = None) -> dict:
    """Misafir için yeni conversation kaydı oluşturur."""
    conv_id = f"guest_{uuid.uuid4()}"
    return {
        "id": conv_id,
        "alias": alias or "Misafir Sohbeti",
        "messages": [],
        "last_activity": datetime.now(),
    }


from .core.security import decode_token
from fastapi import HTTPException

async def get_user_from_token(token: Optional[str]) -> Optional[User]:
    """Token'dan kullanıcıyı alır."""
    if not token:
        return None
    
    try:
        # Token'ı decode et
        try:
            payload = decode_token(token)
        except HTTPException:
            # Token geçersiz veya süresi dolmuş
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
    # HttpOnly cookie'den token al
    token = None
    cookie_header = environ.get('HTTP_COOKIE', '')
    if cookie_header:
        import http.cookies
        cookies = http.cookies.SimpleCookie()
        cookies.load(cookie_header)
        if 'access_token' in cookies:
            token = cookies['access_token'].value
    
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
        # Misafir için ilk conversation oluştur ve listeyi hazırla
        first_conv = _create_guest_conversation(guest_id)
        guest_conversations[guest_id] = {
            "conversations": {first_conv["id"]: first_conv},
            "active_conversation_id": first_conv["id"],
            "last_activity": datetime.now(),
        }
        await sio.emit(
            "guest_conversation_list",
            {
                "conversations": [
                    {"id": first_conv["id"], "alias": first_conv["alias"]}
                ]
            },
            room=sid,
        )
    
    return True


@sio.event
async def guest_new_conversation(sid):
    """Misafir için yeni bir boş sohbet oluşturur ve aktif yapar."""
    session = await sio.get_session(sid)
    guest_id = session.get("guest_id")
    if not guest_id or guest_id not in guest_conversations:
        await sio.emit("error", {"message": "Guest session not found"}, room=sid)
        return

    new_conv = _create_guest_conversation(guest_id)
    guest_state = guest_conversations[guest_id]
    guest_state["conversations"][new_conv["id"]] = new_conv
    guest_state["active_conversation_id"] = new_conv["id"]
    guest_state["last_activity"] = datetime.now()

    await sio.emit(
        "guest_conversation_created",
        {"id": new_conv["id"], "alias": new_conv["alias"]},
        room=sid,
    )


@sio.event
async def guest_get_conversation(sid, data):
    """Misafir için seçili sohbetin geçmişini döner."""
    # Validate input data
    try:
        validated_data = GuestGetConversationInput(**data)
        conv_id = validated_data.conversation_id
    except PydanticValidationError as e:
        logger.warning(f"Invalid guest_get_conversation input: {e}")
        await sio.emit("error", {
            "message": "Geçersiz sohbet ID'si",
            "details": str(e)
        }, room=sid)
        return
    
    session = await sio.get_session(sid)
    guest_id = session.get("guest_id")
    if not guest_id or guest_id not in guest_conversations:
        await sio.emit("error", {"message": "Guest session not found"}, room=sid)
        return
    guest_state = guest_conversations[guest_id]
    conversations = guest_state["conversations"]

    if not conv_id or conv_id not in conversations:
        await sio.emit("error", {"message": "Guest conversation not found"}, room=sid)
        return

    guest_conv = conversations[conv_id]
    guest_state["active_conversation_id"] = conv_id
    guest_conv["last_activity"] = datetime.now()
    guest_state["last_activity"] = datetime.now()

    await sio.emit(
        "guest_conversation_data",
        {
            "conversation_id": conv_id,
            "alias": guest_conv.get("alias") or "Misafir Sohbeti",
            "messages": guest_conv.get("messages", []),
        },
        room=sid,
    )


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
    # Validate input data
    try:
        validated_data = UserMessageInput(**data)
        conversation_id = validated_data.conversation_id
        message_text = validated_data.message
        image_url = validated_data.image_url
        generate_images = validated_data.generate_images
    except PydanticValidationError as e:
        logger.warning(f"Invalid user_message input: {e}")
        await sio.emit('error', {
            'message': 'Geçersiz mesaj formatı. Lütfen mesajınızı kontrol edin.',
            'details': str(e)
        }, room=sid)
        return
    
    session = await sio.get_session(sid)
    is_guest = session.get('is_guest', False)
    
    if is_guest:
        # Misafir kullanıcı için işlem
        guest_id = session.get('guest_id')
        if not guest_id or guest_id not in guest_conversations:
            await sio.emit('error', {'message': 'Guest session not found'}, room=sid)
            return
        
        guest_state = guest_conversations[guest_id]
        conversations = guest_state["conversations"]
        active_conv_id = guest_state.get("active_conversation_id")

        # conversation_id yoksa aktif olanı kullan; aktif de yoksa hata
        if not conversation_id:
            conversation_id = active_conv_id
        if not conversation_id or conversation_id not in conversations:
            await sio.emit('error', {'message': 'Guest conversation not found'}, room=sid)
            return

        guest_conv = conversations[conversation_id]
        guest_alias = guest_conv.get('alias') or "Misafir Sohbeti"
        
        # Son aktivite zamanını güncelle
        guest_conv['last_activity'] = datetime.now()
        guest_state['last_activity'] = datetime.now()
        guest_state['active_conversation_id'] = conversation_id
        
        # Kullanıcı mesajını memory'ye ekle
        user_msg = {
            'id': f'{conversation_id}_msg_{len(guest_conv["messages"]) + 1}',
            'sender': 'user',
            'content': message_text,
            'image_url': image_url,
            'created_at': datetime.now().isoformat()
        }
        guest_conv['messages'].append(user_msg)

        # İlk kullanıcı mesajından takma ad üret (ChatGPT gibi akıllı başlık)
        if message_text:
            from .ai_services import generate_conversation_title
            try:
                # AI ile akıllı başlık oluştur
                guest_alias = await generate_conversation_title(message_text)
                guest_conv['alias'] = guest_alias
                logger.info(f"Guest AI-generated title: {guest_alias}")
            except Exception as title_error:
                logger.warning(f"Guest title generation failed, using fallback: {title_error}")
                # Fallback: İlk 40 karakter
                auto_alias = message_text.strip()[:40]
                if len(message_text.strip()) > 40:
                    auto_alias += "..."
                guest_alias = auto_alias or guest_alias
                guest_conv['alias'] = guest_alias
        
        # AI yanıtını üret
        try:
            # Görsel üretimi: Kullanıcı butona bastığında veya mesajında istediğinde
            generate_images = validated_data.generate_images
            ai_response = await generate_ai_response(message_text, generate_images=generate_images)
            ai_response_text = ai_response['content']
            ai_image_urls = ai_response.get('image_urls', [])
            ai_image_links = ai_response.get('image_links', {})
        except Exception as e:
            logger.error(f"AI yanıt üretme hatası: {e}", exc_info=True)
            ai_response_text = f"Mesajınızı aldım: {message_text}"
            if image_url:
                ai_response_text += f".Görsel URL: {image_url}"
            ai_image_urls = []
            ai_image_links = {}
        
        # AI mesajını memory'ye ekle
        ai_image_url_combined = ";".join(ai_image_urls) if ai_image_urls else None

        ai_msg = {
            'id': f'{conversation_id}_msg_{len(guest_conv["messages"]) + 1}',
            'sender': 'ai',
            'content': ai_response_text,
            'image_urls': ai_image_urls,
            'image_url': ai_image_url_combined,  # backward compatibility / persistence
            'image_links': ai_image_links,  # Görsel-link eşleştirmesi
            'created_at': datetime.now().isoformat()
        }
        guest_conv['messages'].append(ai_msg)
        
        # Kullanıcıya AI yanıtını gönder (tüm görselleri gönder)
        await sio.emit('ai_message', {
            'id': ai_msg['id'],
            'conversation_id': conversation_id,
            'content': ai_msg['content'],
            'image_url': ai_image_url_combined,  # Tüm görseller ';' ile saklandı
            'image_urls': ai_image_urls,  # Tüm görselleri gönder
            'image_links': ai_image_links,  # Görsel-link eşleştirmesi
            'alias': guest_alias,
            'created_at': ai_msg['created_at']
        }, room=sid)

        logger.info(f"Guest message processed: {guest_id} conversation {conversation_id}")
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
            # Geçmişi hazırla
            history = conversation.history_json or []
            
            # Streaming callback fonksiyonu
            async def stream_callback(chunk_content):
                await sio.emit('ai_message_chunk', {
                    'conversation_id': conversation_id,
                    'content': chunk_content
                }, room=sid)

            # Görsel üretimi: Kullanıcı butona bastığında veya mesajında istediğinde
            generate_images = validated_data.generate_images
            ai_response = await generate_ai_response(
                message_text, 
                chat_history=history,
                generate_images=generate_images,
                stream_callback=stream_callback
            )
            ai_response_text = ai_response['content']
            ai_image_urls = ai_response.get('image_urls', [])
            ai_image_links = ai_response.get('image_links', {})
        except Exception as e:
            logger.error(f"AI yanıt üretme hatası: {e}", exc_info=True)
            ai_response_text = f"Mesajınızı aldım: {message_text}"
            if image_url:
                ai_response_text += f".Görsel URL: {image_url}"
            ai_image_urls = []
            ai_image_links = {}
        
        # DB'de tek kolon olduğu için tüm görselleri ';' ile birleştirerek saklıyoruz
        ai_image_url = ";".join(ai_image_urls) if ai_image_urls else None
        
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

        # Sohbet geçmişini JSON olarak güncelle
        history = conversation.history_json or []
        history.extend(
            [
                {
                    "id": user_message.id,
                    "sender": user_message.sender,
                    "content": user_message.content,
                    "image_url": user_message.image_url,
                    "created_at": user_message.created_at.isoformat()
                    if user_message.created_at
                    else None,
                },
                {
                    "id": ai_message.id,
                    "sender": ai_message.sender,
                    "content": ai_message.content,
                    "image_url": ai_message.image_url,
                    "image_urls": ai_image_urls,
                    "image_links": ai_image_links,  # Görsel-link eşleştirmesi
                    "created_at": ai_message.created_at.isoformat()
                    if ai_message.created_at
                    else None,
                },
            ]
        )

        # İlk kullanıcı mesajından otomatik takma ad üret (ChatGPT gibi akıllı başlık)
        if not conversation.alias and user_message.content:
            from .ai_services import generate_conversation_title
            try:
                # AI ile akıllı başlık oluştur
                auto_alias = await generate_conversation_title(user_message.content)
                conversation.alias = auto_alias
                logger.info(f"AI-generated title: {auto_alias}")
            except Exception as title_error:
                logger.warning(f"Title generation failed, using fallback: {title_error}")
                # Fallback: İlk 40 karakter
                auto_alias = user_message.content.strip()[:40]
                if len(user_message.content.strip()) > 40:
                    auto_alias += "..."
                conversation.alias = auto_alias or conversation.title or "Sohbet"

        conversation.history_json = history
        db.add(conversation)
        db.commit()
        
        # Kullanıcıya AI yanıtını gönder (tüm görselleri gönder)
        await sio.emit('ai_message', {
            'id': ai_message.id,
            'conversation_id': conversation_id,
            'content': ai_message.content,
            'image_url': ai_message.image_url,  # Backward compatibility için
            'image_urls': ai_image_urls,  # Tüm görselleri gönder
            'image_links': ai_image_links,  # Görsel-link eşleştirmesi
            'alias': conversation.alias,  # Sidebar başlığı güncellemesi için
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
            
            for guest_id, guest_state in guest_conversations.items():
                last_activity = guest_state.get('last_activity')
                if last_activity:
                    time_diff = now - last_activity
                    if time_diff > timedelta(minutes=GUEST_DATA_TIMEOUT_MINUTES):
                        expired_guests.append(guest_id)
            
            for guest_id in expired_guests:
                del guest_conversations[guest_id]
                logger.info(f"Guest data expired and deleted: {guest_id}")
                
        except Exception as e:
            logger.error(f"Error in cleanup_old_guest_data: {e}")

