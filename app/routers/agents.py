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
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.agent import Agent, AgentCommand, AgentLogEntry

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

# ─── Register ─────────────────────────────────────────────────────────────────

@router.post("/register")
def register_agent(req: AgentRegisterRequest, db: Session = Depends(get_db)):
    """Agent kaydı — ilk çalıştırmada çağrılır."""
    # Aynı isimde agent varsa güncelle
    agent = db.query(Agent).filter(Agent.name == req.name).first()
    
    if agent:
        agent.os_info = req.os
        agent.arch = req.arch
        agent.python_version = req.python
        agent.status = "online"
        agent.last_heartbeat = datetime.utcnow()
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
            last_heartbeat=datetime.utcnow(),
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        logger.info(f"Yeni agent kayıt: {req.name} (ID: {agent.id})")
    
    return {"agent_id": agent.id, "name": agent.name, "status": "registered"}


# ─── Heartbeat ────────────────────────────────────────────────────────────────

@router.post("/heartbeat")
def heartbeat(req: HeartbeatRequest, db: Session = Depends(get_db)):
    """Agent durum bildirimi. Bekleyen komut varsa yanıtta döner."""
    
    # Agent'ı bul (ID veya isim ile)
    agent = None
    if req.agent_id:
        agent = db.query(Agent).filter(Agent.id == req.agent_id).first()
    if not agent and req.name:
        agent = db.query(Agent).filter(Agent.name == req.name).first()
    
    if not agent:
        # Auto-register
        agent = Agent(name=req.name or "unknown", status="online")
        db.add(agent)
        db.commit()
        db.refresh(agent)

    # Durumu güncelle
    agent.status = req.status
    agent.current_task = req.current_task
    agent.stats = req.stats
    agent.last_heartbeat = datetime.utcnow()
    agent.is_active = True
    db.commit()

    # 60 dakikadır sessiz kalan agent'ları sil
    from datetime import timedelta
    stale_cutoff = datetime.utcnow() - timedelta(minutes=60)
    stale_agents = db.query(Agent).filter(
        Agent.id != agent.id,
        Agent.last_heartbeat < stale_cutoff,
    ).all()
    for stale in stale_agents:
        # İlişkili komutları ve logları da temizle
        db.query(AgentCommand).filter(AgentCommand.agent_id == stale.id).delete()
        db.query(AgentLogEntry).filter(AgentLogEntry.agent_id == stale.id).delete()
        db.delete(stale)
        logger.info(f"🧹 Sessiz agent silindi: {stale.name} (ID: {stale.id}, son sinyal: {stale.last_heartbeat})")
    if stale_agents:
        db.commit()

    # Bekleyen komut var mı?
    pending_cmd = db.query(AgentCommand).filter(
        AgentCommand.agent_id == agent.id,
        AgentCommand.status == "pending",
    ).order_by(AgentCommand.created_at.asc()).first()

    response = {"ok": True, "agent_id": agent.id}

    if pending_cmd:
        # Komutu teslim et
        response["command"] = {
            "id": pending_cmd.id,
            "type": pending_cmd.command,
            **pending_cmd.params,
        }
        pending_cmd.status = "delivered"
        pending_cmd.delivered_at = datetime.utcnow()
        db.commit()

    return response


# ─── Command ──────────────────────────────────────────────────────────────────

@router.post("/{agent_id}/command")
def send_command(agent_id: int, req: CommandRequest, db: Session = Depends(get_db)):
    """Agent'a komut gönder (kuyruğa ekler, sonraki heartbeat'te teslim edilir)."""
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
            diff = (datetime.utcnow() - a.last_heartbeat).total_seconds()
            is_online = diff < 120
        
        result.append({
            "id": a.id,
            "name": a.display_name if a.display_name else a.name,
            "hostname": a.name,
            "os": a.os_info,
            "status": a.status if is_online else "offline",
            "current_task": a.current_task,
            "stats": a.stats or {},
            "last_heartbeat": a.last_heartbeat.isoformat() + "Z" if a.last_heartbeat else None,
            "registered_at": getattr(a, 'registered_at', None).isoformat() + "Z" if getattr(a, 'registered_at', None) else None,
        })
    
    return result


# ─── Data Sync ────────────────────────────────────────────────────────────────

