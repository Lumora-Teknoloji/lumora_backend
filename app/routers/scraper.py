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
import logging
import os
import glob
import json
import psutil
import platform
import traceback
from pathlib import Path
from sqlalchemy import func, desc, text
from app.core.database import get_db
from app.services.scraper_service import TrendyolScraperService
from datetime import datetime, timezone, time, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scraper", tags=["Scraper"])

def get_scrapper_dir() -> Path:
    """Scrapper dizinini çalışma ortamına göre (Docker veya Local) döner."""
    docker_path = Path("/Scrapper")
    if docker_path.exists():
        return docker_path
    
    # Linux Remote Server
    linux_path = Path("/var/www/scrapper/Scrapper")
    if linux_path.exists(): 
        return linux_path

    # Yerel Windows ortamında (Backend Docker dışında çalışıyorsa)
    # Backend c:\Users\Admin\Documents\vscode\LangChain_backend
    # Scrapper c:\Users\Admin\Documents\vscode\Scrapper-main
    local_path = Path("c:/Users/Admin/Documents/vscode/Scrapper-main")
    
    # Ensure commands directory exists
    commands_dir = local_path / "commands"
    try:
        commands_dir.mkdir(parents=True, exist_ok=True)
    except:
        pass
        
    return local_path


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
    task_name: str
    target_platform: str = "Trendyol"
    search_term: str
    start_time: Optional[str] = "09:00"
    end_time: Optional[str] = "18:00"
    scrape_interval: int = 24  # hours
    is_active: bool = False


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
    total_scraped: int
    daily_scraped: int
    active_bots: int
    system_health: float
    pending_links: int
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
    from app.models.scraping_task import ScrapingTask
    from datetime import datetime, timedelta
    
    try:
        # Create new task with frontend fields
        new_task = ScrapingTask(
            task_name=request.task_name,
            target_platform=request.target_platform,
            search_params={"search_term": request.search_term},
            target_url=f"https://www.trendyol.com/sr?q={request.search_term}",
            scrape_interval_hours=request.scrape_interval,
            is_active=request.is_active,
            start_time=request.start_time,
            end_time=request.end_time,
            next_run_at=datetime.now() + timedelta(hours=request.scrape_interval) if request.is_active else None
        )
        
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        
        return TaskResponse(
            id=new_task.id,
            search_term=request.search_term,
            status="active" if new_task.is_active else "inactive",
            task_type=request.target_platform
        )
    except Exception as e:
        db.rollback()
        error_msg = str(e)
        if "unique constraint" in error_msg.lower():
            raise HTTPException(status_code=400, detail=f"'{request.search_term}' araması için zaten bir bot mevcut.")
        raise HTTPException(status_code=500, detail=f"Görev oluşturma hatası: {error_msg}")


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


class BotStatusResponse(BaseModel):
    """Bot durum yanıtı."""
    id: int
    name: str
    platform: str
    status: str
    keyword: str
    start_time: str
    end_time: str
    page_limit: int
    is_active: bool
    stats: dict
    pending_links: int = 0
    last_message: Optional[str] = None
    last_product_url: Optional[str] = None
    is_critical: bool = False
    last_error: Optional[str] = None


