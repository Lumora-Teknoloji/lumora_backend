from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

def setup_cors(app: FastAPI):
    """CORS middleware yapılandırmasını ekler. Wildcard (*) YASAKTIR."""
    origins = settings.allowed_origins
    # GÜVENLİK: Wildcard origin asla kabul edilmez
    safe_origins = [o for o in origins if o and o != "*"]
    if not safe_origins:
        safe_origins = ["http://localhost:3000"]
        logger.warning("CORS: Tanımlı origin yok, sadece localhost:3000 izinli. CORS_ORIGINS env ayarlayın!")
    logger.info(f"CORS izinli origin'ler: {safe_origins}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=safe_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Requested-With", "Accept"],
    )
