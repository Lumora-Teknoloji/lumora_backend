import logging
import os
import json
import traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text
from fastapi import BackgroundTasks

from app.models.scraping_task import ScrapingTask
from app.models.product import Product
from app.models.scraping_log import ScrapingLog
from app.models.agent import Agent, AgentCommand
from app.routers.redis_queue import get_redis

logger = logging.getLogger(__name__)

def get_scrapper_dir() -> Path:
    """Scrapper dizinini çalışma ortamına göre (Docker veya Local) döner."""
    env_path = os.getenv("SCRAPPER_DIR")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
    
    docker_path = Path("/Scrapper")
    if docker_path.exists() and (docker_path / "redis_agent.py").exists():
        return docker_path
    
    # Yerel Windows ortamında
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    possible_paths = [
        project_root / "scrapper",
        project_root / "Scrapper",
        project_root / "Scrapper-main",
    ]
    for path in possible_paths:
        if path.exists() and (path / "redis_agent.py").exists():
            return path
            
    return project_root / "Scrapper"

async def get_bots_status_list(db: Session) -> list:
    """Tüm botların durumunu hesaplar ve listeler."""
    tasks = db.query(ScrapingTask).all()
    task_ids = [t.id for t in tasks]
    
    queue_counts = {}; pending_counts = {}; linker_speeds = {}; product_speeds = {}
    log_sums = {}; product_counts = {}; active_agent_tasks = []
    
    if task_ids:
        tid_tuple = tuple(task_ids)
        r = await get_redis()
        
        pending_urls = await r.lrange("links:pending", 0, -1)
        task_map = await r.hgetall("links:task_map")
        
        for url in pending_urls:
            tid_str = task_map.get(url)
            if tid_str and tid_str.isdigit():
                tid = int(tid_str)
                queue_counts[tid] = queue_counts.get(tid, 0) + 1
                pending_counts[tid] = pending_counts.get(tid, 0) + 1
                
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        
        for r_row in db.execute(text("SELECT task_id, COUNT(*) FROM scraping_queue WHERE task_id IN :tids AND discovered_at >= :since GROUP BY task_id"), {"tids": tid_tuple, "since": one_hour_ago}).fetchall():
            linker_speeds[r_row[0]] = r_row[1]
        for r_row in db.execute(text("SELECT task_id, COUNT(id) FROM products WHERE task_id IN :tids AND last_scraped_at >= :since GROUP BY task_id"), {"tids": tid_tuple, "since": one_hour_ago}).fetchall():
            product_speeds[r_row[0]] = r_row[1]
            
        for r_row in db.execute(text("SELECT task_id, COALESCE(SUM(COALESCE(products_added, 0) + COALESCE(products_updated, 0)), 0), COALESCE(SUM(ip_rotations), 0) FROM scraping_logs WHERE task_id IN :tids GROUP BY task_id"), {"tids": tid_tuple}).fetchall():
            log_sums[r_row[0]] = {"scraped": r_row[1] or 0, "ips": r_row[2] or 0}
            
        for r_row in db.execute(text("SELECT task_id, COUNT(id) FROM products WHERE task_id IN :tids GROUP BY task_id"), {"tids": tid_tuple}).fetchall():
            product_counts[r_row[0]] = r_row[1]
            
        active_agent_tasks = [a.current_task.lower() for a in db.query(Agent).filter(Agent.is_active == True, Agent.status.in_(["busy", "scraping", "active"])).all() if a.current_task]

    bots = []
    scrapper_dir = get_scrapper_dir()
    
    for task in tasks:
        last_log = db.query(ScrapingLog).filter(ScrapingLog.task_id == task.id).order_by(desc(ScrapingLog.started_at)).first()
        is_critical = getattr(last_log, 'is_critical', False) if last_log else False
        last_error_msg = getattr(last_log, 'last_error', None) if last_log else None

        pid_file = scrapper_dir / f"bot_{task.id}.pid"
        actual_status = "stopped"
        
        if pid_file.exists():
            try:
                with open(pid_file, "r") as f:
                    pid = int(f.read().strip())
                is_running = False
                try:
                    import os
                    os.kill(pid, 0)
                    is_running = True
                except OSError:
                    pass
                except AttributeError:
                    import psutil
                    is_running = psutil.pid_exists(pid)
                
                if is_running:
                    actual_status = "running"
                    if (scrapper_dir / f"bot_{task.id}.worker").exists():
                        actual_status = "worker_running"
                else:
                    pid_file.unlink(missing_ok=True)
            except Exception:
                pass
        else:
            if any(task.task_name and task.task_name.lower() in agent_task for agent_task in active_agent_tasks):
                bot_mode = task.search_params.get("mode", "normal") if task.search_params else "normal"
                actual_status = "worker_running" if bot_mode == "worker" else "running"
        
        if task.is_active and actual_status == "stopped":
            actual_status = "idle"
        
        bot_mode = task.search_params.get("mode", "normal") if task.search_params else "normal"
        if bot_mode == "linker":
            scraped_count = queue_counts.get(task.id, 0)
        else:
            scraped_count = log_sums.get(task.id, {}).get("scraped", 0)
            if scraped_count == 0: scraped_count = product_counts.get(task.id, 0)
        
        err_log = db.query(ScrapingLog).filter(ScrapingLog.task_id == task.id, ScrapingLog.status == "running").order_by(desc(ScrapingLog.started_at)).first()
        if not err_log: err_log = db.query(ScrapingLog).filter(ScrapingLog.task_id == task.id).order_by(desc(ScrapingLog.started_at)).first()
        error_count = err_log.errors if err_log else 0
            
        recent_count = linker_speeds.get(task.id, 0) if bot_mode == "linker" else product_speeds.get(task.id, 0)
        speed = round(recent_count / 60, 1) if recent_count > 0 else 0
        
        queue_task_id = task.search_params["source_task_id"] if bot_mode == "worker" and task.search_params and task.search_params.get("source_task_id") else task.id
        pending_count = pending_counts.get(queue_task_id, 0)
        ip_change_count = log_sums.get(task.id, {}).get("ips", 0)
        
        last_product = db.query(Product).filter(Product.task_id == task.id).order_by(desc(Product.last_scraped_at)).first()
        last_msg = f"Next run: {task.next_run_at}" if task.next_run_at else "Hazır."
        last_url = None
        
        if actual_status in ["running", "worker_running"]:
            last_msg = "🚀 Veri kazıma işlemi devam ediyor..."
        
        if last_product:
            now = datetime.now(timezone.utc)
            last_scraped = last_product.last_scraped_at
            if last_scraped and last_scraped.tzinfo is None:
                last_scraped = last_scraped.replace(tzinfo=timezone.utc)
            if last_scraped and (now - last_scraped).total_seconds() < 1800:
                price_str = f" ({last_product.last_price} TL)" if last_product.last_price else ""
                last_msg = f"🛍️ {last_product.brand} {last_product.name}{price_str}"
                last_url = last_product.url

        source_task_id = task.search_params.get("source_task_id") if task.search_params else None
        
        pages_scraped = 0
        active_log = db.query(ScrapingLog).filter(ScrapingLog.task_id == task.id, ScrapingLog.status == "running").order_by(desc(ScrapingLog.started_at)).first()
        if active_log and active_log.pages_scraped:
            pages_scraped = active_log.pages_scraped
        elif not active_log:
            last_finished_log = db.query(ScrapingLog).filter(ScrapingLog.task_id == task.id).order_by(desc(ScrapingLog.started_at)).first()
            if last_finished_log and last_finished_log.pages_scraped:
                pages_scraped = last_finished_log.pages_scraped

        bot_state = "idle"
        state_message = ""
        state_countdown = 0
        state_started_at = None
        
        if actual_status in ["running", "worker_running"]:
            bot_state = "scraping"
            if active_log:
                msg = active_log.last_message or ""
                if active_log.is_critical:
                    bot_state = "critical"
                    state_message = msg
                elif msg.startswith("[STATE:"):
                    end_idx = msg.index("]")
                    state_part = msg[7:end_idx]
                    parts = state_part.split(":")
                    bot_state = parts[0]
                    if len(parts) > 1:
                        try: state_countdown = int(parts[1])
                        except Exception: pass
                    state_message = msg[end_idx+2:] if len(msg) > end_idx+1 else ""
                    if active_log.last_seen:
                        state_started_at = active_log.last_seen.isoformat()
                else:
                    state_message = msg

        uptime_seconds = 0
        session_started_at = None
        if actual_status in ["running", "worker_running"]:
            if active_log and active_log.started_at:
                started = active_log.started_at.replace(tzinfo=timezone.utc) if active_log.started_at.tzinfo is None else active_log.started_at
                uptime_seconds = int((datetime.now(timezone.utc) - started).total_seconds())
                session_started_at = started.isoformat()
        else:
            last_finished_log = db.query(ScrapingLog).filter(ScrapingLog.task_id == task.id).order_by(desc(ScrapingLog.started_at)).first()
            if last_finished_log and last_finished_log.started_at:
                started = last_finished_log.started_at.replace(tzinfo=timezone.utc) if last_finished_log.started_at.tzinfo is None else last_finished_log.started_at
                ended = last_finished_log.finished_at.replace(tzinfo=timezone.utc) if last_finished_log.finished_at and last_finished_log.finished_at.tzinfo is None else (last_finished_log.finished_at or datetime.now(timezone.utc))
                uptime_seconds = int((ended - started).total_seconds())
                session_started_at = started.isoformat()

        bots.append({
            "id": task.id,
            "name": task.task_name or "Unnamed Bot",
            "platform": task.target_platform or "Trendyol",
            "status": actual_status,
            "task_status": getattr(task, 'status', 'stopped'),
            "keyword": task.search_params.get("search_term", "") if task.search_params else "",
            "mode": bot_mode,
            "source_task_id": source_task_id,
            "start_time": task.start_time or "09:00",
            "end_time": task.end_time or "23:59",
            "scrape_interval_hours": task.scrape_interval_hours or 0,
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
            "stats": {"scraped": scraped_count, "validated": speed, "errors": error_count, "processed": ip_change_count},
            "last_message": last_msg,
            "last_product_url": last_url,
            "use_proxy": task.search_params.get("use_proxy", False) if task.search_params else False
        })
    return bots

