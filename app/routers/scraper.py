# app/routers/scraper.py
"""
Scraper API endpoint'leri.
- Task yönetimi
- Veri gönderimi
- Durum sorgulama
"""
from fastapi import APIRouter, Depends, HTTPException
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
    if docker_path.exists() and (docker_path / "main.py").exists():
        return docker_path
    
    # Linux Remote Server
    linux_path = Path("/var/www/scrapper/Scrapper")
    if linux_path.exists(): 
        return linux_path

    # Yerel Windows ortamında
    # scraper.py -> routers -> app -> LangChain_backend -> (Project Root)
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    
    possible_paths = [
        project_root / "Scrapper",
        project_root / "Scrapper-main",
    ]
    
    for path in possible_paths:
        if path.exists() and (path / "main.py").exists():
            # Ensure commands directory exists
            commands_dir = path / "commands"
            try:
                commands_dir.mkdir(parents=True, exist_ok=True)
            except:
                pass
            return path
        
    # Fallback
    return project_root / "Scrapper"


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
    from datetime import timedelta
    
    try:
        # Build search_params
        params = {"search_term": request.search_term, "mode": request.mode, "page_limit": request.page_limit}
        if request.source_task_id:
            params["source_task_id"] = request.source_task_id
        
        # For worker bots, copy source bot's URL if no keyword given
        target_url = f"https://www.trendyol.com/sr?q={request.search_term}" if request.search_term else ""
        if request.mode == "worker" and request.source_task_id:
            source = db.query(ScrapingTask).filter(ScrapingTask.id == request.source_task_id).first()
            if source:
                base_url = source.target_url or target_url
                # Append worker identifier to avoid unique constraint on target_url
                import time
                target_url = f"{base_url}&worker={int(time.time())}"
        
        # Create new task with frontend fields
        new_task = ScrapingTask(
            task_name=request.task_name,
            target_platform=request.target_platform,
            search_params=params,
            target_url=target_url,
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
        print(f"[CREATE_TASK_ERROR] mode={request.mode} task_name={request.task_name} search_term={request.search_term} source_task_id={getattr(request, 'source_task_id', None)}")
        print(f"[CREATE_TASK_ERROR] Full error: {repr(e)}")
        if "unique" in error_msg.lower() or "duplicate" in error_msg.lower():
            if request.mode == "worker":
                raise HTTPException(status_code=400, detail=f"'{request.task_name}' isimli bir bot zaten mevcut.")
            raise HTTPException(status_code=400, detail=f"'{request.search_term}' araması için zaten bir bot mevcut.")
        raise HTTPException(status_code=500, detail=f"Görev oluşturma hatası: {error_msg}")


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    """Görev detaylarını getirir."""
    task = db.query(ScrapingTask).filter(ScrapingTask.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    
    return TaskResponse(
        id=task.id,
        search_term=task.task_name or "",
        status="active" if task.is_active else "paused",
        task_type=task.target_platform or "trendyol",
        last_scraped_at=task.last_run_at
    )


@router.patch("/tasks/{task_id}/status")
async def update_task_status(
    task_id: int,
    status: str,
    db: Session = Depends(get_db)
):
    """Görev durumunu günceller."""
    task = db.query(ScrapingTask).filter(ScrapingTask.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    
    task.is_active = (status == "active")
    db.commit()
    
    return {"success": True, "task_id": task_id, "new_status": status}


@router.get("/tasks")
async def list_active_tasks(db: Session = Depends(get_db)):
    """Aktif görevleri listeler."""
    tasks = db.query(ScrapingTask).all()
    
    return [
        TaskResponse(
            id=t.id,
            search_term=t.task_name or "",
            status="active" if t.is_active else "paused",
            task_type=t.target_platform or "trendyol",
            last_scraped_at=t.last_run_at
        )
        for t in tasks
    ]



@router.get("/bots/status")
async def get_bots_status(db: Session = Depends(get_db)):
    """Tüm botların durumunu listeler (frontend için)."""
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
        
        # Count products scraped — bot'un o anki oturumunda işlediği ürün sayısı
        try:
            from app.models.product import Product
            bot_mode = task.search_params.get("mode", "normal") if task.search_params else "normal"
            
            if bot_mode == "linker":
                # Linker bot: count total queue items (links found) instead of products
                total_queue = db.execute(
                    text("SELECT COUNT(*) FROM scraping_queue WHERE task_id = :tid"),
                    {"tid": task.id}
                ).scalar() or 0
                scraped_count = total_queue
            else:
                # Worker/Normal: TÜM oturumların toplam (added + updated) sayısı
                # Bot durdurup başlatınca sıfırlanmaz
                result = db.execute(
                    text("""
                        SELECT COALESCE(SUM(COALESCE(products_added, 0) + COALESCE(products_updated, 0)), 0)
                        FROM scraping_logs WHERE task_id = :tid
                    """),
                    {"tid": task.id}
                ).scalar()
                scraped_count = result or 0
                
                if scraped_count == 0:
                    # Hiç log yoksa ürün sayısından göster (fallback)
                    scraped_count = db.query(func.count(Product.id)).filter(Product.task_id == task.id).scalar() or 0
        except Exception as e:
            logger.warning(f"Scraped count error for task {task.id}: {e}")
            scraped_count = 0
        
        # Count errors — aktif oturumdaki hatalar (tüm oturumların toplamı değil)
        error_count = 0
        try:
            # Önce aktif (running) log'a bak
            err_log = db.query(ScrapingLog).filter(
                ScrapingLog.task_id == task.id,
                ScrapingLog.status == "running"
            ).order_by(desc(ScrapingLog.started_at)).first()
            
            if not err_log:
                # Aktif log yoksa en son log'u al
                err_log = db.query(ScrapingLog).filter(
                    ScrapingLog.task_id == task.id
                ).order_by(desc(ScrapingLog.started_at)).first()
            
            if err_log:
                error_count = err_log.errors or 0
        except:
            pass
            
        # Calculate Speed (Items per minute in the last hour)
        try:
            from datetime import timedelta, timezone
            now_aware = datetime.now(timezone.utc)
            one_hour_ago = now_aware - timedelta(hours=1)
            
            if bot_mode == "linker":
                # Linker: count recently added queue items
                try:
                    recent_count = db.execute(
                        text("SELECT COUNT(*) FROM scraping_queue WHERE task_id = :tid AND created_at >= :since"),
                        {"tid": task.id, "since": one_hour_ago}
                    ).scalar() or 0
                except:
                    db.rollback()
                    recent_count = 0
            else:
                recent_count_query = db.query(func.count(Product.id)).filter(
                    Product.task_id == task.id,
                    Product.last_scraped_at >= one_hour_ago
                )
                recent_count = recent_count_query.scalar() or 0
            # Speed = Items / 60 mins (average over last hour)
            speed = round(recent_count / 60, 1) if recent_count > 0 else 0
        except Exception as e:
            logger.warning(f"Speed calc error for task {task.id}: {e}")
            speed = 0
        
        # Count pending links in queue
        # For worker bots, show SOURCE linker's queue count
        queue_task_id = task.id
        bot_mode = task.search_params.get("mode", "normal") if task.search_params else "normal"
        if bot_mode == "worker" and task.search_params and task.search_params.get("source_task_id"):
            queue_task_id = task.search_params["source_task_id"]
        try:
            pending_count = db.execute(
                text("SELECT COUNT(*) FROM scraping_queue WHERE task_id = :tid AND status = 'pending'"),
                {"tid": queue_task_id}
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

        # For worker bots, get source bot name
        source_task_id = task.search_params.get("source_task_id") if task.search_params else None
        source_bot_name = None
        if source_task_id:
            try:
                source_task = db.query(ScrapingTask).filter(ScrapingTask.id == source_task_id).first()
                source_bot_name = source_task.task_name if source_task else None
            except:
                pass
        # Get pages_scraped for all bot modes (live progress tracking)
        pages_scraped = 0
        try:
            active_log = db.query(ScrapingLog).filter(
                ScrapingLog.task_id == task.id,
                ScrapingLog.status == "running"
            ).order_by(desc(ScrapingLog.started_at)).first()
            if active_log and active_log.pages_scraped:
                pages_scraped = active_log.pages_scraped
            elif not active_log:
                # Bot çalışmıyorsa en son logu al
                last_finished_log = db.query(ScrapingLog).filter(
                    ScrapingLog.task_id == task.id
                ).order_by(desc(ScrapingLog.started_at)).first()
                if last_finished_log and last_finished_log.pages_scraped:
                    pages_scraped = last_finished_log.pages_scraped
        except:
            pass
        # Derive bot_state from active log's [STATE:xxx] or [STATE:xxx:seconds] prefix
        bot_state = "idle"
        state_message = ""
        state_countdown = 0
        state_started_at = None
        if actual_status in ["running", "worker_running"]:
            bot_state = "scraping"  # Default when running
            try:
                active_log = db.query(ScrapingLog).filter(
                    ScrapingLog.task_id == task.id,
                    ScrapingLog.status == "running"
                ).order_by(desc(ScrapingLog.started_at)).first()
                
                if active_log:
                    msg = active_log.last_message or ""
                    
                    # Critical override
                    if active_log.is_critical:
                        bot_state = "critical"
                        state_message = msg
                    # Parse [STATE:xxx] or [STATE:xxx:seconds] prefix
                    elif msg.startswith("[STATE:"):
                        end_idx = msg.index("]")
                        state_part = msg[7:end_idx]  # e.g. "waiting_ip:45" or "waiting_ip"
                        parts = state_part.split(":")
                        bot_state = parts[0]
                        if len(parts) > 1:
                            try:
                                state_countdown = int(parts[1])
                            except:
                                pass
                        state_message = msg[end_idx+2:] if len(msg) > end_idx+1 else ""
                        # last_seen = when the bot wrote this message
                        if active_log.last_seen:
                            state_started_at = active_log.last_seen.isoformat()
                    else:
                        bot_state = "scraping"
                        state_message = msg
            except:
                pass
        # Uptime (çalışma süresi — aktif log'un başlangıcından bu ana)
        uptime_seconds = 0
        session_started_at = None
        try:
            if actual_status in ["running", "worker_running"]:
                # Çalışıyor — aktif log'dan canlı hesapla
                uptime_log = db.query(ScrapingLog).filter(
                    ScrapingLog.task_id == task.id,
                    ScrapingLog.status == "running"
                ).order_by(desc(ScrapingLog.started_at)).first()
                
                if uptime_log and uptime_log.started_at:
                    started = uptime_log.started_at
                    if started.tzinfo is None:
                        started = started.replace(tzinfo=timezone.utc)
                    now_utc = datetime.now(timezone.utc)
                    uptime_seconds = int((now_utc - started).total_seconds())
                    session_started_at = started.isoformat()
            else:
                # Durdurulmuş — son oturumun toplam süresini göster (sabit)
                last_log = db.query(ScrapingLog).filter(
                    ScrapingLog.task_id == task.id
                ).order_by(desc(ScrapingLog.started_at)).first()
                
                if last_log and last_log.started_at:
                    started = last_log.started_at
                    if started.tzinfo is None:
                        started = started.replace(tzinfo=timezone.utc)
                    # Log bitmişse finished_at, bitmemişse şimdiki zaman
                    if last_log.finished_at:
                        ended = last_log.finished_at
                        if ended.tzinfo is None:
                            ended = ended.replace(tzinfo=timezone.utc)
                    else:
                        ended = datetime.now(timezone.utc)
                    uptime_seconds = int((ended - started).total_seconds())
                    session_started_at = started.isoformat()
        except:
            pass

        bot = {
            "id": task.id,
            "name": task.task_name or "Unnamed Bot",
            "platform": task.target_platform or "Trendyol",
            "status": actual_status,
            "keyword": task.search_params.get("search_term", "") if task.search_params else "",
            "mode": task.search_params.get("mode", "normal") if task.search_params else "normal",
            "source_task_id": source_task_id,
            "source_bot_name": source_bot_name,
            "start_time": task.start_time or "09:00",
            "end_time": task.end_time or "18:00",
            "page_limit": task.search_params.get("page_limit", 24) if task.search_params else 24,
            "is_active": task.is_active,
            "pending_links": pending_count,
            "pages_scraped": pages_scraped,
            "bot_state": bot_state,
            "state_message": state_message,
            "state_countdown": state_countdown,
            "state_started_at": state_started_at,
            "uptime_seconds": uptime_seconds,
            "session_started_at": session_started_at,
            "stats": {
                "scraped": scraped_count,
                "validated": speed,
                "errors": error_count,
                "processed": ip_change_count
            },
            "last_message": last_msg,
            "last_product_url": last_url,
            "use_proxy": task.search_params.get("use_proxy", False) if task.search_params else False
        }
        bots.append(bot)
    
    return bots


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


# ==================== BOT CONTROL ENDPOINTS ====================


@router.get("/bots/linkers")
async def get_linker_bots(db: Session = Depends(get_db)):
    """Linker botlarını listeler (Worker oluştururken kaynak seçimi için)."""
    from app.models.scraping_task import ScrapingTask
    from sqlalchemy import text
    
    tasks = db.query(ScrapingTask).all()
    linkers = []
    for task in tasks:
        mode = task.search_params.get("mode", "normal") if task.search_params else "normal"
        if mode == "linker":
            # Count queue items for this linker
            try:
                queue_count = db.execute(
                    text("SELECT COUNT(*) FROM scraping_queue WHERE task_id = :tid"),
                    {"tid": task.id}
                ).scalar() or 0
            except:
                queue_count = 0
            
            keyword = task.search_params.get("search_term", "") if task.search_params else ""
            linkers.append({
                "id": task.id,
                "name": task.task_name,
                "keyword": keyword,
                "queue_count": queue_count
            })
    
    return linkers

@router.post("/bots/{bot_id}/start")
async def start_bot(bot_id: int, db: Session = Depends(get_db)):
    """Botu başlatır - hem dosya tabanlı (eski) hem agent command queue (yeni) sistemi."""
    from app.models.scraping_task import ScrapingTask
    from app.models.agent import Agent, AgentCommand
    import json, os
    
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
    
    # Activate in database
    task.is_active = True
    db.commit()
    
    # Read mode from search_params (linker/worker/normal)
    bot_mode = "normal"
    if task.search_params and task.search_params.get("mode"):
        bot_mode = task.search_params["mode"]
    
    keyword = task.search_params.get("search_term", "") if task.search_params else ""
    max_pages = task.search_params.get("page_limit", 50) if task.search_params else 50
    
    # Get source_task_id for worker bots
    source_task_id = None
    if task.search_params and task.search_params.get("source_task_id"):
        source_task_id = task.search_params["source_task_id"]
    
    cmd_data = {
        "type": "START",
        "task_id": bot_id,
        "target_url": task.target_url,
        "task_name": task.task_name,
        "max_pages": max_pages,
        "mode": bot_mode,
        "force": True
    }
    if source_task_id:
        cmd_data["source_task_id"] = source_task_id

    # ── YENİ: Agent Command Queue (agent.py heartbeat ile alır) ──────────
    try:
        active_agents = db.query(Agent).filter(
            Agent.is_active == True,
            Agent.status != "offline"
        ).all()
        for agent in active_agents:
            agent_cmd = AgentCommand(
                agent_id=agent.id,
                command="scrape",
                params={
                    "keyword": keyword,
                    "mode": bot_mode,
                    "max_pages": max_pages,
                    "task_id": bot_id,
                }
            )
            db.add(agent_cmd)
        db.commit()
        logger.info(f"Agent command queue'ya eklendi: {len(active_agents)} agent")
    except Exception as e:
        logger.warning(f"Agent queue yazılamadı (eski sistem devreye girecek): {e}")

    # ── ESKİ: Dosya tabanlı komut sistemi (geriye uyumluluk) ─────────────
    try:
        scrapper_dir = get_scrapper_dir()
        commands_dir = scrapper_dir / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        cmd_file = commands_dir / f"start_{bot_id}.json"
        with open(cmd_file, "w") as f:
            json.dump(cmd_data, f)
        force_file = scrapper_dir / f"bot_{bot_id}.force"
        force_file.write_text("1")
    except Exception as e:
        logger.warning(f"Komut dosyası yazılamadı: {e}")
    
    return {"success": True, "message": f"Bot {task.task_name} başlatma komutu gönderildi"}


@router.post("/bots/{bot_id}/worker")
async def worker_start_bot(bot_id: int, db: Session = Depends(get_db)):
    """Botu sadece kuyruk eritme (worker) modunda başlatır."""
    from app.models.scraping_task import ScrapingTask
    from app.models.agent import Agent, AgentCommand
    import json, os
    
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
    
    # Review botları için özel handling: WORKER → review_dom moduna çevir
    bot_mode = task.search_params.get("mode", "normal") if task.search_params else "normal"
    is_review_bot = bot_mode == "review"

    keyword = task.search_params.get("search_term", "") if task.search_params else ""
    source_task_id = None
    if task.search_params and task.search_params.get("source_task_id"):
        source_task_id = task.search_params["source_task_id"]

    # ── YENİ: Agent Command Queue ─────────────────────────────────────────
    try:
        active_agents = db.query(Agent).filter(
            Agent.is_active == True,
            Agent.status != "offline"
        ).all()
        for agent in active_agents:
            agent_cmd = AgentCommand(
                agent_id=agent.id,
                command="scrape",
                params={
                    "keyword": keyword,
                    "mode": "review_dom" if is_review_bot else "worker",
                    "max_pages": task.search_params.get("page_limit", 50) if task.search_params else 50,
                    "task_id": bot_id,
                }
            )
            db.add(agent_cmd)
        db.commit()
    except Exception as e:
        logger.warning(f"Agent queue yazılamadı: {e}")

    # ── ESKİ: Dosya tabanlı ───────────────────────────────────────────────
    try:
        scrapper_dir = get_scrapper_dir()
        commands_dir = scrapper_dir / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        
        if is_review_bot:
            # Review bot → review_dom modunda START komutu gönder
            cmd_file = commands_dir / f"start_{bot_id}.json"
            with open(cmd_file, "w") as f:
                json.dump({
                    "type": "START",
                    "task_id": bot_id,
                    "target_url": "review://db-products",
                    "task_name": task.task_name,
                    "mode": "review_dom"
                }, f)
        else:
            cmd_file = commands_dir / f"worker_{bot_id}.json"
            with open(cmd_file, "w") as f:
                json.dump({
                    "type": "WORKER",
                    "task_id": bot_id,
                    "target_url": task.target_url,
                    "task_name": task.task_name,
                    "source_task_id": source_task_id or bot_id,
                    "force": True
                }, f)
    except Exception as e:
        logger.warning(f"Komut dosyası yazılamadı: {e}")
    
    msg = f"Bot {task.task_name} {'DOM yorum kazıma' if is_review_bot else 'kuyruk eritme (worker)'} komutu gönderildi"
    return {"success": True, "message": msg}


@router.post("/bots/{bot_id}/stop")
async def stop_bot(bot_id: int, db: Session = Depends(get_db)):
    """Botu durdurur - hem dosya tabanlı (eski) hem agent command queue (yeni)."""
    from app.models.scraping_task import ScrapingTask
    from app.models.agent import Agent, AgentCommand
    import json, os
    
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
    
    # Deactivate in database and clear schedule
    task.is_active = False
    task.next_run_at = None
    db.commit()

    # ── YENİ: Agent Command Queue ─────────────────────────────────────────
    try:
        active_agents = db.query(Agent).filter(
            Agent.is_active == True,
            Agent.status != "offline"
        ).all()
        for agent in active_agents:
            agent_cmd = AgentCommand(
                agent_id=agent.id,
                command="stop",
                params={"task_id": bot_id}
            )
            db.add(agent_cmd)
        db.commit()
    except Exception as e:
        logger.warning(f"Agent stop queue yazılamadı: {e}")

    # ── ESKİ: Dosya tabanlı ───────────────────────────────────────────────
    try:
        scrapper_dir = get_scrapper_dir()
        commands_dir = scrapper_dir / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        cmd_file = commands_dir / f"stop_{bot_id}.json"
        with open(cmd_file, "w") as f:
            json.dump({"type": "STOP", "task_id": bot_id}, f)
    except Exception as e:
        logger.warning(f"Stop dosyası yazılamadı: {e}")
    
    return {"success": True, "message": f"Bot {task.task_name} durduruldu ve planı temizlendi"}


@router.post("/bots/{bot_id}/speed-mode")
async def toggle_speed_mode(bot_id: int, minutes: int = 30, db: Session = Depends(get_db)):
    """Hız modunu aktif/deaktif eder. Max 30 dakika, sonra otomatik güvenli moda döner."""
    from app.models.scraping_task import ScrapingTask
    import json
    
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
    
    # Max 30 dakika sınırı
    minutes = min(minutes, 30)
    
    # Komut dosyası oluştur (scrapper okuyacak)
    scrapper_dir = get_scrapper_dir()
    commands_dir = scrapper_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    
    cmd_file = commands_dir / f"speed_{bot_id}.json"
    with open(cmd_file, "w") as f:
        json.dump({
            "type": "SPEED_MODE",
            "task_id": bot_id,
            "minutes": minutes
        }, f)
    
    return {
        "success": True, 
        "message": f"⚡ Hız modu {minutes} dakika aktif — {task.task_name}",
        "expires_in_minutes": minutes
    }

@router.post("/bots/{bot_id}/api-mode")
async def toggle_api_mode(bot_id: int, db: Session = Depends(get_db)):
    """API modunu toggle eder (aç/kapat). DOM yerine API-first scraping."""
    from app.models.scraping_task import ScrapingTask
    import json
    
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
    
    # Komut dosyası oluştur (scrapper okuyacak)
    scrapper_dir = get_scrapper_dir()
    commands_dir = scrapper_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    
    cmd_file = commands_dir / f"api_{bot_id}.json"
    with open(cmd_file, "w") as f:
        json.dump({
            "type": "API_MODE",
            "task_id": bot_id,
            "action": "toggle"
        }, f)
    
    return {
        "success": True, 
        "message": f"🔌 API modu toggle edildi — {task.task_name}"
    }

@router.post("/bots/{bot_id}/proxy-mode")
async def toggle_proxy_mode(bot_id: int, db: Session = Depends(get_db)):
    """Proxy modunu toggle eder (aç/kapat). Bright Data residential proxy."""
    from app.models.scraping_task import ScrapingTask
    import json
    
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
    
    # Komut dosyası oluştur (scrapper okuyacak)
    scrapper_dir = get_scrapper_dir()
    commands_dir = scrapper_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    
    cmd_file = commands_dir / f"proxy_{bot_id}.json"
    with open(cmd_file, "w") as f:
        json.dump({
            "type": "PROXY_MODE",
            "task_id": bot_id,
            "action": "toggle"
        }, f)
    
    # search_params'a use_proxy kaydet (sayfa yenilenince korunsun)
    params = task.search_params or {}
    params["use_proxy"] = not params.get("use_proxy", False)
    task.search_params = params
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(task, "search_params")
    db.commit()
    
    status_text = "aktif" if params["use_proxy"] else "deaktif"
    return {
        "success": True, 
        "use_proxy": params["use_proxy"],
        "message": f"🌐 Proxy modu {status_text} — {task.task_name}"
    }

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
        
        # 0. Çalışıyorsa ÖNCE durdur (orphan process önleme)
        scrapper_dir = get_scrapper_dir()
        pid_file = scrapper_dir / f"bot_{bot_id}.pid"
        stop_file = scrapper_dir / f"bot_{bot_id}.stop"
        
        if pid_file.exists():
            # Stop sinyali gönder
            stop_file.write_text("1")
            try:
                pid = int(pid_file.read_text().strip())
                import subprocess as sp
                if os.name == 'nt':
                    sp.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=10)
                else:
                    import signal as sig
                    os.kill(pid, sig.SIGKILL)
            except:
                pass
            # Dosyaları temizle
            for f in [pid_file, stop_file, scrapper_dir / f"bot_{bot_id}.force", scrapper_dir / f"bot_{bot_id}.worker"]:
                try:
                    if f.exists(): f.unlink()
                except:
                    pass
        
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
            logger.warning(f"Bağlı veriler silinirken uyarı: {e}")

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
            logger.info(f"Queue cleared for bot {bot_id} due to keyword change.")
        
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
        logger.error(f"Bot settings update error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
    return {"success": True, "message": "Bot ayarları güncellendi"}


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
            except:
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
                ss_path = os.path.join(str(get_scrapper_dir()), "static", "captures", log.screenshot_path)
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
        logger.error(f"Live products error: {str(e)}")
        traceback.print_exc()
        return [{"id": 0, "name": "Sistem Hatası", "brand": "Hata", "price": "0 TL", "bot": "Sistem", "scraped_at": "00:00", "error": str(e)}]


# ==================== MONITORING ====================

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
