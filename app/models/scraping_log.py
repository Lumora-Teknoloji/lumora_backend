from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from ..core.database import Base

class ScrapingLog(Base):
    __tablename__ = "scraping_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50))
    keyword = Column(String(200))
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True))
    pages_scraped = Column(Integer, default=0)
    products_found = Column(Integer, default=0)
    products_added = Column(Integer, default=0)
    products_updated = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    task_id = Column(Integer, ForeignKey("scraping_tasks.id"), nullable=True)
    status = Column(String(50), default="running")
    error_details = Column(Text, nullable=True)
    screenshot_path = Column(String(255), nullable=True)
    target_url = Column(Text, nullable=True)
    is_critical = Column(Boolean, default=False)
    last_error = Column(String, nullable=True)
    last_message = Column(String(500), nullable=True) # UI için son mesaj
    ip_rotations = Column(Integer, default=0) # IP değişim sayısı
    last_seen = Column(DateTime(timezone=True), onupdate=func.now()) # Son görülme
