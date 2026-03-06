
import os
import sys
import threading
import time
import json
import logging
from datetime import datetime

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
    pid_file = scrapper_root / f"bot_{task_id}.pid"
    worker_marker = scrapper_root / f"bot_{task_id}.worker"
    
    # logger.info(f"Checking status for bot {task_id}: {pid_file} (Exists: {pid_file.exists()})")
    
    if pid_file.exists():
        if worker_marker.exists():
            return "worker_running"
        return "running"
    return "stopped"

def start_bot(task_id, target_url="", max_pages=0, force=False, mode="normal", source_task_id=None):
    """Write START command to file bridge"""
    current_status = get_bot_status(task_id)
    if current_status in ["running", "worker_running"]:
        return
    
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
        logger.error(f"Cannot start bot {task_id}: No URL found")
        return
        
    try:
        commands_dir.mkdir(parents=True, exist_ok=True)
        
        # Worker modu için ayrı komut dosyası
        if mode == "worker":
            cmd_file = commands_dir / f"worker_{task_id}.json"
            cmd_data = {
                "type": "WORKER",
                "task_id": task_id,
                "target_url": target_url,
                "source_task_id": source_task_id or task_id,
                "force": force
            }
        else:
            cmd_file = commands_dir / f"start_{task_id}.json"
            cmd_data = {
                "type": "START",
                "task_id": task_id,
                "target_url": target_url,
                "max_pages": max_pages,
                "mode": mode,
                "force": force
            }
            if source_task_id:
                cmd_data["source_task_id"] = source_task_id
        
        with open(cmd_file, "w") as f:
            json.dump(cmd_data, f)
            
        logger.info(f"Command queued: {'WORKER' if mode == 'worker' else 'START'} Bot {task_id} (mode={mode})")
        return True
    except Exception as e:
        logger.error(f"Failed to queue start command for bot {task_id}: {e}")
        return False

def stop_bot(task_id, reason="Scheduler"):
    """Write STOP command to file bridge"""
    try:
        commands_dir.mkdir(parents=True, exist_ok=True)
        cmd_file = commands_dir / f"stop_{task_id}.json"
        
        with open(cmd_file, "w") as f:
            json.dump({
                "type": "STOP",
                "task_id": task_id,
                "reason": reason
            }, f)
            
        logger.info(f"Command queued: STOP Bot {task_id} ({reason})")
        return True
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
                
                for task in tasks:
                    status = get_bot_status(task.id)
                    start = task.start_time or "09:00"
                    end = task.end_time or "18:00"
                    
                    force_file = scrapper_root / f"bot_{task.id}.force"
                    is_forced = force_file.exists()

                    # 1. Eğer bot pasifse ve force değilse -> DURDUR
                    if not task.is_active and not is_forced:
                        if status in ["running", "worker_running"]:
                            logger.info(f"Stopping bot {task.id} (Deactivated by User and no force marker)")
                            stop_bot(task.id, reason="Task deactivated")
                        continue

                    # 2. Eğer bot WORKER modundaysa -> DOKUNMA (Bırak işini yapsın)
                    if status == "worker_running":
                        # logger.info(f"Bot {task.id} is in worker mode, skipping scheduler intervention.")
                        continue

                    # 3. Zaman Penceresi Kontrolü
                    is_in_window = False
                    if start < end:
                        is_in_window = start <= now_str < end
                    else: 
                        # Cross-midnight (e.g. 22:00 to 06:00)
                        is_in_window = now_str >= start or now_str < end
                    
                    if is_forced:
                        # Manuel başlatılmışsa dokunma, bırak çalışsın
                        continue

                    # 4. Bekleyen Komut Kontrolü (Double-start engelleme)
                    # Eğer hala işlenmemiş bir komut dosyası varsa scheduler müdahale etmesin
                    start_cmd = commands_dir / f"start_{task.id}.json"
                    stop_cmd = commands_dir / f"stop_{task.id}.json"
                    worker_cmd = commands_dir / f"worker_{task.id}.json"
                    if start_cmd.exists() or stop_cmd.exists() or worker_cmd.exists():
                        # logger.info(f"Bot {task.id} için bekleyen komut var, pas geçiliyor.")
                        continue

                    if is_in_window:
                        if status == "stopped":
                            bot_mode = task.search_params.get("mode", "normal") if task.search_params else "normal"
                            page_limit = task.search_params.get("page_limit", 50) if task.search_params else 50
                            src_task_id = task.search_params.get("source_task_id") if task.search_params else None
                            logger.info(f"Starting bot {task.id} (Schedule Match: {start}-{end}, mode={bot_mode})")
                            start_bot(task.id, task.target_url, max_pages=page_limit, mode=bot_mode, source_task_id=src_task_id)
                    else:
                        # Zaman dışı ve force değilse -> DURDUR
                        if status == "running":
                            logger.info(f"Stopping bot {task.id} (Schedule Ended: {start}-{end})")
                            stop_bot(task.id, reason="Schedule ended")

            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
            
            time.sleep(10) # Check every 10s (Faster response)

    thread = threading.Thread(target=scheduler_loop, daemon=True, name="SchedulerThread")
    thread.start()
