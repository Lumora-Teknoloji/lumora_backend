
import os
import sys
import threading
import time
import json
import logging
from datetime import datetime, timezone, timedelta

# --- PATH SETUP ---
from pathlib import Path

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
    # scheduler.py -> services -> app -> LangChain_backend -> (Project Root)
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    
    # Olası Scrapper yolları
    possible_paths = [
        project_root / "Scrapper",
        project_root / "Scrapper-main",
    ]
    
    for path in possible_paths:
        if path.exists() and (path / "main.py").exists():
            return path
            
    # Fallback
    return project_root / "Scrapper"

scrapper_root = get_scrapper_dir()
commands_dir = scrapper_root / "commands"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Scheduler")

# --- DATABASE UTILS (Backend PostgreSQL) ---
def get_db_session():
    """Backend PostgreSQL session kullan."""
    import sys
    # app/services folder
    current_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(os.path.dirname(current_dir))  
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    
    from app.core.database import SessionLocal
    return SessionLocal()

def fetch_tasks():
    """Backend PostgreSQL'den task'ları çek."""
    session = get_db_session()
    try:
        from app.models.scraping_task import ScrapingTask
        tasks = session.query(ScrapingTask).order_by(ScrapingTask.id.asc()).all()
        session.expunge_all()
        return tasks
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        return []
    finally:
        session.close()

# --- BOT MANAGEMENT (File-Based Bridge) ---
def get_bot_status(task_id):
    session = get_db_session()
    try:
        from app.models.agent import Agent
        # Check active agents to see if this task is running
        active_agents = session.query(Agent).filter(
            Agent.is_active == True,
            Agent.status.in_(["busy", "scraping", "active"])
        ).all()
        for a in active_agents:
            if a.current_task and str(task_id) in a.current_task:
                return "running"
        return "stopped"
    finally:
        session.close()

def start_bot(task_id, target_url="", max_pages=0, force=False, mode="normal", source_task_id=None):
    """Publish START command to Agent Command Queue"""
    # URL veya diğer bilgiler eksikse veritabanından çek
    
    # URL veya diğer bilgiler eksikse veritabanından çek
    if not target_url or mode == "normal":
        session = get_db_session()
        try:
            from app.models.scraping_task import ScrapingTask
            task = session.query(ScrapingTask).filter(ScrapingTask.id == task_id).first()
            if task:
                target_url = target_url or task.target_url
                params = task.search_params or {}
                if mode == "normal":
                    mode = params.get("mode", "normal")
                if not source_task_id:
                    source_task_id = params.get("source_task_id")
                if not max_pages or max_pages <= 0:
                    max_pages = params.get("page_limit", 50)
        finally:
            session.close()
            
    if not target_url:
        # Review modu DB'deki ürünleri kullanır — URL gerekmez
        if mode == "review":
            target_url = "review://db-products"
        else:
            # is_active=False olan test task'ları için sadece debug log (her 10s spam önleme)
            log_level = logger.error if task_id else logger.debug
            logger.debug(f"Bot {task_id}: URL bulunamadı, başlatılamıyor (target_url boş)")
            return
        
    try:
        session = get_db_session()
        try:
            from app.models.agent import Agent, AgentCommand
            from datetime import datetime, timedelta, timezone
            
            cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=120)
            active_agents = session.query(Agent).filter(
                Agent.is_active == True,
                Agent.last_heartbeat > cutoff
            ).all()
            
            if active_agents:
                chosen_agent = active_agents[0]
                agent_cmd = AgentCommand(
                    agent_id=chosen_agent.id,
                    command="scrape",
                    params={
                        "keyword": target_url,
                        "mode": mode,
                        "page_limit": max_pages,
                        "task_id": task_id,
                    }
                )
                session.add(agent_cmd)
                session.commit()
                logger.info(f"Scheduled task {task_id} added to agent queue. Agent ID={chosen_agent.id}")
                return True
            else:
                logger.warning(f"No active agents found for scheduled task {task_id}!")
                return False
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Failed to execute linker for bot {task_id}: {e}")
        return False

