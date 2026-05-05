from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
import logging

from app.core.database import get_db
from app.models.scraping_task import ScrapingTask
from app.models.agent import Agent, AgentCommand
from app.schemas.scraper import (
    ScrapedProduct, IngestRequest, IngestResponse,
    CreateTaskRequest, TaskResponse, StatusResponse,
    BotStatusResponse, BotSettingsUpdate
)
from app.services.data.bot_manager import (
    get_bots_status_list,
    start_bot_process,
    stop_bot_process,
    cancel_bot_process,
    toggle_bot_mode
)

logger = logging.getLogger(__name__)
from app.middleware.rate_limit import limiter
router = APIRouter(prefix="/scraper", tags=["Scraper"])

# ==================== ENDPOINTS ====================

@router.get("/bots/status")
async def get_bots_status(db: Session = Depends(get_db)):
    """Tüm botların durumunu listeler (frontend için)."""
    return await get_bots_status_list(db)

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
            except Exception:
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
async def start_bot(request: Request, bot_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Botu başlatır - hem dosya tabanlı (eski) hem agent command queue (yeni) sistemi."""
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
        
    start_bot_process(bot_id, task, background_tasks, db)
    return {"success": True, "message": f"Bot {task.task_name} başlatma komutu gönderildi"}

@router.post("/bots/{bot_id}/worker")
async def worker_start_bot(request: Request, bot_id: int, db: Session = Depends(get_db)):
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
        from datetime import datetime, timedelta
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=120)
        active_agents = db.query(Agent).filter(
            Agent.is_active == True,
            Agent.status != "offline",
            Agent.last_heartbeat > cutoff
        ).all()
        for agent in active_agents:
            agent_cmd = AgentCommand(
                agent_id=agent.id,
                command="scrape",
                params={
                    "keyword": keyword,
                    "mode": "review_api" if is_review_bot else "worker",
                    "max_pages": task.search_params.get("page_limit", 50) if task.search_params else 50,
                    "task_id": bot_id,
                }
            )
            db.add(agent_cmd)
        db.commit()
    except Exception as e:
        logger.warning(f"Agent queue yazılamadı: {e}")

    msg = f"Bot {task.task_name} {'API yorum kazıma' if is_review_bot else 'kuyruk eritme (worker)'} komutu gönderildi"
    return {"success": True, "message": msg}

@router.post("/bots/{bot_id}/stop")
async def stop_bot(request: Request, bot_id: int, db: Session = Depends(get_db)):
    """Botu durdurur - hem dosya tabanlı (eski) hem agent command queue (yeni)."""
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
        
    stop_bot_process(bot_id, task, db)
    return {"success": True, "message": f"Bot {task.task_name} durduruldu ve planı temizlendi"}


@router.post("/bots/{bot_id}/complete")
async def complete_bot_task(request: Request, bot_id: int, db: Session = Depends(get_db)):
    """Linker görevi tamamlandığında çağrılır.
    Görevi 'scheduled' durumuna döndürür ve bir sonraki çalışma zamanını hesaplar.
    /stop'dan farkı: Bu endpoint görevi durdurmaz, sadece 'tamamlandı' sinyali verir."""
    from app.models.scraping_task import ScrapingTask
    import datetime
    
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamıdı")
    
    # Görev zamanlanmışsa (recurring), scheduled'a dön
    interval = task.scrape_interval_hours or 0
    
    if task.start_time and interval > 0:
        task.status = "scheduled"
        task.is_active = True
        task.last_run_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        
        # Bir sonraki çalışma zamanını hesapla
        try:
            time_parts = [int(p) for p in task.start_time.split(":")]
            now = datetime.datetime.now(datetime.timezone.utc)
            start_dt = now.replace(hour=time_parts[0], minute=time_parts[1], second=0, microsecond=0)
            if start_dt <= now:
                start_dt = start_dt + datetime.timedelta(days=1)
            task.next_run_at = start_dt
        except Exception:
            task.next_run_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=interval)
        
        logger.info(f"✅ Görev {bot_id} ({task.task_name}) tamamlandı → scheduled (next: {task.next_run_at})")
    else:
        # Tek seferlik görev: durdur
        task.status = "stopped"
        task.is_active = False
        task.next_run_at = None
        task.last_run_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        logger.info(f"✅ Görev {bot_id} ({task.task_name}) tamamlandı → stopped (tek seferlik)")
    
    db.commit()
    return {"success": True, "message": f"Görev {task.task_name} tamamlandı", "new_status": task.status}

