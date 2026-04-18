"""
Agents Router — Dağıtık Agent Yönetim API'si

Agent'lar bu endpoint'ler üzerinden:
1. Register olur
2. Heartbeat gönderir (ve komut alır)
3. Veri senkronize eder
"""
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.database import get_db, SessionLocal
from app.models.agent import Agent, AgentCommand, AgentLogEntry
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class AgentRegisterRequest(BaseModel):
    name: str
    os: str = ""
    arch: str = ""
    python: str = ""
    secret: str = ""

class HeartbeatRequest(BaseModel):
    agent_id: Optional[int] = None
    name: str = ""
    status: str = "idle"
    current_task: Optional[str] = None
    stats: dict = {}
    timestamp: Optional[str] = None

class CommandRequest(BaseModel):
    command: str  # scrape, stop, sync, status
    params: dict = {}

class LogEntry(BaseModel):
    level: str = "INFO"
    logger: str = ""
    message: str = ""
    timestamp: Optional[str] = None

class LogBatchRequest(BaseModel):
    agent_id: int
    logs: list[LogEntry] = []

class AgentRenameRequest(BaseModel):
    name: str

class AgentSchedulePatchRequest(BaseModel):
    enabled: bool
    time: str  # HH:MM
    keyword: str
    mode: str = "linker"

# ─── Register ─────────────────────────────────────────────────────────────────

