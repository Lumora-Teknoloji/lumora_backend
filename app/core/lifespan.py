from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio
import logging

from app.core.config import settings
from app.core.database import setup_database
from app.socket_manager import cleanup_old_guest_data

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
    asyncio.create_task(cleanup_old_guest_data())
    logger.info("Guest data cleanup task started")
    
    yield
    
    # Shutdown (gerekirse temizlik işlemleri buraya)
    logger.info("Application shutting down")