@router.post("/sync")
async def sync_data(
    file: UploadFile = File(...),
    agent_id: str = Form("unknown"),
    db: Session = Depends(get_db),
):
    """Agent'ın local SQLite verisini alır ve PostgreSQL'e merge eder."""
    
    # 1. Gelen dosyayı geçici dizine kaydet
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, "agent_upload.db")
    
    try:
        with open(tmp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 2. SQLite'ı aç ve verileri oku
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker as sm
        
        sqlite_engine = create_engine(f"sqlite:///{tmp_path}")
        SSession = sm(bind=sqlite_engine)
        sqlite_session = SSession()
        
        # Scrapper modellerini import et (farklı Base!)
        from sqlalchemy import MetaData, Table, select
        from sqlalchemy.exc import DatabaseError, OperationalError
        metadata = MetaData()
        
        try:
            metadata.reflect(bind=sqlite_engine)
        except (DatabaseError, OperationalError) as e:
            logger.warning(f"Agent {agent_id} geçersiz/bozuk veritabanı gönderdi. Atlanıyor. Detay: {e}")
            sqlite_engine.dispose()
            raise HTTPException(400, "Yüklenen dosya geçerli bir SQLite veritabanı değil veya anlık olarak bozuk.")
            
        merged = {"products": 0, "metrics": 0}
        
        # 3. Products tablosunu merge et
        if "products" in metadata.tables:
            products_table = metadata.tables["products"]
            rows = sqlite_session.execute(select(products_table)).fetchall()
            
            from app.models.product import Product as PgProduct
            from app.models.daily_metric import DailyMetric as PgMetric
            
            for row in rows:
                row_dict = row._asdict() if hasattr(row, '_asdict') else dict(row._mapping)
                url = row_dict.get("url")
                if not url:
                    continue
                
                existing = db.query(PgProduct).filter(PgProduct.url == url).first()
                if existing:
                    # Güncelle
                    for key in ["name", "brand", "seller", "category", "category_tag",
                                "image_url", "last_price", "last_discount_rate",
                                "attributes", "review_summary", "sizes"]:
                        if key in row_dict and row_dict[key] is not None:
                            # if it's empty string and it's image_url, don't override a good image_url with an empty one
                            if key == "image_url" and row_dict[key] == "" and getattr(existing, "image_url", ""):
                                continue
                            setattr(existing, key, row_dict[key])
                    existing.last_scraped_at = datetime.utcnow()
                else:
                    # Yeni ekle
                    new_p = PgProduct(
                        product_code=row_dict.get("product_code"),
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
                    merged["products"] += 1
            
            db.commit()
        
        # 4. Daily metrics tablosunu merge et
        if "daily_metrics" in metadata.tables:
            metrics_table = metadata.tables["daily_metrics"]
            rows = sqlite_session.execute(select(metrics_table)).fetchall()
            
            for row in rows:
                m_dict = row._asdict() if hasattr(row, '_asdict') else dict(row._mapping)
                sqlite_product_id = m_dict.get("product_id")
                
                # SQLite URL'sini bul
                if "products" in metadata.tables:
                    products_table = metadata.tables["products"]
                    sqlite_p = sqlite_session.execute(select(products_table).where(products_table.c.id == sqlite_product_id)).first()
                    if not sqlite_p:
                        continue
                    p_dict = sqlite_p._asdict() if hasattr(sqlite_p, '_asdict') else dict(sqlite_p._mapping)
                    url = p_dict.get("url")
                    if not url:
                        continue
                    
                    # PostgreSQL'deki product_id'yi bul
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
        sqlite_engine.dispose()
        
        logger.info(f"Agent {agent_id} sync tamamlandı: {merged}")
        return {"status": "ok", "merged": merged}
        
    except Exception as e:
        logger.error(f"Sync hatası: {e}")
        raise HTTPException(500, f"Sync hatası: {str(e)}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

# ─── Agent Logs ───────────────────────────────────────────────────────────────

@router.post("/logs")
def ingest_logs(req: LogBatchRequest, db: Session = Depends(get_db)):
    """Agent'ın batch halinde log göndermesi."""
    if not req.logs:
        return {"status": "ok", "ingested": 0}

    count = 0
    for entry in req.logs:
        ts = None
        if entry.timestamp:
            try:
                ts = datetime.fromisoformat(entry.timestamp)
            except (ValueError, TypeError):
                ts = datetime.utcnow()
        else:
            ts = datetime.utcnow()

        log_row = AgentLogEntry(
            agent_id=req.agent_id,
            level=entry.level.upper(),
            logger_name=entry.logger or "",
            message=entry.message,
            timestamp=ts,
        )
        db.add(log_row)
        count += 1

    # TTL: 7 günden eski logları temizle
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=7)
    old = db.query(AgentLogEntry).filter(AgentLogEntry.timestamp < cutoff).delete()
    if old:
        logger.info(f"TTL temizliği: {old} eski log silindi")

    db.commit()
    logger.debug(f"Agent {req.agent_id} → {count} log kaydedildi")
    return {"status": "ok", "ingested": count}


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
