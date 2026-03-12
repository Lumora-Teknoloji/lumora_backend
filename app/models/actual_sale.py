# app/models/actual_sale.py
"""
Gerçek satış sonuçları — Feedback loop'un ikinci halkası.
production_decisions ile eşleşerek Intelligence'ı gerçek veriye bağlar.
"""
from sqlalchemy import Column, Integer, Float, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from .base import Base


class ActualSale(Base):
    """
    Üretilen ürünlerin gerçek satış sonuçlarını tutar.
    sell_through_rate = sold_quantity / produced_quantity
    Bu tablo dolmaya başladıkça Intelligence'ın doğruluğu artar:
      0  kayıt → ~%55-60 isabetlilik
      30 kayıt → ~%70-75 (CatBoost ilk gerçek eğitim)
      100 kayıt → ~%80-85
    """
    __tablename__ = "actual_sales"

    id                = Column(Integer, primary_key=True)
    production_id     = Column(Integer, ForeignKey("production_decisions.id", ondelete="CASCADE"), index=True)
    sold_quantity     = Column(Integer)     # Gerçek satılan adet
    produced_quantity = Column(Integer)     # Üretilen adet (production_decision.quantity'den kopyalanır)
    sell_through_rate = Column(Float)       # sold / produced  → 1.0 mükemmel, 0.0 hiç satılmamış
    revenue           = Column(Float)       # Gerçek gelir (opsiyonel)
    feedback_date     = Column(Date, server_default=func.current_date())
    created_at        = Column(DateTime(timezone=True), server_default=func.now())

    # İlişki
    production = relationship("ProductionDecision", back_populates="actual_sales")