@router.get("/bots/status")
async def get_bots_status(db: Session = Depends(get_db)):
    """Tüm botların durumunu listeler (frontend için)."""
    from app.models.scraping_task import ScrapingTask
    from app.models.product import Product
    from app.models.scraping_log import ScrapingLog
    
    tasks = db.query(ScrapingTask).all()
    
    bots = []
    for task in tasks:
        # Get latest log for this task
        last_log = db.query(ScrapingLog).filter(ScrapingLog.task_id == task.id).order_by(desc(ScrapingLog.started_at)).first()
        
        is_critical = False
        last_error_msg = None
        if last_log:
            is_critical = getattr(last_log, 'is_critical', False)
            last_error_msg = getattr(last_log, 'last_error', None)

        # Check bot status via PID file
        scrapper_dir = get_scrapper_dir()
        pid_file = scrapper_dir / f"bot_{task.id}.pid"
        actual_status = "stopped"
        if pid_file.exists():
            try:
                with open(pid_file, "r") as f:
                    pid = int(f.read().strip())
                # PID dosyası varsa running kabul et (Windows service yönetiyor)
                actual_status = "running"
                
                # Check for worker marker
                worker_marker = scrapper_dir / f"bot_{task.id}.worker"
                if worker_marker.exists():
                    actual_status = "worker_running"
            except:
                pass
        
        # Override with is_active flag from DB
        if task.is_active and actual_status == "stopped":
            actual_status = "idle"  # Aktif ama henüz çalışmıyor
        
        # Count products scraped based on ACTUAL items in products table for THIS bot
        try:
            from app.models.product import Product
            scraped_count = db.query(func.count(Product.id)).filter(Product.task_id == task.id).scalar() or 0
        except Exception as e:
            print(f"Scraped Count Error: {e}")
            scraped_count = 0
        
        # Count errors from scraping_logs
        error_count = 0
        try:
            from app.models.product import Base
            from sqlalchemy import text
            result = db.execute(
                text("SELECT COUNT(*) FROM scraping_logs WHERE task_id = :tid AND errors > 0"),
                {"tid": task.id}
            ).scalar()
            error_count = result or 0
        except:
            pass
            
        # Calculate Speed (Items per minute in the last hour)
        try:
            from datetime import timedelta, timezone
            now_aware = datetime.now(timezone.utc)
            one_hour_ago = now_aware - timedelta(hours=1)
            
            recent_count_query = db.query(func.count(Product.id)).filter(
                Product.task_id == task.id,
                Product.last_scraped_at >= one_hour_ago
            )
            recent_count = recent_count_query.scalar() or 0
            # Speed = Items / 60 mins (average over last hour)
            speed = round(recent_count / 60, 1) if recent_count > 0 else 0
        except Exception as e:
            print(f"Speed Calc Error (Task {task.id}): {e}")
            speed = 0
        
        # Count pending links in queue for THIS bot
        try:
            from sqlalchemy import text
            pending_count = db.execute(
                text("SELECT COUNT(*) FROM scraping_queue WHERE task_id = :tid AND status = 'pending'"),
                {"tid": task.id}
            ).scalar() or 0
        except:
            pending_count = 0
            speed = 0

        # IP Change (Sum from all logs for this task)
        try:
            ip_change_count = db.query(func.sum(ScrapingLog.ip_rotations)).filter(ScrapingLog.task_id == task.id).scalar() or 0
        except:
            ip_change_count = 0
        
        # Get last scraped product for this bot
        last_product = db.query(Product).filter(Product.task_id == task.id).order_by(desc(Product.last_scraped_at)).first()
        
        last_msg = f"Next run: {task.next_run_at}" if task.next_run_at else "Hazır."
        last_url = None
        
        if actual_status in ["running", "worker_running"]:
            last_msg = "🚀 Veri kazıma işlemi devam ediyor..."
        
        if last_product:
            # Ensure aware comparison
            now = datetime.now(timezone.utc)
            last_scraped = last_product.last_scraped_at
            
            # If last_scraped is naive, make it aware (for safety)
            if last_scraped and last_scraped.tzinfo is None:
                last_scraped = last_scraped.replace(tzinfo=timezone.utc)

            # If product was scraped recently (within last 30 mins), show it as live
            if last_scraped and (now - last_scraped).total_seconds() < 1800:
                price_str = f" ({last_product.last_price} TL)" if last_product.last_price else ""
                last_msg = f"🛍️ {last_product.brand} {last_product.name}{price_str}"
                last_url = last_product.url

        bot = {
            "id": task.id,
            "name": task.task_name or "Unnamed Bot",
            "platform": task.target_platform or "Trendyol",
            "status": actual_status,
            "keyword": task.search_params.get("search_term", "") if task.search_params else "",
            "start_time": task.start_time or "09:00",
            "end_time": task.end_time or "18:00",
            "page_limit": task.search_params.get("page_limit", 24) if task.search_params else 24,
            "is_active": task.is_active,
            "pending_links": pending_count,
            "stats": {
                "scraped": scraped_count,
                "validated": speed,      # Frontend shows this as SPEED (Items/Min)
                "errors": error_count,
                "processed": ip_change_count # Frontend shows this as IP CHANGE
            },
            "last_message": last_msg,
            "last_product_url": last_url
        }
        bots.append(bot)
    
    return bots