def start_bot_process(bot_id: int, task: ScrapingTask, background_tasks: BackgroundTasks, db: Session):
    task.is_active = True
    task.status = "active"
    db.commit()
    
    def _clear_scraped_urls_bg(task_id: int):
        try:
            import httpx
            from app.core.config import settings as app_settings
            secret = getattr(app_settings, 'agent_secret', '')
            resp = httpx.post("http://127.0.0.1:8000/api/redis/queue/clear_scraped_urls", params={"task_id": task_id}, headers={"X-Agent-Secret": secret}, timeout=10)
            logger.info(f"🧹 scraped:urls temizlendi (task={task_id})")
        except Exception as e:
            logger.warning(f"scraped:urls temizleme hatası: {e}")
            
    background_tasks.add_task(_clear_scraped_urls_bg, bot_id)
    
    bot_mode = task.search_params.get("mode", "normal") if task.search_params else "normal"
    keyword = task.search_params.get("search_term", "") if task.search_params else ""
    max_pages = task.search_params.get("page_limit", 50) if task.search_params else 50
    
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=120)
    active_agents = db.query(Agent).filter(Agent.is_active == True, Agent.last_heartbeat > cutoff).all()
    
    if active_agents:
        chosen_agent = active_agents[0]
        db.add(AgentCommand(agent_id=chosen_agent.id, command="scrape", params={"keyword": keyword, "mode": bot_mode, "page_limit": max_pages, "task_id": bot_id}))
        db.commit()
    return True

