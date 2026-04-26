"""
AI Clients - OpenAI, Tavily başlatma ve yönetimi
"""
import logging
from typing import Optional
from openai import OpenAI
from tavily import TavilyClient
from app.core.config import settings

logger = logging.getLogger(__name__)

# Global clients
openai_client: Optional[OpenAI] = None
tavily_client: Optional[TavilyClient] = None


def get_model_name() -> str:
    """Girilen API anahtarına göre doğru model adını döndürür"""
    if settings.openai_api_key and settings.openai_api_key.startswith("sk-"):
        return "gpt-4o-mini"
    return "gemini-2.5-flash"


def initialize_ai_clients():
    """AI client'larını başlatır (OpenAI, Tavily)"""
    global openai_client, tavily_client
    try:
        if settings.openai_api_key:
            if settings.openai_api_key.startswith("sk-"):
                # Native OpenAI
                openai_client = OpenAI(
                    api_key=settings.openai_api_key,
                    timeout=45.0
                )
                logger.info("✅ OpenAI (Native) Hazır (Model: gpt-4o-mini)")
            else:
                # Gemini üzerinden OpenAI SDK uyumluluğu
                openai_client = OpenAI(
                    api_key=settings.openai_api_key,
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                    timeout=45.0
                )
                logger.info("✅ OpenAI (Gemini Compatible) Hazır (Model: gemini-2.5-flash)")
        else:
            logger.warning("⚠️ OpenAI API key bulunamadı")
            
        if settings.tavily_api_key:
            try:
                tavily_client = TavilyClient(api_key=settings.tavily_api_key)
                # Test sorgusu ile API'nin çalıştığını doğrula
                test_response = tavily_client.search(query="test", max_results=1)
                if test_response:
                    logger.info("✅ Tavily Hazır ve API erişilebilir")
                else:
                    logger.warning("⚠️ Tavily API yanıt vermiyor")
            except Exception as tavily_error:
                logger.error(f"❌ Tavily başlatma hatası: {tavily_error}")
                tavily_client = None
        else:
            logger.warning("⚠️ Tavily API key bulunamadı")
        
        # SerpApi (Google Trends) kontrolü
        if settings.serpapi_api_key:
            try:
                from serpapi import GoogleSearch
                # Basit bir test sorgusu ile API'nin çalıştığını doğrula
                test_params = {
                    "engine": "google_trends",
                    "q": "test",
                    "data_type": "TIMESERIES",
                    "date": "now 1-d",
                    "geo": "TR",
                    "api_key": settings.serpapi_api_key
                }
                test_search = GoogleSearch(test_params)
                test_result = test_search.get_dict()
                if test_result and "error" not in test_result:
                    logger.info("✅ SerpApi Hazır (Google Trends)")
                else:
                    logger.warning(f"⚠️ SerpApi yanıt vermiyor: {test_result.get('error', 'Bilinmeyen hata')}")
            except ImportError:
                logger.warning("⚠️ SerpApi paketi yüklü değil (google-search-results)")
            except Exception as serpapi_error:
                logger.error(f"❌ SerpApi başlatma hatası: {serpapi_error}")
        else:
            logger.warning("⚠️ SerpApi API key bulunamadı (SERPAPI_API_KEY)")
            
    except Exception as e:
        logger.error(f"❌ Başlatma Hatası: {e}")



# Uygulama başladığında client'ları başlat
initialize_ai_clients()
