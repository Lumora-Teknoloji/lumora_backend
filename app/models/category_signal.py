# app/models/category_signal.py
"""
Kategori günlük sinyal tablosu — Kategori sıcaklık haritası.
Intelligence nightly batch tarafından her gece güncellenir.
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, func
from sqlalchemy import UniqueConstraint
from .base import Base


class CategoryDailySignal(Base):
    """
    Her kategorinin günlük sağlık sinyalini tutar.

    category_heat yorumu:
      +1.0 → Kategori çok ısınıyor (yükselen ürünler çoğunlukta)
       0.0 → Nötr
      -1.0 → Kategori soğuyor (düşen ürünler çoğunlukta)

    Kullanım:
      - Intelligence: kategori bazlı ağırlık ayarlaması
      - Backend/Frontend: "Bugün hangi kategoriler sıcak?" dashboard widget'ı
    """
    __tablename__ = "category_daily_signals"

    id             = Column(Integer, primary_key=True)
    signal_date    = Column(Date, index=True, server_default=func.current_date())
    search_term    = Column(String(100), index=True)      # Kategori adı (crop, tayt, ...)

    # Sayısal özetler
    total_products  = Column(Integer)    # Kategorideki toplam ürün
    rising_count    = Column(Integer)    # TREND / POTANSIYEL olanlar
    falling_count   = Column(Integer)    # DUSEN olanlar
    new_entrants    = Column(Integer)    # is_new_entrant = True olanlar
    avg_fav_change  = Column(Float)      # Ortalama favori değişimi
    avg_rank_change = Column(Float)      # Ortalama rank değişimi

    # Isı skoru: -1.0 (soğuyor) … +1.0 (ısınıyor)
    category_heat   = Column(Float)

    # Uyarı bayrağı
    is_hot          = Column(Boolean, default=False)   # category_heat > 0.8
    is_cold         = Column(Boolean, default=False)   # category_heat < -0.5

    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    # Aynı tarih + kategori kombinasyonu benzersiz olmalı
    __table_args__ = (
        UniqueConstraint("signal_date", "search_term", name="uq_category_signal_date_term"),
    )