@router.post("/bots/{bot_id}/reset")
async def reset_bot_stats(request: Request, bot_id: int, db: Session = Depends(get_db)):
    """Bot'un kazıma loglarını, bekleyen link kuyruğunu siler ve topladığı ürünlerin bağını kopararak sıfırlar."""
    from app.models.scraping_task import ScrapingTask
    from sqlalchemy import text
    
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
        
    db.execute(text("DELETE FROM scraping_logs WHERE task_id = :tid"), {"tid": bot_id})
    db.execute(text("DELETE FROM scraping_queue WHERE task_id = :tid"), {"tid": bot_id})
    db.execute(text("UPDATE products SET task_id = NULL WHERE task_id = :tid"), {"tid": bot_id})
    db.commit()
    
    return {"success": True, "message": f"{task.task_name} istatistikleri sıfırlandı."}

@router.post("/bots/{bot_id}/schedule")
async def schedule_bot(request: Request, bot_id: int, db: Session = Depends(get_db)):
    """Botu planlanmış duruma geçirir."""
    from app.models.scraping_task import ScrapingTask
    import datetime
    
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
    
    task.is_active = True
    task.status = "scheduled"
    
    # Calculate next_run_at based on start_time if available
    time_val = task.start_time or "09:00"
    try:
        time_parts = [int(p) for p in time_val.split(":")]
        now = datetime.datetime.now(datetime.timezone.utc)
        start_dt = now.replace(hour=time_parts[0], minute=time_parts[1], second=0, microsecond=0)
        if start_dt < now:
            start_dt = start_dt + datetime.timedelta(days=1)
        task.next_run_at = start_dt
    except Exception:
        pass
        
    db.commit()
    return {"success": True, "message": f"Bot {task.task_name} planlandı (Beklemede)"}

@router.post("/bots/{bot_id}/cancel")
async def cancel_bot(bot_id: int, db: Session = Depends(get_db)):
    """Botu iptal eder — aktif kazımayı durdurur, yarım kalan veriyi sync eder."""
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
        
    cancel_bot_process(bot_id, task, db)
    return {"success": True, "message": f"Bot {task.task_name} iptal edildi"}

@router.post("/bots/{bot_id}/speed-mode")
async def toggle_speed_mode(bot_id: int, minutes: int = 30, db: Session = Depends(get_db)):
    """Hız modunu aktif/deaktif eder. Max 30 dakika, sonra otomatik güvenli moda döner."""
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
        
    minutes = min(minutes, 30)
    toggle_bot_mode(bot_id, "SPEED_MODE", {"minutes": minutes})
    
    return {
        "success": True, 
        "message": f"⚡ Hız modu {minutes} dakika aktif — {task.task_name}",
        "expires_in_minutes": minutes
    }

@router.post("/bots/{bot_id}/api-mode")
async def toggle_api_mode(bot_id: int, db: Session = Depends(get_db)):
    """API modunu toggle eder (aç/kapat). DOM yerine API-first scraping."""
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
        
    toggle_bot_mode(bot_id, "API_MODE", {"action": "toggle"})
    
    return {
        "success": True, 
        "message": f"🔌 API modu toggle edildi — {task.task_name}"
    }

@router.post("/bots/{bot_id}/proxy-mode")
async def toggle_proxy_mode(bot_id: int, db: Session = Depends(get_db)):
    """Proxy modunu toggle eder (aç/kapat)."""
    task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Bot bulunamadı")
        
    toggle_bot_mode(bot_id, "PROXY_MODE", {"action": "toggle"})
    
    params = task.search_params or {}
    params["use_proxy"] = not params.get("use_proxy", False)
    task.search_params = params
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(task, "search_params")
    db.commit()
    
    status_text = "aktif" if params["use_proxy"] else "deaktif"
    return {
        "success": True, 
        "message": f"🌐 Proxy modu {status_text} — {task.task_name}"
    }

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