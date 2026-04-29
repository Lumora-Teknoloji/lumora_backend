# app/schemas/scraper.py
"""
Scraper API schema tanımları.
Tüm Pydantic model'leri burada merkezi olarak tanımlıdır.
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


# ==================== INGEST SCHEMAS ====================

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
    review_summary: Optional[str] = None
    sizes: Optional[List[str]] = None
    attributes: Optional[dict] = None

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


# ==================== TASK SCHEMAS ====================

class CreateTaskRequest(BaseModel):
    """Yeni görev oluşturma isteği."""
    task_name: str
    target_platform: str = "Trendyol"
    search_term: str = ""
    mode: str = "normal"  # linker, worker, normal
    page_limit: int = 50  # Sayfa limiti (ürün sayısı DEĞİL, sayfa sayısı)
    source_task_id: Optional[int] = None  # worker: which linker bot's queue to use
    start_time: Optional[str] = "09:00"
    end_time: Optional[str] = "18:00"
    scrape_interval: int = 24  # hours (frontend sends page_limit here sometimes)
    is_active: bool = False


class TaskResponse(BaseModel):
    """Görev yanıtı."""
    id: int
    search_term: str
    status: str
    task_type: str
    created_at: Optional[datetime] = None
    last_scraped_at: Optional[datetime] = None
    progress_percent: float = 0.0
    queue_stats: Optional[dict] = None


class StatusResponse(BaseModel):
    """Durum yanıtı."""
    total_products: int
    total_scraped: int
    daily_scraped: int
    active_bots: int
    system_health: float
    pending_links: int
    last_scrape_date: Optional[str] = None


# ==================== BOT SCHEMAS ====================

class BotStatusResponse(BaseModel):
    """Bot durum yanıtı."""
    id: int
    name: str
    platform: str
    status: str
    keyword: str
    start_time: str
    end_time: str
    scrape_interval_hours: int = 24
    page_limit: int
    is_active: bool
    stats: dict
    pending_links: int = 0
    last_message: Optional[str] = None
    last_product_url: Optional[str] = None
    is_critical: bool = False
    last_error: Optional[str] = None


class BotSettingsUpdate(BaseModel):
    """Bot ayar güncelleme isteği."""
    keyword: Optional[str] = None
    mode: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    page_limit: Optional[int] = None
    is_active: Optional[bool] = None
