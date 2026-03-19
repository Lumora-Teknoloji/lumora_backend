# app/services/metrics_service.py
"""
Metrik ve skor hesaplama formülleri.
Tüm iş mantığı formülleri bu servis içinde tutulur.
"""
import math
from typing import Optional
from dataclasses import dataclass


@dataclass
class VelocityWeights:
    """Velocity skoru için ağırlık konfigürasyonu."""
    basket: float = 3.0
    favorite: float = 2.0
    view: float = 1.0


@dataclass 
class TrendWeights:
    """Trend skoru için ağırlık konfigürasyonu."""
    velocity: float = 0.4
    rating: float = 0.3
    review_growth: float = 0.3


class MetricsService:
    """
    Tüm metrik ve skor hesaplamalarını yapan servis.
    
    Bu servis aşağıdaki formülleri içerir:
    - velocity_score: Ürün popülerlik hızı
    - trend_score: Genel trend skoru
    - discount_rate: İndirim oranı hesaplama
    - engagement_score: Kullanıcı etkileşim skoru
    """

    def __init__(
        self, 
        velocity_weights: VelocityWeights = None,
        trend_weights: TrendWeights = None
    ):
        self.velocity_weights = velocity_weights or VelocityWeights()
        self.trend_weights = trend_weights or TrendWeights()

    # ==================== VELOCITY SCORE ====================
    
    def calculate_velocity_score(
        self,
        basket_count: int = 0,
        favorite_count: int = 0,
        view_count: int = 0,
        use_log_scale: bool = False
    ) -> float:
        """
        Ürün popülerlik hızını hesaplar.
        
        Formül (linear):
            velocity = (sepet × 3) + (favori × 2) + görüntülenme
        
        Formül (log scale - büyük sayılar için):
            velocity = log(sepet+1)×3 + log(favori+1)×2 + log(görüntülenme+1)
        
        Args:
            basket_count: Sepete ekleyen kişi sayısı
            favorite_count: Favorileyen kişi sayısı
            view_count: Görüntüleyen kişi sayısı
            use_log_scale: Büyük sayılar için logaritmik ölçekleme
        
        Returns:
            float: Velocity skoru
        """
        w = self.velocity_weights
        
        if use_log_scale:
            return (
                math.log(basket_count + 1) * w.basket +
                math.log(favorite_count + 1) * w.favorite +
                math.log(view_count + 1) * w.view
            )
        else:
            return (
                basket_count * w.basket +
                favorite_count * w.favorite +
                view_count * w.view
            )

    # ==================== DISCOUNT RATE ====================
    
    def calculate_discount_rate(
        self,
        original_price: Optional[float],
        discounted_price: Optional[float]
    ) -> Optional[float]:
        """
        İndirim oranını hesaplar.
        
        Formül:
            discount_rate = ((orijinal - indirimli) / orijinal) × 100
        
        Args:
            original_price: Orijinal fiyat
            discounted_price: İndirimli fiyat
        
        Returns:
            float: İndirim yüzdesi (0-100)
        """
        if not original_price or not discounted_price:
            return None
        if original_price <= 0:
            return None
        if discounted_price >= original_price:
            return 0.0
            
        return ((original_price - discounted_price) / original_price) * 100

    # ==================== ENGAGEMENT SCORE ====================
    
    def calculate_engagement_score(
        self,
        rating: Optional[float] = None,
        review_count: int = 0,
        qa_count: int = 0,
        favorite_count: int = 0
    ) -> float:
        """
        Kullanıcı etkileşim skorunu hesaplar.
        
        Formül:
            engagement = (rating × 20) + log(review+1)×10 + log(qa+1)×5 + log(fav+1)×5
        
        Args:
            rating: Ortalama puan (1-5)
            review_count: Yorum sayısı
            qa_count: Soru-cevap sayısı
            favorite_count: Favori sayısı
        
        Returns:
            float: Engagement skoru (0-100+)
        """
        rating_score = (rating or 0) * 20  # Max 100
        review_score = math.log(review_count + 1) * 10
        qa_score = math.log(qa_count + 1) * 5
        favorite_score = math.log(favorite_count + 1) * 5
        
        return rating_score + review_score + qa_score + favorite_score

    # ==================== TREND SCORE ====================
    
    def calculate_trend_score(
        self,
        velocity_score: float = 0,
        rating: Optional[float] = None,
        review_growth_rate: float = 0
    ) -> float:
        """
        Genel trend skorunu hesaplar.
        
        Formül:
            trend = (velocity_norm × 0.4) + (rating_norm × 0.3) + (growth × 0.3)
        
        Args:
            velocity_score: Velocity skoru (normalize edilecek)
            rating: Ortalama puan (1-5)
            review_growth_rate: Yorum artış oranı (%)
        
        Returns:
            float: Trend skoru (0-100)
        """
        w = self.trend_weights
        
        # Normalize velocity (log scale, max ~20 → 100)
        velocity_norm = min(math.log(velocity_score + 1) * 5, 100)
        
        # Normalize rating (1-5 → 0-100)
        rating_norm = ((rating or 3) - 1) * 25
        
        # Growth rate capped at 100
        growth_norm = min(review_growth_rate, 100)
        
        return (
            velocity_norm * w.velocity +
            rating_norm * w.rating +
            growth_norm * w.review_growth
        )

    # ==================== PRICE COMPARISON ====================
    
    def calculate_price_change(
        self,
        old_price: Optional[float],
        new_price: Optional[float]
    ) -> Optional[float]:
        """
        Fiyat değişim yüzdesini hesaplar.
        
        Formül:
            change = ((yeni - eski) / eski) × 100
        
        Returns:
            float: Değişim yüzdesi (negatif = düşüş, pozitif = artış)
        """
        if not old_price or not new_price or old_price <= 0:
            return None
        return ((new_price - old_price) / old_price) * 100

    # ==================== STOCK HEALTH ====================
    
    def calculate_stock_health(
        self,
        available_sizes: list,
        total_sizes: int = 6  # S, M, L, XL, XXL, XXXL
    ) -> float:
        """
        Stok sağlığını hesaplar (mevcut beden oranı).
        
        Returns:
            float: 0-100 arası stok sağlığı skoru
        """
        if not available_sizes or total_sizes <= 0:
            return 0.0
        return (len(available_sizes) / total_sizes) * 100


# Singleton instance for easy import
metrics = MetricsService()
