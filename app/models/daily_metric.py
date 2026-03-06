from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from .base import Base


class DailyMetric(Base):
    """
    Ürünlerin günlük metrik snapshot'larını tutar.
    Her scraping işleminde yeni bir kayıt oluşturulur.
    """
    __tablename__ = "daily_metrics"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"))
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    product = relationship("Product", back_populates="daily_metrics")
    
    # ==================== TEMEL VERİLER ====================
    # Fiyat bilgileri
    price = Column(Float)  # Orijinal fiyat
    discounted_price = Column(Float)  # İndirimli fiyat
    discount_rate = Column(Float)  # İndirim yüzdesi (0-100)
    
    # Stok durumu
    stock_status = Column(Boolean, default=True)
    available_sizes = Column(Integer)  # Mevcut beden sayısı
    
    # ==================== HAM METRİKLER ====================
    # Trendyol'dan direkt gelen sayılar
    cart_count = Column(Integer)  # "X kişinin sepetinde"
    favorite_count = Column(Integer)  # "X kişi favoriledi"
    view_count = Column(Integer)  # "X kişi görüntüledi"
    
    # Değerlendirmeler
    rating_count = Column(Integer)  # Yorum sayısı
    avg_rating = Column(Float)  # Ortalama puan (1-5)
    qa_count = Column(Integer)  # Soru-cevap sayısı
    
    # Sıralama
    sales_rank = Column(Integer)  # Kategori sıralaması
    
    # ==================== ARAMA SIRALAMA TAKİBİ ====================
    search_term = Column(String(200), index=True)  # Hangi arama terimi ile bu sırada bulundu
    search_rank = Column(Integer)                   # Sayfadaki sıra (1-48)
    page_number = Column(Integer)                   # Hangi sayfa (1, 2, 3...)
    absolute_rank = Column(Integer)                 # Toplam sıra = (page-1)*48 + rank
    scrape_mode = Column(String(20))                # Kazıma modu: api, dom, speed
    
    # ==================== HESAPLANAN SKORLAR ====================
    # Anlık skorlar (tek snapshot ile hesaplanır)
    engagement_score = Column(Float)  # Etkileşim skoru: (sepet×3 + fav×2 + view)
    popularity_score = Column(Float)  # Popülerlik skoru: rating×review_count normalize
    
    # Zaman bazlı skorlar (önceki snapshot ile karşılaştırılarak)
    # Bu değerler scraper_service tarafından hesaplanır
    sales_velocity = Column(Float)  # Saatlik sepet artış hızı: (yeni_sepet - eski_sepet) / saat
    demand_acceleration = Column(Float)  # Talep ivmesi: (yeni_velocity - eski_velocity)
    trend_direction = Column(Integer)  # Trend yönü: -1 (düşüş), 0 (sabit), 1 (yükseliş)
    
    # Eski alan (geriye uyumluluk için)
    velocity_score = Column(Float)  # DEPRECATED: engagement_score kullanın