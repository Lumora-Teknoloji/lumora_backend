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
from app.models.agent import Agent, AgentCommand

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
            "name": a.name,
            "os": a.os_info,
            "status": a.status if is_online else "offline",
            "current_task": a.current_task,
            "stats": a.stats or {},
            "last_heartbeat": a.last_heartbeat.isoformat() if a.last_heartbeat else None,
            "registered_at": a.registered_at.isoformat() if a.registered_at else None,
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
        metadata = MetaData()
        metadata.reflect(bind=sqlite_engine)
        
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
                                "image_url", "last_price", "last_discount_rate"]:
                        val = row_dict.get(key)
                        if val:
                            setattr(existing, key, val)
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
                    )
                    db.add(new_p)
                    merged["products"] += 1
            
            db.commit()
        
        # 4. Daily metrics tablosunu merge et
        if "daily_metrics" in metadata.tables:
            metrics_table = metadata.tables["daily_metrics"]
            rows = sqlite_session.execute(select(metrics_table)).fetchall()
            # TODO: product_id mapping (SQLite → PostgreSQL)
            merged["metrics"] = len(rows)
        
        sqlite_session.close()
        sqlite_engine.dispose()
        
        logger.info(f"Agent {agent_id} sync tamamlandı: {merged}")
        return {"status": "ok", "merged": merged}
        
    except Exception as e:
        logger.error(f"Sync hatası: {e}")
        raise HTTPException(500, f"Sync hatası: {str(e)}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