def stop_bot_process(bot_id: int, task: ScrapingTask, db: Session):
    if task.start_time:
        task.status = "scheduled"
        task.is_active = True
        try:
            time_parts = [int(p) for p in task.start_time.split(":")]
            now = datetime.now(timezone.utc)
            start_dt = now.replace(hour=time_parts[0], minute=time_parts[1], second=0, microsecond=0)
            if start_dt <= now: start_dt += timedelta(days=1)
            task.next_run_at = start_dt
        except Exception: pass
    else:
        task.is_active = False
        task.status = "stopped"
        task.next_run_at = None
        
    db.commit()
    
    active_agents = db.query(Agent).filter(Agent.is_active == True, Agent.status != "offline").all()
    for agent in active_agents:
        db.add(AgentCommand(agent_id=agent.id, command="stop", params={"task_id": bot_id}))
    db.commit()
    return True

def cancel_bot_process(bot_id: int, task: ScrapingTask, db: Session):
    task.is_active = False
    task.next_run_at = None
    db.commit()

    active_agents = db.query(Agent).filter(Agent.is_active == True, Agent.status != "offline").all()
    for agent in active_agents:
        db.add(AgentCommand(agent_id=agent.id, command="cancel", params={"task_id": bot_id}))
    db.commit()
    return True

def toggle_bot_mode(bot_id: int, command_type: str, extra_params: dict = {}):
    scrapper_dir = get_scrapper_dir()
    commands_dir = scrapper_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    
    cmd_name = command_type.split("_")[0].lower()
    cmd_file = commands_dir / f"{cmd_name}_{bot_id}.json"
    
    payload = {"type": command_type, "task_id": bot_id}
    payload.update(extra_params)
    
    with open(cmd_file, "w") as f:
        json.dump(payload, f)
    return True
