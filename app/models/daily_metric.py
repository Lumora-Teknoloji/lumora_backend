from sqlalchemy import Column, Integer, Float, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from .base import Base

class DailyMetric(Base):
    __tablename__ = "daily_metrics"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"))
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    
    product = relationship("Product", back_populates="daily_metrics")
    
    # Değişken Veriler
    price = Column(Float)
    discount_rate = Column(Float)
    stock_status = Column(Boolean)
    
    # Pazar Performans Verileri
    sales_rank = Column(Integer) # Sıralamadaki yeri (Örn: 1. sıradaydı, 5'e düştü)
    rating_count = Column(Integer)
    avg_rating = Column(Float)
    
    # Hesaplanan Trend Skorları
    velocity_score = Column(Float) # Satış hızı artış oranı