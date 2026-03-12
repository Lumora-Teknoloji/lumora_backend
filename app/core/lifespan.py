from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio
import logging

from app.core.config import settings
from app.core.database import setup_database
from app.services.socket_manager import cleanup_old_guest_data

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama yaşam döngüsü yöneticisi."""
    # Startup
    # Validate required API keys
    if not settings.openai_api_key:
        logger.error("❌ OPENAI_API_KEY is not configured!")
        raise ValueError("Missing required API key: OPENAI_API_KEY")
    
    logger.info("✅ API keys validated successfully")
    
    setup_database()
    
    # Start scheduler for bot management
    from app.services.scheduler import start_scheduler_thread
    start_scheduler_thread()
    logger.info("✅ Bot scheduler started")
    
    asyncio.create_task(cleanup_old_guest_data())
    logger.info("Guest data cleanup task started")

    # Intelligence Client başlat (non-blocking — servis kapalı olsa bile backend çalışır)
    from app.services.intelligence_client import intelligence_client
    await intelligence_client.startup()
    # Startup ping — sadece loglama, hata atmaz
    try:
        ping = await intelligence_client.health()
        if ping.get("status") == "ok":
            logger.info(f"✅ Intelligence servisi aktif — engine_trained={ping.get('engine_trained')}")
        else:
            logger.warning(
                f"⚠️  Intelligence servisi erişilemiyor (startup ping: {ping.get('status', 'unknown')}). "
                "Backend normal çalışmaya devam eder, /api/intelligence/* endpointleri 503 döner."
            )
    except Exception as e:
        logger.warning(
            f"⚠️  Intelligence startup ping başarısız: {e}. "
            "Intelligence servisini ayrıca başlatmayı unutmayın."
        )
    
    yield
    
    # Shutdown
    await intelligence_client.shutdown()
    logger.info("Application shutting down")