@router.post("/register")
@limiter.limit("10/minute")
def register_agent(request: Request, req: AgentRegisterRequest, db: Session = Depends(get_db)):
    """Agent kaydı — ilk çalıştırmada çağrılır."""
    if req.secret != settings.agent_secret:
        raise HTTPException(status_code=401, detail="Geçersiz secret")

    # Aynı isimde agent varsa güncelle
    agent = db.query(Agent).filter(Agent.name == req.name).first()
    
    if agent:
        agent.os_info = req.os
        agent.arch = req.arch
        agent.python_version = req.python
        agent.status = "online"
        agent.last_heartbeat = datetime.now(timezone.utc).replace(tzinfo=None)
        agent.is_active = True
        db.commit()
        logger.info(f"Agent güncellendi: {req.name} (ID: {agent.id})")
    else:
        agent = Agent(
            name=req.name,
            os_info=req.os,
            arch=req.arch,
            python_version=req.python,
            secret=req.secret,
            status="online",
            last_heartbeat=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        logger.info(f"Yeni agent kayıt: {req.name} (ID: {agent.id})")
    
    return {"agent_id": agent.id, "name": agent.name, "status": "registered"}


# ─── Heartbeat ────────────────────────────────────────────────────────────────

def _clean_stale_agents(agent_id: int):
    db = SessionLocal()
    try:
        from datetime import timedelta
        stale_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
        stale_agents = db.query(Agent.id).filter(
            Agent.id != agent_id,
            Agent.last_heartbeat < stale_cutoff,
        ).all()
        
        if stale_agents:
            stale_ids = [stale.id for stale in stale_agents]
            db.query(AgentCommand).filter(AgentCommand.agent_id.in_(stale_ids)).delete(synchronize_session=False)
            db.query(AgentLogEntry).filter(AgentLogEntry.agent_id.in_(stale_ids)).delete(synchronize_session=False)
            db.query(Agent).filter(Agent.id.in_(stale_ids)).delete(synchronize_session=False)
            db.commit()
            logger.info(f"🧹 {len(stale_ids)} adet sessiz (24 saat+) agent ve ilişkili verileri topluca silindi.")
    except Exception as e:
        logger.error(f"Eski agent temizleme hatası: {e}")
    finally:
        db.close()

def _process_heartbeat(req: HeartbeatRequest, db: Session, background_tasks: BackgroundTasks):
    agent = None
    if req.agent_id:
        agent = db.query(Agent).filter(Agent.id == req.agent_id).first()
    if not agent and req.name:
        agent = db.query(Agent).filter(Agent.name == req.name).first()
    
    if not agent:
        return None

    normalized_status = "standby" if req.status == "idle" else req.status
    agent.status = normalized_status
    agent.current_task = req.current_task
    agent.stats = req.stats
    agent.last_heartbeat = datetime.now(timezone.utc).replace(tzinfo=None)
    agent.is_active = True
    db.commit()

    import random
    if random.random() < 0.05:
        background_tasks.add_task(_clean_stale_agents, agent.id)

    pending_cmd = db.query(AgentCommand).filter(
        AgentCommand.agent_id == agent.id,
        AgentCommand.status == "pending",
    ).order_by(AgentCommand.created_at.asc()).first()

    response = {"ok": True, "agent_id": agent.id, "schedule_config": agent.schedule_config}

    if pending_cmd:
        response["command"] = {
            "id": pending_cmd.id,
            "type": pending_cmd.command,
            **pending_cmd.params,
        }
        pending_cmd.status = "delivered"
        pending_cmd.delivered_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()

    return response

@router.post("/heartbeat")
async def heartbeat(req: HeartbeatRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Agent durum bildirimi. Bekleyen komut varsa yanıtta döner."""
    response = await run_in_threadpool(_process_heartbeat, req, db, background_tasks)
    if response is None:
        raise HTTPException(status_code=401, detail="Agent bulunamadı veya kayıtsız")
    return response


# ─── Command ──────────────────────────────────────────────────────────────────

def _process_send_command(agent_id: int, req: CommandRequest, db: Session):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent bulunamadı")

    cmd = AgentCommand(
        agent_id=agent_id,
        command=req.command,
        params=req.params,
    )
    db.add(cmd)
    db.commit()
    db.refresh(cmd)

    return {"command_id": cmd.id, "status": "queued", "agent": agent.name}

@router.post("/{agent_id}/command")
@limiter.limit("10/minute")
async def send_command(request: Request, agent_id: int, req: CommandRequest, db: Session = Depends(get_db)):
    """Agent'a komut gönder (kuyruğa ekler, sonraki heartbeat'te teslim edilir)."""
    return await run_in_threadpool(_process_send_command, agent_id, req, db)


# ─── Delete Agent ─────────────────────────────────────────────────────────────

@router.delete("/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    """Agent'ı ve tüm ilişkili verilerini kalıcı olarak siler."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent bulunamadı")

    name = agent.name
    # İlişkili komutları ve logları temizle
    deleted_cmds = db.query(AgentCommand).filter(AgentCommand.agent_id == agent_id).delete()
    deleted_logs = db.query(AgentLogEntry).filter(AgentLogEntry.agent_id == agent_id).delete()
    db.delete(agent)
    db.commit()

    logger.info(f"🗑️ Agent silindi: {name} (ID: {agent_id}, {deleted_cmds} komut, {deleted_logs} log)")
    return {
        "status": "deleted",
        "agent": name,
        "cleaned": {"commands": deleted_cmds, "logs": deleted_logs},
    }


# ─── Rename Agent ─────────────────────────────────────────────────────────────

@router.patch("/{agent_id}/name")
def rename_agent(agent_id: int, req: AgentRenameRequest, db: Session = Depends(get_db)):
    """Agent'ın görünen yüz (display) ismini günceller."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent bulunamadı")

    agent.display_name = req.name
    db.commit()
    logger.info(f"✏️ Agent yeniden adlandırıldı: {agent.name} -> {agent.display_name} (ID: {agent.id})")
    return {"status": "ok", "agent_id": agent.id, "display_name": agent.display_name}


# ─── Agent Schedule ───────────────────────────────────────────────────────────

@router.patch("/{agent_id}/schedule")
def update_agent_schedule(agent_id: int, req: AgentSchedulePatchRequest, db: Session = Depends(get_db)):
    """Agent'ın zamanlanmış görev konfigürasyonunu günceller."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent bulunamadı")

    agent.schedule_config = {
        "enabled": req.enabled,
        "time": req.time,
        "keyword": req.keyword,
        "mode": req.mode
    }
    db.commit()
    logger.info(f"⏱️ Agent zamanlayıcısı güncellendi: {agent.name} (ID: {agent.id}) -> {req.time} {req.enabled}")
    return {"status": "ok", "agent_id": agent.id, "schedule_config": agent.schedule_config}


# ─── List Agents ──────────────────────────────────────────────────────────────

@router.get("/list")
def list_agents(db: Session = Depends(get_db)):
    """Tüm agent'ları listele."""
    agents = db.query(Agent).filter(Agent.is_active == True).all()
    
    result = []
    for a in agents:
        # 2 dakikadan fazla heartbeat yoksa offline say
        is_online = False
        if a.last_heartbeat:
            diff = (datetime.now(timezone.utc).replace(tzinfo=None) - a.last_heartbeat).total_seconds()
            is_online = diff < 120
        
        result.append({
            "id": a.id,
            "name": a.display_name if a.display_name else a.name,
            "hostname": a.name,
            "os": a.os_info,
            "status": a.status if is_online else "offline",
            "current_task": a.current_task,
            "stats": a.stats or {},
            "schedule_config": a.schedule_config or {"enabled": False, "time": "09:00", "keyword": "", "mode": "linker"},
            "last_heartbeat": a.last_heartbeat.isoformat() + "Z" if a.last_heartbeat else None,
            "registered_at": getattr(a, 'registered_at', None).isoformat() + "Z" if getattr(a, 'registered_at', None) else None,
        })
    
    return result


# ─── Data Sync ────────────────────────────────────────────────────────────────

def _process_sync_data(tmp_path: str, agent_id: str, db: Session):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker as sm
    
    sqlite_engine = create_engine(f"sqlite:///{tmp_path}")
    SSession = sm(bind=sqlite_engine)
    sqlite_session = SSession()
    
    from sqlalchemy import MetaData, Table, select
    from sqlalchemy.exc import DatabaseError, OperationalError
    metadata = MetaData()
    
    try:
        metadata.reflect(bind=sqlite_engine)
    except (DatabaseError, OperationalError) as e:
        logger.warning(f"Agent {agent_id} geçersiz/bozuk veritabanı gönderdi. Atlanıyor. Detay: {e}")
        sqlite_engine.dispose()
        raise HTTPException(400, "Yüklenen dosya geçerli bir SQLite veritabanı değil veya anlık olarak bozuk.")
        
    merged = {"products_added": 0, "products_updated": 0, "metrics": 0}
    
    try:
        if "products" in metadata.tables:
            products_table = metadata.tables["products"]
            rows = sqlite_session.execute(select(products_table)).fetchall()
            
            from app.models.product import Product as PgProduct
            from app.models.daily_metric import DailyMetric as PgMetric
            
            for row in rows:
                row_dict = row._asdict() if hasattr(row, '_asdict') else dict(row._mapping)
                url = row_dict.get("url")
                product_code = row_dict.get("product_code")
                if not url:
                    continue
                
                existing = db.query(PgProduct).filter(PgProduct.url == url).first()
                if not existing and product_code:
                    existing = db.query(PgProduct).filter(PgProduct.product_code == str(product_code)).first()
                
                if existing:
                    for key in ["name", "brand", "seller", "category", "category_tag",
                                "image_url", "last_price", "last_discount_rate",
                                "attributes", "review_summary", "sizes"]:
                        if key in row_dict and row_dict[key] is not None:
                            if key == "image_url" and row_dict[key] == "" and getattr(existing, "image_url", ""):
                                continue
                            setattr(existing, key, row_dict[key])
                    if existing.url != url:
                        existing.url = url
                    existing.last_scraped_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    merged["products_updated"] += 1
                else:
                    new_p = PgProduct(
                        product_code=product_code,
                        url=url,
                        name=row_dict.get("name", ""),
                        brand=row_dict.get("brand", ""),
                        image_url=row_dict.get("image_url", ""),
                        seller=row_dict.get("seller", ""),
                        category=row_dict.get("category", ""),
                        category_tag=row_dict.get("category_tag", ""),
                        last_price=row_dict.get("last_price", 0),
                        last_discount_rate=row_dict.get("last_discount_rate", 0),
                        attributes=row_dict.get("attributes"),
                        sizes=row_dict.get("sizes"),
                        review_summary=row_dict.get("review_summary"),
                    )
                    db.add(new_p)
                    merged["products_added"] += 1
            
        if "daily_metrics" in metadata.tables:
            metrics_table = metadata.tables["daily_metrics"]
            rows = sqlite_session.execute(select(metrics_table)).fetchall()
            
            for row in rows:
                m_dict = row._asdict() if hasattr(row, '_asdict') else dict(row._mapping)
                sqlite_product_id = m_dict.get("product_id")
                
                if "products" in metadata.tables:
                    products_table = metadata.tables["products"]
                    sqlite_p = sqlite_session.execute(select(products_table).where(products_table.c.id == sqlite_product_id)).first()
                    if not sqlite_p:
                        continue
                    p_dict = sqlite_p._asdict() if hasattr(sqlite_p, '_asdict') else dict(sqlite_p._mapping)
                    url = p_dict.get("url")
                    if not url:
                        continue
                    
                    pg_product = db.query(PgProduct).filter(PgProduct.url == url).first()
                    if not pg_product:
                        continue
                    
                    new_m = PgMetric(
                        product_id=pg_product.id,
                        price=m_dict.get("price", 0),
                        discounted_price=m_dict.get("discounted_price", 0),
                        discount_rate=m_dict.get("discount_rate", 0),
                        avg_rating=m_dict.get("avg_rating", 0),
                        rating_count=m_dict.get("rating_count", 0),
                        favorite_count=m_dict.get("favorite_count", 0),
                        cart_count=m_dict.get("cart_count", 0),
                        view_count=m_dict.get("view_count", 0),
                        qa_count=m_dict.get("qa_count", 0),
                        stock_status=m_dict.get("stock_status", True),
                        search_term=m_dict.get("search_term", ""),
                        search_rank=m_dict.get("search_rank"),
                        page_number=m_dict.get("page_number"),
                        absolute_rank=m_dict.get("absolute_rank"),
                        scrape_mode=m_dict.get("scrape_mode"),
                    )
                    db.add(new_m)
                    merged["metrics"] += 1
        
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        sqlite_engine.dispose()
        
    return merged

@router.post("/sync")
@limiter.limit("5/minute")
async def sync_data(
    request: Request,
    file: UploadFile = File(...),
    agent_id: str = Form("unknown"),
    db: Session = Depends(get_db),
):
    """Agent'ın local SQLite verisini alır ve PostgreSQL'e merge eder."""
    
    # 1. Gelen dosyayı geçici dizine kaydet
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, "agent_upload.db")
    
    try:
        content = await file.read()
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(413, "Dosya çok büyük (Max 50MB)")
        
        # Eğer uzantı .gz ise, GZIP ile sıkıştırılmış veriyi bellekte aç
        if file.filename and file.filename.endswith(".gz"):
            import gzip
            content = gzip.decompress(content)
            
        with open(tmp_path, "wb") as f:
            f.write(content)
        
        merged = await run_in_threadpool(_process_sync_data, tmp_path, agent_id, db)
        
        logger.info(f"Agent {agent_id} sync tamamlandı: {merged}")
        return {"status": "ok", "merged": merged}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sync hatası: {e}")
        raise HTTPException(500, f"Sync hatası: {str(e)}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

# ─── Agent Logs ───────────────────────────────────────────────────────────────

def _clean_old_logs():
    db = SessionLocal()
    try:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
        old = db.query(AgentLogEntry).filter(AgentLogEntry.timestamp < cutoff).delete()
        if old:
            logger.info(f"TTL temizliği: {old} eski log silindi")
        db.commit()
    except Exception as e:
        logger.error(f"Log TTL temizleme hatası: {e}")
    finally:
        db.close()

def _process_ingest_logs(req: LogBatchRequest, db: Session, background_tasks: BackgroundTasks):
    if not req.logs:
        return {"status": "ok", "ingested": 0}

    count = 0
    for entry in req.logs:
        ts = None
        if entry.timestamp:
            try:
                ts = datetime.fromisoformat(entry.timestamp)
            except (ValueError, TypeError):
                ts = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            ts = datetime.now(timezone.utc).replace(tzinfo=None)

        log_row = AgentLogEntry(
            agent_id=req.agent_id,
            level=entry.level.upper(),
            logger_name=entry.logger or "",
            message=entry.message,
            timestamp=ts,
        )
        db.add(log_row)
        count += 1

    db.commit()
    background_tasks.add_task(_clean_old_logs)
    logger.debug(f"Agent {req.agent_id} → {count} log kaydedildi")
    return {"status": "ok", "ingested": count}

@router.post("/logs")
async def ingest_logs(req: LogBatchRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Agent'ın batch halinde log göndermesi."""
    return await run_in_threadpool(_process_ingest_logs, req, db, background_tasks)


@router.get("/{agent_id}/logs")
def get_agent_logs(
    agent_id: int,
    limit: int = 50,
    level: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Belirli bir agent'ın son loglarını döner."""
    query = db.query(AgentLogEntry).filter(AgentLogEntry.agent_id == agent_id)
    
    if level and level.upper() != "ALL":
        query = query.filter(AgentLogEntry.level == level.upper())
    
    logs = query.order_by(AgentLogEntry.timestamp.desc()).limit(limit).all()
    
    return [
        {
            "id": log.id,
            "level": log.level,
            "logger": log.logger_name,
            "message": log.message,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in reversed(logs)  # Kronolojik sıra (eski → yeni)
    ]


@router.get("/logs/latest")
def get_latest_logs(
    limit: int = 50,
    level: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Tüm agent'lardan son logları döner (genel bakış)."""
    query = db.query(AgentLogEntry)
    
    if level and level.upper() != "ALL":
        query = query.filter(AgentLogEntry.level == level.upper())
    
    logs = query.order_by(AgentLogEntry.timestamp.desc()).limit(limit).all()
    
    # Agent isimlerini çek
    agent_ids = set(log.agent_id for log in logs)
    agents = db.query(Agent).filter(Agent.id.in_(agent_ids)).all() if agent_ids else []
    agent_map = {a.id: a.name for a in agents}
    
    return [
        {
            "id": log.id,
            "agent_id": log.agent_id,
            "agent_name": agent_map.get(log.agent_id, "?"),
            "level": log.level,
            "logger": log.logger_name,
            "message": log.message,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in reversed(logs)
    ]
