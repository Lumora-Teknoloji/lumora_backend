from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from .base import Base

class ScrapingTask(Base):
    __tablename__ = "scraping_tasks"

    id = Column(Integer, primary_key=True, index=True)
    
    # Görev Kimliği ve Strateji
    task_name = Column(String(255)) # Örn: "Trendyol Elbise - Çok Satanlar"
    target_platform = Column(String(100)) # Örn: "Amazon", "Trendyol"
    
    # Filtre Parametreleri (JSONB kullanarak esneklik sağlıyoruz)
    # Örn: {"category": "elbise", "sort_by": "best_seller", "min_rating": 4.5}
    search_params = Column(JSONB, nullable=True) 
    
    target_url = Column(String, unique=True, nullable=False)
    
    # Zamanlama ve Otomasyon
    scrape_interval_hours = Column(Integer, default=24) # Kaç saatte bir çalışacak?
    is_active = Column(Boolean, default=True) # Görev durdurulabilir
    
    last_run_at = Column(DateTime(timezone=True))
    next_run_at = Column(DateTime(timezone=True)) # Bir sonraki çalışma zamanı
    
    products = relationship("Product", back_populates="task")