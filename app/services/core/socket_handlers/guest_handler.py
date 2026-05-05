import logging
from datetime import datetime
from app.services.ai.ai_orchestrator import generate_ai_response
from app.services.ai.title_generator import generate_conversation_title

logger = logging.getLogger(__name__)

async def handle_guest_message(
    sio, sid, guest_id, conversation_id, message_text, image_url, generate_images, guest_conversations
):
    """Misafir kullanıcının mesajını işler."""
    if guest_id not in guest_conversations:
        await sio.emit('error', {'message': 'Guest session not found'}, room=sid)
        return
    
    guest_state = guest_conversations[guest_id]
    conversations = guest_state["conversations"]
    active_conv_id = guest_state.get("active_conversation_id")

    if not conversation_id:
        conversation_id = active_conv_id
    if not conversation_id or conversation_id not in conversations:
        await sio.emit('error', {'message': 'Guest conversation not found'}, room=sid)
        return

    guest_conv = conversations[conversation_id]
    guest_alias = guest_conv.get('alias') or "Misafir Sohbeti"
    
    guest_conv['last_activity'] = datetime.now()
    guest_state['last_activity'] = datetime.now()
    guest_state['active_conversation_id'] = conversation_id
    
    user_msg = {
        'id': f'{conversation_id}_msg_{len(guest_conv["messages"]) + 1}',
        'sender': 'user',
        'content': message_text,
        'image_url': image_url,
        'created_at': datetime.now().isoformat()
    }
    guest_conv['messages'].append(user_msg)

    if message_text and len(guest_conv["messages"]) <= 2:
        try:
            guest_alias = await generate_conversation_title(message_text)
            guest_conv['alias'] = guest_alias
            logger.info(f"Guest AI-generated title: {guest_alias}")
        except Exception as title_error:
            logger.warning(f"Guest title generation failed, using fallback: {title_error}")
            auto_alias = message_text.strip()[:40]
            if len(message_text.strip()) > 40:
                auto_alias += "..."
            guest_alias = auto_alias or guest_alias
            guest_conv['alias'] = guest_alias
    
    try:
        guest_history = []
        for m in guest_conv.get('messages', []):
            role = "assistant" if m.get('sender') == "ai" else "user"
            content = m.get('content', '')
            if content:
                guest_history.append({"role": role, "content": content, "sender": role})
        
        async def guest_stream_callback(chunk_content):
            await sio.emit('ai_message_chunk', {
                'conversation_id': conversation_id,
                'content': chunk_content
            }, room=sid)
        
        ai_response = await generate_ai_response(
            message_text, 
            chat_history=guest_history,
            generate_images=generate_images,
            stream_callback=guest_stream_callback
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
    
    ai_image_url_combined = ";".join(ai_image_urls) if ai_image_urls else None

    ai_msg = {
        'id': f'{conversation_id}_msg_{len(guest_conv["messages"]) + 1}',
        'sender': 'ai',
        'content': ai_response_text,
        'image_urls': ai_image_urls,
        'image_url': ai_image_url_combined,
        'image_links': ai_image_links,
        'created_at': datetime.now().isoformat()
    }
    guest_conv['messages'].append(ai_msg)
    
    await sio.emit('ai_message', {
        'id': ai_msg['id'],
        'conversation_id': conversation_id,
        'content': ai_msg['content'],
        'image_url': ai_image_url_combined,
        'image_urls': ai_image_urls,
        'image_links': ai_image_links,
        'alias': guest_alias,
        'created_at': ai_msg['created_at']
    }, room=sid)

    logger.info(f"Guest message processed: {guest_id} conversation {conversation_id}")
