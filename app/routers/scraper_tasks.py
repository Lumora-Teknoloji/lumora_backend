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
    if docker_path.exists() and (docker_path / "main.py").exists():
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
        if path.exists() and (path / "main.py").exists():
            return path
        
    # Fallback
    return project_root / "Scrapper"

# ==================== ENDPOINTS ====================

@router.post("/tasks", response_model=TaskResponse)
async def create_scraping_task(
    request: CreateTaskRequest,
    background_tasks: BackgroundTasks,
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
                import time
                target_url = f"{base_url}&worker={int(time.time())}"
        
        # Create new task
        new_task = ScrapingTask(
            task_name=request.task_name,
            target_platform=request.target_platform,
            search_params=params,
            target_url=target_url,
            scrape_interval_hours=request.scrape_interval,
            is_active=request.is_active,
            status="active" if request.is_active else "stopped",
            start_time=request.start_time,
            end_time=request.end_time,
            next_run_at=datetime.now() + timedelta(hours=request.scrape_interval) if request.is_active else None
        )
        
        db.add(new_task)
        db.commit()
        db.refresh(new_task)
        
        # YENI: Eger is_active ise aninda tetikle (Immediate Run on Create)
        if request.is_active and request.search_term:
            from app.models.agent import Agent, AgentCommand
            try:
                active_agents = db.query(Agent).filter(
                    Agent.is_active == True,
                    Agent.status != "offline"
                ).all()
                if active_agents:
                    agent_cmd = AgentCommand(
                        agent_id=active_agents[0].id,
                        command="scrape",
                        params={
                            "keyword": request.search_term,
                            "mode": request.mode,
                            "page_limit": request.page_limit,
                            "task_id": new_task.id,
                        }
                    )
                    db.add(agent_cmd)
                    db.commit()
                    logger.info(f"Agent command queue'ya eklendi: Yeni gorev: {request.search_term}")
            except Exception as e:
                logger.error(f"Agent command trigger hatası: {e}")
        
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
        status=task.status if task.status else ("active" if task.is_active else "stopped"),
        task_type=task.target_platform or "trendyol",
        last_scraped_at=task.last_run_at
    )

@router.patch("/tasks/{task_id}/status")
async def update_task_status(
    task_id: int,
    status: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Görev durumunu günceller ve eğer başlatılıyorsa anlık tetikler."""
    task = db.query(ScrapingTask).filter(ScrapingTask.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    
    task.is_active = (status == "active")
    task.status = "active" if status == "active" else "stopped"
    db.commit()
    
    # Eger Play tusuna (active) basildiysa aninda tetikle
    if task.is_active:
        keyword = task.target_url
        if task.search_params and "search_term" in task.search_params:
            keyword = keyword or task.search_params.get("search_term")
            
        page_limit = task.search_params.get("page_limit", 50) if task.search_params else 50
        
        if keyword:
            from app.models.agent import Agent, AgentCommand
            try:
                from datetime import datetime, timedelta
                cutoff = datetime.now(timezone.utc) - timedelta(seconds=120)
                active_agents = db.query(Agent).filter(
                    Agent.is_active == True,
                    Agent.status != "offline",
                    Agent.last_heartbeat > cutoff
                ).all()
                if active_agents:
                    agent_cmd = AgentCommand(
                        agent_id=active_agents[0].id,
                        command="scrape",
                        params={
                            "keyword": keyword,
                            "mode": "normal",
                            "page_limit": page_limit,
                            "task_id": task_id,
                        }
                    )
                    db.add(agent_cmd)
                    db.commit()
            except Exception as e:
                logger.error(f"Agent command trigger hatası: {e}")
    
    return {"success": True, "task_id": task_id, "new_status": status}

@router.get("/tasks")
async def list_active_tasks(db: Session = Depends(get_db)):
    """Aktif görevleri listeler."""
    tasks = db.query(ScrapingTask).all()
    
    return [
        TaskResponse(
            id=t.id,
            search_term=t.task_name or "",
            status=t.status if t.status else ("active" if t.is_active else "stopped"),
            task_type=t.target_platform or "trendyol",
            last_scraped_at=t.last_run_at
        )
        for t in tasks
    ]

@router.delete("/tasks/{bot_id}")
async def delete_bot(bot_id: int, db: Session = Depends(get_db)):
    """Botu ve onunla ilişkili tüm verileri siler."""
    from app.models.scraping_task import ScrapingTask
    from sqlalchemy import text
    
    try:
        task = db.query(ScrapingTask).filter(ScrapingTask.id == bot_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Bot bulunamadı")
        
        task_name = task.task_name

        # Agent'lara cancel komutu gönder (aktif kazıma varsa iptal etsin)
        try:
            from app.models.agent import Agent, AgentCommand
            active_agents = db.query(Agent).filter(
                Agent.is_active == True,
                Agent.status != "offline"
            ).all()
            for agent in active_agents:
                agent_cmd = AgentCommand(
                    agent_id=agent.id,
                    command="cancel",
                    params={"task_id": bot_id}
                )
                db.add(agent_cmd)
            if active_agents:
                db.commit()
        except Exception as e:
            logger.warning(f"Delete sırasında agent cancel gönderilemedi: {e}")
        
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
            except Exception:
                pass
            # Dosyaları temizle
            for f in [pid_file, stop_file, scrapper_dir / f"bot_{bot_id}.force", scrapper_dir / f"bot_{bot_id}.worker"]:
                try:
                    if f.exists(): f.unlink()
                except Exception:
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