@router.get("/status", response_model=StatusResponse)
async def get_scraper_status(db: Session = Depends(get_db)):
    """Genel scraper durumunu döner."""
    from app.models.product import Product
    from app.models.scraping_log import ScrapingLog
    from app.models.scraping_task import ScrapingTask
    from sqlalchemy import func
    import os
    
    # 1. Toplam Ürün Sayısı (Unique)
    total_products = db.query(func.count(Product.id)).scalar() or 0
    
    # 2. Toplam Kazınan Veri (Tüm Zamanların Toplam Başarı İşlemi)
    # Sadece unique ürün değil, her başarılı tarama (yeni + güncelleme) sayılır.
    total_added = db.query(func.sum(ScrapingLog.products_added)).scalar() or 0
    total_updated = db.query(func.sum(ScrapingLog.products_updated)).scalar() or 0
    total_scraped = int(total_added + total_updated)

    # 3. Günlük Kazınan Veri (Takvim Günü - Gece 00:00'dan Beri)
    from datetime import datetime, time, timezone
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    daily_added = db.query(func.sum(ScrapingLog.products_added)).filter(ScrapingLog.started_at >= today_start).scalar() or 0
    daily_updated = db.query(func.sum(ScrapingLog.products_updated)).filter(ScrapingLog.started_at >= today_start).scalar() or 0
    daily_scraped = (daily_added or 0) + (daily_updated or 0)
    
    active_bots = 0
    tasks = db.query(ScrapingTask).all()
    scrapper_dir = get_scrapper_dir()
    for task in tasks:
        pid_file = scrapper_dir / f"bot_{task.id}.pid"
        if pid_file.exists():
            active_bots += 1
    
    # 5. Sistem Sağlığı (% Başarı Oranı)
    total_errors = db.query(func.sum(ScrapingLog.errors)).scalar() or 0
    total_attempts = total_scraped + total_errors
    
    health = (total_scraped / total_attempts * 100) if total_attempts > 0 else 100.0
    if health > 100: health = 100.0
    
    # 6. Bekleyen Link Sayısı (Kuyruk)
    from sqlalchemy import text
    pending_links = db.execute(text("SELECT count(*) FROM scraping_queue WHERE status = 'pending'")).scalar() or 0
    
    # Son tarama tarihi
    last_log = db.query(ScrapingLog).order_by(ScrapingLog.started_at.desc()).first()
    last_date = last_log.started_at if last_log else None
    
    return StatusResponse(
        total_products=total_products,
        total_scraped=total_scraped,
        daily_scraped=daily_scraped,
        active_bots=active_bots,
        system_health=round(health, 1),
        pending_links=pending_links,
        last_scrape_date=last_date.isoformat() if last_date else None
    )


# ==================== BOT CONTROL ENDPOINTS ====================

@router.post("/bots/{bot_id}/start")
async def start_bot(bot_id: int, db: Session = Depends(get_db)):
    """Botu başlatır - dosya tabanlı komut sistemi (Docker → Windows)."""
    from app.models.scraping_task import ScrapingTask
    import json, os
    
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
    
    # Activate in database
    task.is_active = True
    db.commit()
    
    # Write command file for Windows launcher service
    scrapper_dir = get_scrapper_dir()
    commands_dir = scrapper_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    
    cmd_file = commands_dir / f"start_{bot_id}.json"
    with open(cmd_file, "w") as f:
        json.dump({
            "type": "START",
            "task_id": bot_id,
            "target_url": task.target_url,
            "task_name": task.task_name,
            "max_pages": task.scrape_interval_hours or 50, # Default to 50 if 0/Null
            "force": True # Manual start override
        }, f)
    
    return {"success": True, "message": f"Bot {task.task_name} başlatma komutu gönderildi"}


