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
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    product = relationship("Product", back_populates="daily_metrics")
    
    # ==================== TEMEL VERİLER ====================
    price = Column(Float)            # Orijinal fiyat
    discounted_price = Column(Float) # İndirimli fiyat
    discount_rate = Column(Float)    # İndirim yüzdesi (0-100)
    
    # Stok durumu
    stock_status   = Column(Boolean, default=True)
    available_sizes = Column(Integer)  # Mevcut beden sayısı
    stock_depth    = Column(Integer)   # Toplam stok adedi (varsa scraper'dan)

    # ==================== HAM METRİKLER ====================
    cart_count     = Column(Integer)   # "X kişinin sepetinde"
    favorite_count = Column(Integer)   # "X kişi favoriledi"
    view_count     = Column(Integer)   # "X kişi görüntüledi"
    rating_count   = Column(Integer)   # Yorum sayısı
    avg_rating     = Column(Float)     # Ortalama puan (1-5)
    qa_count       = Column(Integer)   # Soru-cevap sayısı

    # ==================== ARAMA SIRALAMA TAKİBİ ====================
    search_term  = Column(String(200), index=True)  # Hangi arama terimi
    search_rank  = Column(Integer)                  # Sayfadaki sıra (1-48)
    page_number  = Column(Integer)                  # Hangi sayfa
    absolute_rank = Column(Integer)                 # Toplam sıra = (page-1)*48 + rank
    scrape_mode  = Column(String(20))               # Kazıma modu
    # DEPRECATED — absolute_rank kullanın
    sales_rank   = Column(Integer)

    # ==================== RANK MOMENTUM (Intelligence Faz 1) ====================
    # Lumora Intelligence nightly batch tarafından güncellenir
    rank_change_1d  = Column(Integer)              # Dünden bugüne rank değişimi (+iyileşme, -kötüleşme)
    rank_change_3d  = Column(Integer)              # 3 günlük rank değişimi
    rank_velocity   = Column(Float)                # Rank değişim hızı (expon. moving avg)
    momentum_score  = Column(Float)                # tanh(rank_change_3d / 100) → [-1, +1]
    is_new_entrant  = Column(Boolean, default=False)  # İlk kez top100'e giren ürün

    # ==================== HESAPLANAN SKORLAR ====================
    engagement_score    = Column(Float)   # Etkileşim skoru
    popularity_score    = Column(Float)   # Popülerlik skoru
    sales_velocity      = Column(Float)   # Saatlik sepet artış hızı
    demand_acceleration = Column(Float)   # Talep ivmesi
    trend_direction     = Column(Integer) # -1 düşüş, 0 sabit, 1 yükseliş
    velocity_score      = Column(Float)   # DEPRECATED: engagement_score kullanın
