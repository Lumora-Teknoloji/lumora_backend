"""Agent — Dağıtık scraper agent modeli"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

from app.core.database import Base


class Agent(Base):
    """Kayıtlı scraper agent'ları."""
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    display_name = Column(String(100), nullable=True)  # UI için özel isim
    os_info = Column(String(100))
    arch = Column(String(50))
    python_version = Column(String(20))
    secret = Column(String(100), default="")
    
    status = Column(String(30), default="offline")  # online, offline, scraping, completed, error
    current_task = Column(String(200))
    stats = Column(JSONB, default={})
    
    last_heartbeat = Column(DateTime)
    registered_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Schedule Configuration
    schedule_config = Column(JSONB, default={"enabled": False, "time": "09:00", "keyword": "", "mode": "linker"})


class AgentCommand(Base):
    """Agent'lara gönderilen komutlar kuyruğu."""
    __tablename__ = "agent_commands"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, nullable=False, index=True)
    
    command = Column(String(50), nullable=False)  # scrape, stop, sync, status
    params = Column(JSONB, default={})
    
    status = Column(String(30), default="pending")  # pending, delivered, completed, failed
    result = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    delivered_at = Column(DateTime)
    completed_at = Column(DateTime)


class AgentLogEntry(Base):
    """Agent'lardan gelen log kayıtları."""
    __tablename__ = "agent_log_entries"
    __table_args__ = (
        Index("ix_agent_log_agent_ts", "agent_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, nullable=False, index=True)
    level = Column(String(20))          # INFO, WARNING, ERROR, CRITICAL
    logger_name = Column(String(100))   # logger adı (LumoraAgent, agent.heartbeat vb.)
    message = Column(Text)              # log mesajı
    timestamp = Column(DateTime)        # log zamanı (agent tarafındaki)
    received_at = Column(DateTime, default=datetime.utcnow)
