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

@router.get("/status", response_model=StatusResponse)
async def get_scraper_status(db: Session = Depends(get_db)):
    """Genel scraper durumunu döner."""
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
    from datetime import time
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

@router.get("/logs")
async def get_system_logs(
    limit: int = 100,
    filter: Optional[str] = None,
    bot_id: int = 0,
    db: Session = Depends(get_db)
):
    """Sistem loglarını ve hataları veritabanı ve dosya sisteminden getirir."""
    from app.models.scraping_log import ScrapingLog
    import os
    import glob
    
    # 1. Read actual text logs from file system
    log_messages = []
    try:
        # Use centralized path resolution
        base_dir = str(get_scrapper_dir())
            
        # Find bot log files — filter by bot_id if specified
        if bot_id > 0:
            log_files = [os.path.join(base_dir, f"bot_{bot_id}.log")]
            log_files = [f for f in log_files if os.path.exists(f)]
        else:
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
            except Exception:
                return "00:00:00"
        
        all_lines.sort(key=extract_timestamp)

        # Clean and filter lines
        # Do NOT reverse. We want [Oldest, ..., Newest] so they appear at the bottom of the terminal.
        
        # Filter and limit
        for line in all_lines:
            line = line.strip()
            if not line: continue
            
            # Show meaningful logs from all bot types:
            # 🛍️ Product scraped, ❌ Error, 🔗 Link found (Linker)
            # 📡 Linker status, 🔍 Worker status, 🏁 Finished
            # ⚠️ Warning, 🔄 IP rotation, 🛑 Stop signal
            meaningful_emojis = ["🛍️", "❌", "🔗", "📡", "🔍", "🏁", "⚠️", "🔄", "🛑"]
            if not any(emoji in line for emoji in meaningful_emojis):
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
        
        # Join with ScrapingTask to get real bot name + mode
        results = db.query(ScrapingLog, ScrapingTask.task_name, ScrapingTask.search_params).outerjoin(
            ScrapingTask, ScrapingLog.task_id == ScrapingTask.id
        ).filter(ScrapingLog.errors > 0).order_by(ScrapingLog.started_at.desc()).limit(20).all()
        
        for log, t_name, s_params in results:
             bot_mode = s_params.get("mode", "normal") if s_params else "normal"
             detailed_errors.append({
                "id": log.id,
                "task_name": t_name or f"Görev {log.task_id}",
                "mode": bot_mode,
                "error": log.error_details or "Hata detayı yok.",
                "screenshot": log.screenshot_path,
                "date": log.started_at.strftime("%d.%m.%Y %H:%M") if log.started_at else ""
            })
    except Exception as e:
        logger.error(f"Error fetching detailed logs: {e}")
            
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
                    ss_path = os.path.join(str(get_scrapper_dir()), "static", "captures", log.screenshot_path)
                    if os.path.exists(ss_path):
                        os.remove(ss_path)
                except Exception:
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
                ss_path = os.path.join(str(get_scrapper_dir()), "static", "captures", log.screenshot_path)
                if os.path.exists(ss_path):
                    os.remove(ss_path)
            except Exception:
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
        except Exception:
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
        logger.error(f"Live products error: {str(e)}")
        traceback.print_exc()
        return [{"id": 0, "name": "Sistem Hatası", "brand": "Hata", "price": "0 TL", "bot": "Sistem", "scraped_at": "00:00", "error": str(e)}]

@router.get("/monitor/check")
async def monitor_check(db: Session = Depends(get_db)):
    """
    Scraper sağlık kontrolü — veri akışı durunca webhook ile bildirim gönderir.
    Bu endpoint'i bir cron job ile çağırabilirsin (her 30dk'da bir).
    """
    from app.core.config import settings
    import httpx
    
    threshold = settings.alert_threshold_minutes
    
    # Son veri ne zaman geldi?
    latest = db.query(func.max(Product.last_scraped_at)).scalar()
    
    if not latest:
        return {"status": "no_data", "message": "Veritabanında hiç veri yok"}
    
    # Make timezone aware for comparison
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    
    now = datetime.now(timezone.utc)
    minutes_since = (now - latest).total_seconds() / 60
    
    status_data = {
        "status": "healthy" if minutes_since < threshold else "stale",
        "last_data_at": latest.isoformat(),
        "minutes_since_last_data": round(minutes_since, 1),
        "threshold_minutes": threshold,
    }
    
    # Alert if stale
    if minutes_since >= threshold and settings.webhook_url:
        try:
            message = (
                f"⚠️ SCRAPER ALERT\n"
                f"Son veri: {round(minutes_since)} dakika önce\n"
                f"Eşik: {threshold} dakika\n"
                f"Kontrol edin!"
            )
            async with httpx.AsyncClient() as client:
                # Discord webhook format
                if "discord" in settings.webhook_url:
                    await client.post(settings.webhook_url, json={"content": message})
                # Telegram bot format
                elif "telegram" in settings.webhook_url:
                    await client.post(settings.webhook_url, json={"text": message})
                else:
                    await client.post(settings.webhook_url, json={"message": message})
            
            status_data["alert_sent"] = True
        except Exception as e:
            logger.error(f"Webhook alert error: {e}")
            status_data["alert_error"] = str(e)
    
    return status_data