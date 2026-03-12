# app/models/production_decision.py
"""
Üretim kararları — Feedback loop'un birinci halkası.
Intelligence'ın TREND dediği ürünler için alınan üretim kararlarını tutar.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from .base import Base


class ProductionDecision(Base):
    """
    Her TREND tahmini için alınan üretim kararını kaydeder.
    actual_sales ile eşleşince Kalman feedback loop tetiklenir.
    """
    __tablename__ = "production_decisions"

    id              = Column(Integer, primary_key=True)
    product_id      = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True)
    search_term     = Column(String(100), index=True)   # Hangi kategori (crop, tayt...)
    predicted_score = Column(Float)                     # Intelligence'ın verdiği trend_score
    decision        = Column(String(20))                # 'produce' | 'skip' | 'wait'
    quantity        = Column(Integer)                   # Kaç adet üretilecek/üretildi
    notes           = Column(String(500))               # Serbest not
    decided_at      = Column(DateTime(timezone=True), server_default=func.now())

    # İlişkiler
    product       = relationship("Product")
    actual_sales  = relationship("ActualSale", back_populates="production", cascade="all, delete-orphan")
