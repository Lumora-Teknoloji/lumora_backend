from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
import os
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
    
    # ==================== ÖZELLİKLER ====================
    # Dinamik özellikler JSONB olarak saklanır
    # Örnek: {renk: "Siyah", kumaş: "Pamuk", beden: ["S","M","L"]}
    attributes = Column(JSONB)
    
    # ==================== YORUM & BEDEN ====================
    review_summary = Column(String)  # AI değerlendirme özeti (Trendyol tarafından oluşturulan)
    sizes = Column(JSONB)  # Mevcut bedenler listesi, örn: ["S", "M", "L", "XL"]
    
    # ==================== HESAPLANAN ALANLAR ====================
    # Son scraping'den gelen özet veriler (hızlı erişim için)
    last_price = Column(Float)
    last_discount_rate = Column(Float)
    last_engagement_score = Column(Float)
    avg_sales_velocity = Column(Float)  # Ortalama satış hızı

    # ==================== STİL ÖZELLİKLERİ (JSONB'den çıkarılmış) ====================
    # attributes JSONB'den extract edilen en sık sorgulanan alanlar
    # Scraper_service veya nightly batch tarafından doldurulur
    dominant_color = Column(String(50), index=True)   # Ürünün ana rengi (Siyah, Beyaz, ...)
    fabric_type    = Column(String(50))               # Kumaş tipi (Pamuk, Polyester, ...)
    fit_type       = Column(String(50))               # Kalıp tipi (Regular, Oversize, ...)

    # ==================== INTELLIGENCE ALANLARI ====================
    # Lumora Intelligence mikro servisi tarafından güncellenir (:8001)
    # Bu kolonlara SADECE Intelligence yazar — backend SADECE okur
    trend_score     = Column(Float, index=True)           # 0-100 ensemble skor
    trend_direction = Column(String(30))                  # TREND / POTANSIYEL / STABIL / DUSEN
    last_scored_at  = Column(DateTime(timezone=True))     # Son Intelligence güncellemesi

    # ==================== ZAMAN BİLGİLERİ ====================
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_scraped_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # ==================== İLİŞKİLER ====================
    task = relationship("ScrapingTask", back_populates="products")
    daily_metrics = relationship("DailyMetric", back_populates="product", cascade="all, delete-orphan")
    designs = relationship("GeneratedDesign", back_populates="product")
    forecasts = relationship("SalesForecast", back_populates="product")


# ==================== AI VEKTÖRLERİ (dinamik) ====================
# pgvector extension PostgreSQL'de yüklüyse feature_vector kolonu otomatik eklenir.
# Bu kontrol database.py'deki ensure_vector_extension() tarafından yapılır.
def _add_vector_column():
    """pgvector varsa feature_vector kolonunu Product modeline ekler."""
    if os.environ.get("PGVECTOR_AVAILABLE", "0") == "1":
        try:
            from pgvector.sqlalchemy import Vector
            Product.feature_vector = Column(Vector(1536))
        except ImportError:
            pass

# NOT: Bu fonksiyon database.py setup_database() içinde çağrılır.
# Model ilk yüklendiğinde pgvector durumu henüz bilinmediği için
# kolon ekleme işlemi setup_database() sırasında yapılır.