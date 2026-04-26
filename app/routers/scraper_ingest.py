from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
import logging
import os
import glob
import json
from datetime import datetime, timezone
import psutil
import platform
import traceback
from pathlib import Path
from sqlalchemy import func, desc, text
from datetime import datetime, timezone, time, timedelta
from app.core.database import get_db
from app.services.data.scraper_service import TrendyolScraperService
from app.models.scraping_task import ScrapingTask
from app.models.product import Product
from app.models.scraping_log import ScrapingLog
from app.schemas.scraper import (
    ScrapedProduct, IngestRequest, IngestResponse,
    CreateTaskRequest, TaskResponse, StatusResponse,
    BotStatusResponse, BotSettingsUpdate
)
logger = logging.getLogger(__name__)
from app.middleware.rate_limit import limiter
router = APIRouter(prefix="/scraper", tags=["Scraper"])

def get_scrapper_dir() -> Path:
    """Scrapper dizinini çalışma ortamına göre (Docker veya Local) döner."""
    # 1. Env variable (en yüksek öncelik)
    env_path = os.getenv("SCRAPPER_DIR")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
    
    # 2. Docker ortamında
    docker_path = Path("/Scrapper")
    if docker_path.exists() and (docker_path / "redis_agent.py").exists():
        return docker_path
    
    # 3. Local ortamda
    local_path = Path(__file__).parent.parent.parent.parent / "scrapper"
    if local_path.exists():
        return local_path
        
    local_path_cap = Path(__file__).parent.parent.parent.parent / "Scrapper"
    if local_path_cap.exists():
        return local_path_cap

    # Yerel Windows ortamında
    # scraper.py -> routers -> app -> LangChain_backend -> (Project Root)
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    
    possible_paths = [
        project_root / "Scrapper",
        project_root / "Scrapper-main",
    ]
    
    for path in possible_paths:
        if path.exists() and (path / "redis_agent.py").exists():
            return path
        
    # Fallback
    return project_root / "Scrapper"

# ==================== ENDPOINTS ====================

async def ingest_scraped_products(
    request: Request,
    ingest_request: IngestRequest,
    db: Session = Depends(get_db)
):
    """Scraper sonuçlarını toplu olarak veritabanına yazar."""
    if not ingest_request.products:
        raise HTTPException(status_code=400, detail="Ürün listesi boş olamaz")
    
    service = TrendyolScraperService(db)
    
    try:
        products_data = [p.model_dump() for p in ingest_request.products]
        stats = service.process_scraped_batch(products_data, ingest_request.task_id)
        
        return IngestResponse(
            success=True,
            inserted=stats["inserted"],
            updated=stats["updated"],
            errors=stats["errors"],
            message=f"Toplam {len(ingest_request.products)} ürün işlendi."
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"İşlem hatası: {str(e)}")