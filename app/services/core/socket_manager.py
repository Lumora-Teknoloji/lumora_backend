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

from app.core.database import get_db
from app.models import Conversation, Message, User
from app.core.config import settings
from app.services.ai.ai_orchestrator import generate_ai_response
from app.schemas.socketio import UserMessageInput, GuestGetConversationInput
from app.core.security import decode_token
from fastapi import HTTPException
from app.services.core.socket_handlers.guest_handler import handle_guest_message
from app.services.core.socket_handlers.auth_handler import handle_auth_message

logger = logging.getLogger(__name__)

sio = socketio.AsyncServer(
    cors_allowed_origins=lambda origin, environ: True,
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


async def get_user_from_token(token: Optional[str]) -> Optional[User]:
    """Token'dan kullanıcıyı alır."""
    if not token:
        return None
    
    try:
        try:
            payload = decode_token(token)
        except PydanticValidationError:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        # Database session oluştur
        db = next(get_db())
        try:
            user = db.query(User).filter(User.id == int(user_id)).first()
            return user
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Socket auth error: {str(e)}")
        return None


@sio.event
async def connect(sid, environ, auth):
    """Client bağlandığında çağrılır."""
    token = None
    if auth and isinstance(auth, dict) and 'token' in auth and auth['token']:
        token = auth['token']
    
    if not token:
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
        guest_id = session.get('guest_id')
        await handle_guest_message(
            sio, sid, guest_id, conversation_id, message_text, image_url, generate_images, guest_conversations
        )
    else:
        user_id = session.get('user_id')
        await handle_auth_message(
            sio, sid, user_id, conversation_id, message_text, image_url, generate_images
        )


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
