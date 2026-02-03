# app/routers/scraper.py
"""
Scraper API endpoint'leri.
- Task yönetimi
- Veri gönderimi
- Durum sorgulama
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.services.scraper_service import TrendyolScraperService

router = APIRouter(prefix="/scraper", tags=["Scraper"])


# ==================== SCHEMAS ====================

class ScrapedProduct(BaseModel):
    """Scraper'dan gelen ürün verisi."""
    product_id: str
    ProductName: Optional[str] = None
    Brand: Optional[str] = None
    Seller: Optional[str] = None
    URL: Optional[str] = None
    Price: Optional[str] = None
    Discount: Optional[str] = None
    Rating: Optional[str] = None
    Size: Optional[List[str]] = None
    Image_URLs: Optional[List[str]] = None
    BasketCount: Optional[str] = None
    FavoriteCount: Optional[str] = None
    ViewCount: Optional[str] = None
    QACount: Optional[str] = None
    category_tag: Optional[str] = None
    
    class Config:
        extra = "allow"


class IngestRequest(BaseModel):
    """Toplu veri gönderme isteği."""
    products: List[ScrapedProduct]
    task_id: Optional[int] = None


class IngestResponse(BaseModel):
    """İşlem sonucu."""
    success: bool
    inserted: int
    updated: int
    errors: int
    message: str


class CreateTaskRequest(BaseModel):
    """Yeni görev oluşturma isteği."""
    user_id: int
    search_term: str
    task_type: str = "CATEGORY_SEARCH"


class TaskResponse(BaseModel):
    """Görev yanıtı."""
    id: int
    search_term: str
    status: str
    task_type: str
    created_at: Optional[datetime] = None
    last_scraped_at: Optional[datetime] = None


class StatusResponse(BaseModel):
    """Durum yanıtı."""
    total_products: int
    total_daily_metrics: int
    last_scrape_date: Optional[str] = None


# ==================== ENDPOINTS ====================

@router.post("/ingest", response_model=IngestResponse)
async def ingest_scraped_products(
    request: IngestRequest,
    db: Session = Depends(get_db)
):
    """Scraper sonuçlarını toplu olarak veritabanına yazar."""
    if not request.products:
        raise HTTPException(status_code=400, detail="Ürün listesi boş olamaz")
    
    service = TrendyolScraperService(db)
    
    try:
        products_data = [p.model_dump() for p in request.products]
        stats = service.process_scraped_batch(products_data, request.task_id)
        
        return IngestResponse(
            success=True,
            inserted=stats["inserted"],
            updated=stats["updated"],
            errors=stats["errors"],
            message=f"Toplam {len(request.products)} ürün işlendi."
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"İşlem hatası: {str(e)}")


@router.post("/tasks", response_model=TaskResponse)
async def create_scraping_task(
    request: CreateTaskRequest,
    db: Session = Depends(get_db)
):
    """Yeni scraping görevi oluşturur."""
    service = TrendyolScraperService(db)
    
    try:
        task = service.create_task(
            user_id=request.user_id,
            search_term=request.search_term,
            task_type=request.task_type
        )
        db.commit()
        
        return TaskResponse(
            id=task.id,
            search_term=task.search_term,
            status=task.status,
            task_type=task.task_type
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Görev oluşturma hatası: {str(e)}")


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    """Görev detaylarını getirir."""
    service = TrendyolScraperService(db)
    task = service.get_task_by_id(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    
    return TaskResponse(
        id=task.id,
        search_term=task.search_term,
        status=task.status,
        task_type=task.task_type,
        last_scraped_at=task.last_scraped_at
    )


@router.patch("/tasks/{task_id}/status")
async def update_task_status(
    task_id: int,
    status: str,
    db: Session = Depends(get_db)
):
    """Görev durumunu günceller."""
    service = TrendyolScraperService(db)
    task = service.get_task_by_id(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    
    service.update_task_status(task_id, status)
    db.commit()
    
    return {"success": True, "task_id": task_id, "new_status": status}


@router.get("/tasks")
async def list_active_tasks(db: Session = Depends(get_db)):
    """Aktif görevleri listeler."""
    service = TrendyolScraperService(db)
    tasks = service.get_active_tasks()
    
    return [
        TaskResponse(
            id=t.id,
            search_term=t.search_term,
            status=t.status,
            task_type=t.task_type,
            last_scraped_at=t.last_scraped_at
        )
        for t in tasks
    ]


@router.get("/status", response_model=StatusResponse)
async def get_scraper_status(db: Session = Depends(get_db)):
    """Genel scraper durumunu döner."""
    service = TrendyolScraperService(db)
    
    total_products = service.get_product_count()
    total_metrics = service.get_daily_metric_count()
    last_date = service.get_last_scrape_date()
    
    return StatusResponse(
        total_products=total_products,
        total_daily_metrics=total_metrics,
        last_scrape_date=last_date.isoformat() if last_date else None
    )
