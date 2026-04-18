from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio
import logging

from app.core.config import settings
from app.core.database import setup_database
from app.services.core.socket_manager import cleanup_old_guest_data

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama yaşam döngüsü yöneticisi."""
    # Startup
    # OPENAI key yoksa uygulamayı crash etmek yerine AI özelliklerini devre dışı bırakıp çalışmaya devam et.
    # (Login/REST endpoints çalışmaya devam etmeli; realtime akış da try/except ile fallback üretiyor.)
    if not settings.openai_api_key:
        if settings.app_env == "production":
            logger.error("❌ OPENAI_API_KEY is not configured! AI features will be disabled.")
        else:
            logger.warning("⚠️ OPENAI_API_KEY not set — AI features disabled.")
    
    logger.info("✅ Startup checks passed")
    
    setup_database()
    
    # Start scheduler for bot management
    from app.services.core.scheduler import start_scheduler_thread
    start_scheduler_thread()
    logger.info("✅ Bot scheduler started")
    
    asyncio.create_task(cleanup_old_guest_data())
    logger.info("Guest data cleanup task started")

    # Intelligence Client başlat (non-blocking — servis kapalı olsa bile backend çalışır)
    from app.services.intelligence.intelligence_client import intelligence_client
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
    
    # Redis Queue background loop'ları başlat
    # NOT: APIRouter lifespan desteklemediği için buraya taşındı (redis_queue.py'den).
    from app.routers.redis_queue import (
        _results_flusher_loop,
        _recovery_loop,
        _retry_requeue_loop,
    )
    redis_flusher_task = asyncio.create_task(_results_flusher_loop())
    redis_recovery_task = asyncio.create_task(_recovery_loop())
    redis_retry_task = asyncio.create_task(_retry_requeue_loop())
    logger.info("✅ Redis Queue background loop'ları başlatıldı (flusher, recovery, retry)")

    yield
    
    # Shutdown
    redis_flusher_task.cancel()
    redis_recovery_task.cancel()
    redis_retry_task.cancel()
    await intelligence_client.shutdown()
    logger.info("Application shutting down")
