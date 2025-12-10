"""
AI Clients - OpenAI, Tavily başlatma ve yönetimi
"""
import logging
from typing import Optional
from openai import OpenAI
from tavily import TavilyClient
from ..config import settings

logger = logging.getLogger(__name__)

# Global clients
openai_client: Optional[OpenAI] = None
tavily_client: Optional[TavilyClient] = None


def initialize_ai_clients():
    """AI client'larını başlatır (OpenAI, Tavily)"""
    global openai_client, tavily_client
    try:
        if settings.openai_api_key:
            # Vision işlemleri bazen uzun sürebilir, timeout artırıldı
            openai_client = OpenAI(api_key=settings.openai_api_key, timeout=45.0)
            logger.info("✅ OpenAI Hazır")
        if settings.tavily_api_key:
            tavily_client = TavilyClient(api_key=settings.tavily_api_key)
            logger.info("✅ Tavily Hazır")
    except Exception as e:
        logger.error(f"❌ Başlatma Hatası: {e}")


# Uygulama başladığında client'ları başlat
initialize_ai_clients()