@router.post("/bots/{bot_id}/worker")
async def worker_start_bot(bot_id: int, db: Session = Depends(get_db)):
    """Botu sadece kuyruk eritme (worker) modunda başlatır."""
    from app.models.scraping_task import ScrapingTask
    import json, os
    
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
    
    # Write command file for Windows launcher service with type WORKER
    scrapper_dir = get_scrapper_dir()
    commands_dir = scrapper_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    
    cmd_file = commands_dir / f"worker_{bot_id}.json"
    with open(cmd_file, "w") as f:
        json.dump({
            "type": "WORKER",
            "task_id": bot_id,
            "target_url": task.target_url,
            "task_name": task.task_name,
            "force": True
        }, f)
    
    return {"success": True, "message": f"Bot {task.task_name} kuyruk eritme (worker) komutu gönderildi"}


@router.post("/bots/{bot_id}/stop")
async def stop_bot(bot_id: int, db: Session = Depends(get_db)):
    """Botu durdurur - dosya tabanlı komut sistemi (Docker → Windows)."""
    from app.models.scraping_task import ScrapingTask
    import json, os
    
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
    
    # Deactivate in database and clear schedule
    task.is_active = False
    task.next_run_at = None
    db.commit()
    
    # Write command file for Windows launcher service
    scrapper_dir = get_scrapper_dir()
    commands_dir = scrapper_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    
    cmd_file = commands_dir / f"stop_{bot_id}.json"
    with open(cmd_file, "w") as f:
        json.dump({
            "type": "STOP",
            "task_id": bot_id
        }, f)
    
    return {"success": True, "message": f"Bot {task.task_name} durduruldu ve planı temizlendi"}


@router.delete("/bots/{bot_id}")
async def delete_bot(bot_id: int, db: Session = Depends(get_db)):
    """Botu ve onunla ilişkili tüm verileri siler."""
    from app.models.scraping_task import ScrapingTask
    from sqlalchemy import text
    
    try:
        task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Bot bulunamadı")
        
        task_name = task.task_name
        
        # İlişkili verileri manuel sil (ForeignKey hatalarını önlemek için)
        # SIRA ÖNEMLİ: En uçtaki tablodan başlıyoruz
        try:
            # 1. Kuyruğu temizle (İşlenmemiş linkler gidebilir)
            db.execute(text("DELETE FROM scraping_queue WHERE task_id = :tid"), {"tid": bot_id})
            
            # 2. Logları KORU ama bot ile bağını kes (Global istatistikler düşmesin diye)
            db.execute(text("UPDATE scraping_logs SET task_id = NULL WHERE task_id = :tid"), {"tid": bot_id})
            
            # 3. Ürünleri KORU ama bot ile bağını kes
            db.execute(text("UPDATE products SET task_id = NULL WHERE task_id = :tid"), {"tid": bot_id})
            
            db.flush()
        except Exception as e:
            print(f"Bağlı veriler silinirken uyarı (muhtemelen tablo boş): {e}")

        # 4. Botun kendisini sil
        db.delete(task)
        db.commit()
        
        return {"success": True, "message": f"Bot {task_name} ve tüm geçmiş verileri silindi"}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail=f"Bot silinirken bir hata oluştu: {str(e)}"
        )


class BotSettingsUpdate(BaseModel):
    """Bot ayar güncelleme isteği."""
    keyword: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    page_limit: Optional[int] = None
    is_active: Optional[bool] = None


