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


def initialize_ai_clients():
    """AI client'larını başlatır (OpenAI, Tavily)"""
    global openai_client, tavily_client
    try:
        if settings.openai_api_key:
            # Vision işlemleri bazen uzun sürebilir, timeout artırıldı
            openai_client = OpenAI(api_key=settings.openai_api_key, timeout=45.0)
            logger.info("✅ OpenAI Hazır")
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
