# app/models/user_product.py
"""
Kullanıcıya ait ürün kayıtları.
Her kullanıcı kendi dashboard'unda ürün kaydedebilir,
performans etiketi atayabilir ve takip edebilir.
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text,
    ForeignKey, DateTime, func
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from .base import Base


class UserProduct(Base):
    """
    Kullanıcının dashboard'una kaydettiği ürünler.
    Opsiyonel olarak DB'deki Product ile eşleştirilebilir.
    """
    __tablename__ = "user_products"

    id              = Column(Integer, primary_key=True)
    user_id         = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id      = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)

    # ==================== KULLANICI GİRİŞ BİLGİLERİ ====================
    name            = Column(String(300), nullable=False)
    category        = Column(String(100), index=True)
    brand           = Column(String(100))
    price           = Column(Float)
    image_url       = Column(String(500))
    description     = Column(Text)
    attributes      = Column(JSONB)  # {renk, kumaş, beden, stil, vb.}

    # ==================== PERFORMANS İŞARETLEME ====================
    performance_tag  = Column(String(30))   # 'bestseller' | 'impactful' | 'potential' | 'flop' | None
    performance_note = Column(String(500))  # Kullanıcının serbest notu

    # ==================== TAKİP ====================
    is_watching      = Column(Boolean, default=True)

    # ==================== ZAMAN ====================
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    updated_at       = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # ==================== İLİŞKİLER ====================
    user    = relationship("User", back_populates="user_products")
    product = relationship("Product")