def stop_bot(task_id, reason="Scheduler"):
    """Publish STOP command to Agent Command Queue"""
    try:
        session = get_db_session()
        try:
            from app.models.agent import Agent, AgentCommand
            active_agents = session.query(Agent).filter(
                Agent.is_active == True,
                Agent.status != "offline"
            ).all()
            for agent in active_agents:
                agent_cmd = AgentCommand(
                    agent_id=agent.id,
                    command="stop",
                    params={"task_id": task_id}
                )
                session.add(agent_cmd)
            session.commit()
            logger.info(f"Command queued: STOP Bot {task_id} ({reason}) to {len(active_agents)} agents")
            return True
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Failed to queue stop command for bot {task_id}: {e}")
        return False

# --- SCHEDULER LOOP ---
def start_scheduler_thread():
    def scheduler_loop():
        logger.info("Scheduler thread started (Safe Path Mode)")
        while True:
            try:
                tasks = fetch_tasks() 
                now = datetime.now()
                now_str = now.strftime("%H:%M")
                
                import zoneinfo
                from datetime import datetime, timedelta, timezone
                tz_ist = zoneinfo.ZoneInfo("Europe/Istanbul")
                
                for task in tasks:
                    status = get_bot_status(task.id)
                    start = task.start_time or "09:00"
                    end = task.end_time or "18:00"
                    
                    force_file = scrapper_root / f"bot_{task.id}.force"
                    is_forced = force_file.exists()

                    # 1. Eğer bot pasifse veya durdurulduysa dokunma
                    if task.status == "stopped" and not is_forced:
                        if status in ["running", "worker_running"]:
                            logger.info(f"Stopping bot {task.id} (Status changed to stopped)")
                            stop_bot(task.id, reason="Task stopped")
                        continue

                    # 2. WORKER veya ACTIVE -> DOKUNMA
                    if status == "worker_running" or task.status == "active":
                        continue

                    if is_forced:
                        continue

                    # 3. Eğer bot "scheduled" ise zamanını kontrol et
                    if task.status == "scheduled":
                        now_dt = datetime.now(tz_ist)
                        # next_run_at utc timezone degilse fix
                        next_run = task.next_run_at
                        if next_run:
                            if next_run.tzinfo is None:
                                next_run = next_run.replace(tzinfo=timezone.utc).astimezone(tz_ist)
                            else:
                                next_run = next_run.astimezone(tz_ist)
                                
                            if now_dt >= next_run:
                                bot_mode = task.search_params.get("mode", "normal") if task.search_params else "normal"
                                page_limit = task.search_params.get("page_limit", 50) if task.search_params else 50
                                src_task_id = task.search_params.get("source_task_id") if task.search_params else None
                                logger.info(f"Starting scheduled bot {task.id} (mode={bot_mode})")
                                
                                keyword = task.target_url
                                if task.search_params and "search_term" in task.search_params:
                                    keyword = keyword or task.search_params.get("search_term")
                                    
                                success = start_bot(task.id, keyword, max_pages=page_limit, mode=bot_mode, source_task_id=src_task_id)
                                
                                if success:
                                    # DB'de status='active' yapip bir sonraki calismayi ayarla
                                    session = get_db_session()
                                    try:
                                        from app.models.scraping_task import ScrapingTask
                                        db_task = session.query(ScrapingTask).filter(ScrapingTask.id == task.id).first()
                                        if db_task:
                                            db_task.last_run_at = datetime.utcnow()
                                            db_task.status = "active"
                                            # Bir sonraki calismayi 24 saat sonraya kur eger interval varsa
                                            interval = db_task.scrape_interval_hours or 24
                                            if interval > 0:
                                                db_task.next_run_at = now_dt + timedelta(hours=interval)
                                            else:
                                                db_task.next_run_at = None
                                            session.commit()
                                    except Exception as dbe:
                                        logger.error(f"Failed to update task {task.id}: {dbe}")
                                    finally:
                                        session.close()

            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
            
            time.sleep(10) # Check every 10s (Faster response)

    thread = threading.Thread(target=scheduler_loop, daemon=True, name="SchedulerThread")
    thread.start()
