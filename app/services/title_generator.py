"""
AI Title Generator - Automatically generate conversation titles
"""
import logging
from typing import Optional
from .clients import openai_client

logger = logging.getLogger(__name__)


async def generate_conversation_title(user_message: str) -> str:
    """
    Kullanıcının ilk mesajından ChatGPT tarzında kısa bir başlık oluşturur.
    
    Args:
        user_message: Kullanıcının ilk mesajı
        
    Returns:
        2-5 kelimelik kısa başlık
    """
    if not openai_client:
        # OpenAI kullanılamıyorsa basit fallback
        fallback = user_message.strip()[:40]
        if len(user_message.strip()) > 40:
            fallback += "..."
        return fallback or "Yeni Konuşma"
    
    try:
        # OpenAI'ye başlık oluşturma isteği gönder
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "Sen bir başlık oluşturucu asistansın. Kullanıcının mesajını analiz edip, o konuyu en iyi özetleyen 2-5 kelimelik kısa ve özlü bir başlık oluştur. Sadece başlığı yaz, başka bir şey ekleme. Türkçe başlık oluştur."
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            max_tokens=20,
            temperature=0.7,
            timeout=10.0  # Hızlı yanıt
        )
        
        title = response.choices[0].message.content.strip()
        
        # Başlık çok uzunsa kısalt
        if len(title) > 50:
            title = title[:50] + "..."
            
        return title or "Yeni Konuşma"
        
    except Exception as e:
        logger.warning(f"Başlık oluşturulurken hata: {e}")
        # Hata durumunda fallback kullan
        fallback = user_message.strip()[:40]
        if len(user_message.strip()) > 40:
            fallback += "..."
        return fallback or "Yeni Konuşma"
