
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
        # Review modu DB'deki ürünleri kullanır — URL gerekmez
        if mode == "review":
            target_url = "review://db-products"
        else:
            # is_active=False olan test task'ları için sadece debug log (her 10s spam önleme)
            log_level = logger.error if task_id else logger.debug
            logger.debug(f"Bot {task_id}: URL bulunamadı, başlatılamıyor (target_url boş)")
            return
        
    try:
        import subprocess

        linker_path = scrapper_root / "vps" / "linker_service.py"
        
        # Linker servisini çağır (Bot id ve keyword argümanlarıyla)
        keyword = target_url  # target_url artık "search_term" görevini de görüyor
        if not keyword:
            logger.error(f"Failed to queue linker for bot {task_id}: keyword empty")
            return False

        # Eğer url http ile başlıyorsa, linker yerine doğrudan queue'ye atmamız gerekir,
        # ancak şimdilik kullanıcıya "Kategori yaz" dediğimiz için bu senaryoyu basit bırakıyoruz.
        
        cmd = [
            sys.executable, str(linker_path),
            str(keyword),
            "--pages", str(max_pages),
            "--task-id", str(task_id)
        ]

        # Linker'ı arka planda asenkron olarak başlat (blocking olmasın)
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

        logger.info(f"Linker Service executed for keyword: {keyword} (max_pages={max_pages})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to execute linker for bot {task_id}: {e}")
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
                        now_dt = datetime.now(timezone.utc)
                        # next_run_at utc timezone degilse fix
                        next_run = task.next_run_at
                        if next_run:
                            if next_run.tzinfo is None:
                                next_run = next_run.replace(tzinfo=timezone.utc)
                                
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
