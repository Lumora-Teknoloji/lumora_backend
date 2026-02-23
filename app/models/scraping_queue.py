from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from ..core.database import Base

class ScrapingQueue(Base):
    """Bulunan ama henüz detayları kazılmamış linkler havuzu"""
    __tablename__ = "scraping_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("scraping_tasks.id"), nullable=False)
    url = Column(String(500), nullable=False, index=True)
    status = Column(String(20), default="pending") # pending, processing, completed, failed
    discovered_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
    error_msg = Column(Text)
    retry_count = Column(Integer, default=0) # Kaç kere denendi?
