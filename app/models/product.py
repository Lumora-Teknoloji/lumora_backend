from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from .base import Base


class Product(Base):
    """
    Ürün temel bilgilerini tutar.
    Değişken veriler (fiyat, stok, vb.) DailyMetric tablosunda.
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("scraping_tasks.id"))
    
    # ==================== KİMLİK BİLGİLERİ ====================
    product_code = Column(String, index=True, unique=True)  # Trendyol ürün ID'si
    name = Column(String)
    brand = Column(String, index=True)
    seller = Column(String, index=True)  # Satıcı adı
    
    # ==================== URL & MEDYA ====================
    url = Column(String)  # Ürün sayfası URL'i
    image_url = Column(String)  # Ana görsel URL'i
    
    # ==================== KATEGORİ ====================
    category = Column(String, index=True)  # Ana kategori
    category_tag = Column(String)  # Alt kategori/etiket
    
    # ==================== AI VEKTÖRLERİ ====================
    # pgvector: CREATE EXTENSION vector; yapmayı unutma.
    feature_vector = Column(Vector(1536))  # Görsel/metin embedding
    
    # ==================== ÖZELLİKLER ====================
    # Dinamik özellikler JSONB olarak saklanır
    # Örnek: {renk: "Siyah", kumaş: "Pamuk", beden: ["S","M","L"]}
    attributes = Column(JSONB)
    
    # ==================== HESAPLANAN ALANLAR ====================
    # Son scraping'den gelen özet veriler (hızlı erişim için)
    last_price = Column(Float)
    last_discount_rate = Column(Float)
    last_engagement_score = Column(Float)
    avg_sales_velocity = Column(Float)  # Ortalama satış hızı
    
    # ==================== ZAMAN BİLGİLERİ ====================
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_scraped_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # ==================== İLİŞKİLER ====================
    task = relationship("ScrapingTask", back_populates="products")
    daily_metrics = relationship("DailyMetric", back_populates="product", cascade="all, delete-orphan")
    designs = relationship("GeneratedDesign", back_populates="product")
    forecasts = relationship("SalesForecast", back_populates="product")