@router.patch("/bots/{bot_id}/settings")
async def update_bot_settings(
    bot_id: int,
    settings: BotSettingsUpdate,
    db: Session = Depends(get_db)
):
    """Bot ayarlarını günceller."""
    from app.models.scraping_task import ScrapingTask
    
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
    
    try:
        if settings.keyword is not None:
            # FIX: Re-assign dict for SQLAlchemy change tracking
            new_params = dict(task.search_params) if task.search_params else {}
            new_params["search_term"] = settings.keyword
            task.search_params = new_params
            
            # Update target_url
            task.target_url = f"https://www.trendyol.com/sr?q={settings.keyword}"
            
            # CRITICAL: Clear existing queue for this task!
            # Otherwise bot continues scraping old keyword's products
            from sqlalchemy import text
            db.execute(
                text("DELETE FROM scraping_queue WHERE task_id = :tid"),
                {"tid": bot_id}
            )
            print(f"Queue cleared for bot {bot_id} due to keyword change.")
        
        if settings.start_time is not None:
            task.start_time = settings.start_time
            
        if settings.end_time is not None:
            task.end_time = settings.end_time

        if settings.page_limit is not None:
            # FIX: Re-assign dict for SQLAlchemy change tracking
            new_params = dict(task.search_params) if task.search_params else {}
            new_params["page_limit"] = settings.page_limit
            task.search_params = new_params
        
        if settings.is_active is not None:
            task.is_active = settings.is_active
            if settings.is_active:
                # Calculate next run more intuitively
                now = datetime.now()
                now_str = now.strftime("%H:%M")
                start = task.start_time or "09:00"
                end = task.end_time or "18:00"
                
                is_in_window = False
                if start < end:
                    is_in_window = start <= now_str < end
                else: 
                    is_in_window = now_str >= start or now_str < end
                
                if is_in_window:
                    # If in window, show it's scheduled for now
                    task.next_run_at = now
                elif now_str < start:
                    # Scheduled for later today
                    h, m = map(int, start.split(":"))
                    task.next_run_at = now.replace(hour=h, minute=m, second=0, microsecond=0)
                else:
                    # Scheduled for tomorrow
                    h, m = map(int, start.split(":"))
                    tomorrow = now + timedelta(days=1)
                    task.next_run_at = tomorrow.replace(hour=h, minute=m, second=0, microsecond=0)
            else:
                task.next_run_at = None
        
        db.commit()
    except Exception as e:
        print(f"Update Error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
    return {"success": True, "message": "Bot ayarları güncellendi"}


@router.get("/logs")
async def get_system_logs(
    limit: int = 100,
    filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Sistem loglarını ve hataları veritabanı ve dosya sisteminden getirir."""
    from app.models.scraping_log import ScrapingLog
    import os
    import glob
    
    # 1. Read actual text logs from file system
    log_messages = []
    try:
        # /Scrapper volume mount check or local fallback
        base_dir = "/Scrapper"
        if not os.path.exists(base_dir):
            base_dir = "Scrapper" # Fallback for local testing
            
        # Find all bot logs
        log_files = glob.glob(os.path.join(base_dir, "bot_*.log"))
        
        all_lines = []
        for log_file in log_files:
            try:
                # Read last N lines from each file
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    # Simple tail implementation
                    lines = f.readlines()
                    all_lines.extend(lines[-limit:]) 
            except Exception as e:
                print(f"Error reading {log_file}: {e}")

        
        # Sort lines by timestamp [HH:MM:SS]
        def extract_timestamp(line):
            try:
                # [14:30:00] ... -> 14:30:00
                if line.startswith('['):
                    return line.split(']')[0].strip('[')
                return "00:00:00"
            except:
                return "00:00:00"
        
        all_lines.sort(key=extract_timestamp)

        # Clean and filter lines
        # Do NOT reverse. We want [Oldest, ..., Newest] so they appear at the bottom of the terminal.
        
        # Filter and limit
        for line in all_lines:
            line = line.strip()
            if not line: continue
            
            # User Request: Only show rich product logs and errors
            # Filter out verbose steps like "Sayfa", "Link", "Kazılıyor"
            if "🛍️" not in line and "❌" not in line:
                continue

            if filter and filter.lower() not in line.lower():
                continue
            log_messages.append(line)
            
        log_messages = log_messages[:limit]
        
    except Exception as e:
        log_messages.append(f"Log okuma hatası: {str(e)}")

    # 2. Get detailed errors from DB as before
    detailed_errors = []
    try:
        from app.models.scraping_task import ScrapingTask
        
        # Join with ScrapingTask to get real bot name
        results = db.query(ScrapingLog, ScrapingTask.task_name).outerjoin(
            ScrapingTask, ScrapingLog.task_id == ScrapingTask.id
        ).filter(ScrapingLog.errors > 0).order_by(ScrapingLog.started_at.desc()).limit(20).all()
        
        for log, t_name in results:
             detailed_errors.append({
                "id": log.id,
                "task_name": t_name or f"Görev {log.task_id}",
                "error": log.error_details or "Hata detayı yok.",
                "screenshot": log.screenshot_path,
                "date": log.started_at.strftime("%d.%m.%Y %H:%M") if log.started_at else ""
            })
    except Exception as e:
        print(f"Error fetching detailed logs: {e}")
            
    return {
        "logs": log_messages,
        "detailed_errors": detailed_errors
    }


@router.get("/logs/backend")
async def get_backend_logs(limit: int = 100):
    """Backend servis loglarını döner."""
    try:
        import os
        log_path = "backend.log"
        if not os.path.exists(log_path):
            return {"logs": ["Henüz backend log kaydı oluşmadı."]}
            
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            # Son N satırı al
            tail_lines = [line.strip() for line in lines[-limit:] if line.strip()]
            return {"logs": tail_lines}
    except Exception as e:
        return {"logs": [f"Backend log okuma hatası: {str(e)}"]}


@router.delete("/logs/errors")
async def clear_error_logs(db: Session = Depends(get_db)):
    """Tüm hata kayıtlarını temizler."""
    try:
        from app.models.scraping_log import ScrapingLog
        import os
        
        # Hatalı logları bul ve sil
        logs = db.query(ScrapingLog).filter(ScrapingLog.errors > 0).all()
        for log in logs:
            # Screenshot varsa sil
            if log.screenshot_path:
                try:
                    # Scrapper/static/captures/filename.png
                    # Biz scraper.py'deyiz (LangChain_backend/app/routers)
                    # Screenshot yolu: ../../../Scrapper/static/captures/
                    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                    project_root = os.path.dirname(backend_root) 
                    ss_path = os.path.join(project_root, "Scrapper", "static", "captures", log.screenshot_path)
                    if os.path.exists(ss_path):
                        os.remove(ss_path)
                except:
                    pass
            db.delete(log)
            
        db.commit()
        return {"success": True, "message": "Tüm hata kayıtları temizlendi"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/logs/{log_id}")
async def delete_log(log_id: int, db: Session = Depends(get_db)):
    """Tekil bir log kaydını siler."""
    try:
        from app.models.scraping_log import ScrapingLog
        import os
        
        log = db.query(ScrapingLog).filter(ScrapingLog.id == log_id).first()
        if not log:
            raise HTTPException(status_code=404, detail="Log bulunamadı")
            
        # Screenshot varsa sil
        if log.screenshot_path:
            try:
                backend_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                project_root = os.path.dirname(backend_root) 
                ss_path = os.path.join(project_root, "Scrapper", "static", "captures", log.screenshot_path)
                if os.path.exists(ss_path):
                    os.remove(ss_path)
            except:
                pass
                
        db.delete(log)
        db.commit()
        return {"success": True, "message": "Log silindi"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/health")
async def get_system_health(db: Session = Depends(get_db)):
    """Sistem sağlığı ve istatistiklerini döner."""
    try:
        from app.models.product import Product
        from app.models.scraping_task import ScrapingTask
        from app.models.scraping_log import ScrapingLog

        # DB Stats - Individual counts to avoid total failure
        total_products = 0
        total_tasks = 0
        total_logs = 0
        db_connection = "healthy"
        
        try:
            total_products = db.query(Product).count()
            total_tasks = db.query(ScrapingTask).count()
            total_logs = db.query(ScrapingLog).count()
        except Exception as db_e:
            logger.error(f"DB STATS ERROR: {db_e}")
            db_connection = "error"
        
        # System Info
        try:
            cpu_usage = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
        except Exception as sys_e:
            logger.error(f"SYSTEM INFO ERROR: {sys_e}")
            cpu_usage = 0
            memory = type('obj', (object,), {'percent': 0, 'used': 0, 'total': 0})
            disk = type('obj', (object,), {'percent': 0, 'used': 0, 'total': 0})

        # Calculate Pulse Status
        pulse_status = "healthy"
        pulse_message = "Sistem Stabil"
        
        try:
            cpu_val = float(cpu_usage)
            mem_val = float(memory.percent)
            
            if db_connection != "healthy":
                pulse_status = "error"
                pulse_message = "Bağlantı Kesik"
            elif cpu_val > 90 or mem_val > 95:
                pulse_status = "critical"
                pulse_message = "Kritik Yük!"
            elif cpu_val > 50 or mem_val > 70:
                pulse_status = "busy"
                pulse_message = "Yük Altında"
        except:
            pass

        return {
            "status": "online" if db_connection == "healthy" else "degraded",
            "pulse": {
                "status": pulse_status,
                "message": pulse_message
            },
            "database": {
                "connection": db_connection,
                "total_products": total_products,
                "total_tasks": total_tasks,
                "total_logs": total_logs
            },
            "server": {
                "cpu": f"{cpu_usage}%",
                "memory": f"{memory.percent}% ({round(memory.used / (1024**3), 2)} GB / {round(memory.total / (1024**3), 2)} GB)",
                "disk": f"{disk.percent}% ({round(disk.used / (1024**3), 2)} GB / {round(disk.total / (1024**3), 2)} GB)",
                "os": platform.system(),
            }
        }
    except Exception as e:
        logger.error(f"HEALTH CHECK CRITICAL ERROR: {e}", exc_info=True)
        return {
            "status": "degraded",
            "database": {
                "connection": f"HATA: {str(e)[:20]}...",
                "total_products": 0,
                "total_tasks": 0,
                "total_logs": 0
            },
            "server": {
                "cpu": "0%",
                "memory": "0%",
                "disk": "0%",
                "os": platform.system(),
                "uptime": "ERR"
            }
        }


@router.get("/live-products")
async def get_live_products(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    try:
        from app.models.product import Product
        from app.models.scraping_task import ScrapingTask
        import traceback
        
        # Son eklenen ürünleri çek (en yeni en üstte)
        # feature_vector gibi ağır/özel tipler hata verebilir, sadece ihtiyacımız olanları seçsek iyi olur ama şimdilik try-except ile görelim.
        products = db.query(Product).order_by(Product.last_scraped_at.desc()).limit(limit).all()
        
        data = []
        
        # Task isimlerini cache'leyelim (N+1 query olmasın)
        task_map = {}
        tasks = db.query(ScrapingTask).all()
        for t in tasks:
            task_map[t.id] = t.task_name
            
        for p in products:
            task_name = task_map.get(p.task_id, "Bilinmeyen Bot")
            
            # Fiyat formatla
            price_val = getattr(p, "last_price", 0) or getattr(p, "price", 0)
            price_display = f"{price_val} TL" if price_val else "Fiyat Yok"
            
            # Resim URL
            image_src = getattr(p, "image_url", None) or (p.image_urls[0] if hasattr(p, "image_urls") and p.image_urls else None)
            
            data.append({
                "id": p.id,
                "name": p.name or "İsimsiz Ürün",
                "brand": p.brand or "Marka Yok",
                "price": price_display,
                "url": p.url,
                "scraped_at": p.last_scraped_at.strftime("%H:%M:%S") if p.last_scraped_at else "--:--:--",
                "bot": task_name,
                "platform": "Trendyol",
                "image": image_src
            })
            
        return data

    except Exception as e:
        print(f"DEBUG ERROR: {str(e)}")
        traceback.print_exc()
        # Geçici olarak hatayı frontend'e/curl'a dönüyoruz
        return [{"id": 0, "name": "Sistem Hatası", "brand": "Hata", "price": "0 TL", "bot": "Sistem", "scraped_at": "00:00", "error": str(e)}]
