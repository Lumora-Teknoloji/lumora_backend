import logging
from datetime import datetime
from app.core.database import get_db
from app.models import Conversation, Message
from app.services.ai.ai_orchestrator import generate_ai_response
from app.services.ai.title_generator import generate_conversation_title

logger = logging.getLogger(__name__)

async def handle_auth_message(
    sio, sid, user_id, conversation_id, message_text, image_url, generate_images
):
    """Kayıtlı kullanıcının mesajını işler."""
    if not user_id:
        await sio.emit('error', {'message': 'Unauthorized'}, room=sid)
        return
    
    if not conversation_id:
        await sio.emit('error', {'message': 'conversation_id is required'}, room=sid)
        return
    
    db = next(get_db())
    try:
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
        
        try:
            db_messages = db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at.desc()).limit(40).all()
            
            db_messages.reverse()
            
            chat_history = []
            for msg in db_messages:
                role = "assistant" if msg.sender == "ai" else "user"
                if msg.content:
                    chat_history.append({"role": role, "content": msg.content, "sender": role})
            
            async def auth_stream_callback(chunk_content):
                await sio.emit('ai_message_chunk', {
                    'conversation_id': conversation_id,
                    'content': chunk_content
                }, room=sid)
                
            ai_response = await generate_ai_response(
                message_text, 
                chat_history=chat_history,
                generate_images=generate_images,
                stream_callback=auth_stream_callback
            )
            ai_response_text = ai_response['content']
            ai_image_urls = ai_response.get('image_urls', [])
            ai_image_links = ai_response.get('image_links', {})
            process_log = ai_response.get('process_log', [])
        except Exception as e:
            logger.error(f"AI yanıt üretme hatası: {e}")
            ai_response_text = f"Sistemde bir hata oluştu: {str(e)}"
            ai_image_urls = []
            ai_image_links = {}
            process_log = [f"Hata: {str(e)}"]

        ai_image_url_combined = ";".join(ai_image_urls) if ai_image_urls else None

        ai_message = Message(
            conversation_id=conversation_id,
            sender='ai',
            content=ai_response_text,
            image_url=ai_image_url_combined,
            process_log=process_log
        )
        db.add(ai_message)
        
        # Konuşma başlığı yoksa oluştur
        alias = conversation.alias
        if not alias or alias.startswith("Yeni Sohbet") or alias.strip() == "":
            try:
                new_title = await generate_conversation_title(message_text)
                conversation.alias = new_title
                alias = new_title
                logger.info(f"Auth AI-generated title: {alias}")
            except Exception as title_error:
                logger.warning(f"Auth title generation failed: {title_error}")
                auto_alias = message_text.strip()[:40]
                if len(message_text.strip()) > 40:
                    auto_alias += "..."
                conversation.alias = auto_alias or "Sohbet"
                alias = conversation.alias
        
        db.commit()
        db.refresh(ai_message)
        
        await sio.emit('ai_message', {
            'id': ai_message.id,
            'conversation_id': conversation_id,
            'content': ai_message.content,
            'image_url': ai_message.image_url,
            'image_urls': ai_image_urls,
            'image_links': ai_image_links,
            'alias': alias,
            'created_at': ai_message.created_at.isoformat()
        }, room=sid)

        logger.info(f"AI message saved: {ai_message.id}")
        
    except Exception as e:
        logger.error(f"Error handling authenticated message: {e}", exc_info=True)
        await sio.emit('error', {'message': f'Sunucu hatası: {str(e)}'}, room=sid)
    finally:
        db.close()
