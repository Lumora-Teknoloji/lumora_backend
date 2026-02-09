# app/services/scraper_service.py
"""
Trendyol scraper verilerini veritabanına kaydeden servis.
- Product: Ürün verileri
- DailyMetric: Günlük snapshot'lar
"""
import re
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import Product, DailyMetric
from app.services.metrics_service import metrics

logger = logging.getLogger(__name__)


class TrendyolScraperService:
    """Scraper verilerini işleyen ve veritabanına kaydeden servis."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== PARSING UTILITIES ====================

    def _parse_count(self, text: Optional[str]) -> Optional[int]:
        """
        Türkçe metin içinden sayıyı parse eder.
        Örnek: "6,4B kişinin sepetinde" -> 6400
        """
        if not text:
            return None
        
        match = re.search(r'([\d,\.]+)\s*([BbKk])?', text)
        if not match:
            return None
        
        number_str = match.group(1).replace(",", ".")
        multiplier_char = match.group(2)
        
        try:
            number = float(number_str)
            if multiplier_char and multiplier_char.upper() in ('B', 'K'):
                number *= 1000
            return int(number)
        except ValueError:
            return None

    def _parse_qa_count(self, text: Optional[str]) -> Optional[int]:
        """Q&A sayısını parse eder."""
        if not text:
            return None
        match = re.search(r'\((\d+)\)', text)
        return int(match.group(1)) if match else None

    # ==================== MAPPING ====================

    def _map_scraped_to_product(self, scraped: dict, task_id: Optional[int] = None) -> dict:
        """Scraper verisini Product model alanlarına eşler."""
        image_urls = scraped.get("Image_URLs", [])
        first_image = image_urls[0] if image_urls else None
        
        # Dinamik özellikler
        attributes = {
            "image_urls": image_urls,
            "color": scraped.get("Renk") or scraped.get("Color"),
            "fabric_type": scraped.get("Kumaş Tipi") or scraped.get("FabricType"),
            "pattern": scraped.get("Desen"),
            "neck_style": scraped.get("Yaka Tipi"),
            "sleeve_type": scraped.get("Kol Tipi"),
            "length": scraped.get("Boy"),
            "origin": scraped.get("Menşei"),
            "sizes": scraped.get("Size", []),
        }
        
        return {
            "task_id": task_id,
            "product_code": str(scraped.get("product_id")),
            "name": scraped.get("ProductName"),
            "brand": scraped.get("Brand"),
            "seller": scraped.get("Seller"),
            "url": scraped.get("URL"),
            "image_url": first_image,
            "category_tag": scraped.get("category_tag"),
            "attributes": attributes,
        }

    def _map_scraped_to_daily_metric(self, scraped: dict, previous_metric: Optional[DailyMetric] = None) -> dict:
        """Scraper verisini DailyMetric model alanlarına eşler."""
        # Parse fiyatlar
        try:
            price = float(scraped.get("Price")) if scraped.get("Price") else None
        except (ValueError, TypeError):
            price = None
            
        try:
            discounted_price = float(scraped.get("Discount")) if scraped.get("Discount") else None
        except (ValueError, TypeError):
            discounted_price = None
        
        # İndirim oranı
        discount_rate = metrics.calculate_discount_rate(price, discounted_price)
        
        # Rating
        try:
            avg_rating = float(scraped.get("Rating")) if scraped.get("Rating") else None
        except (ValueError, TypeError):
            avg_rating = None
            
        try:
            rating_count = int(scraped.get("Review Count", 0))
        except (ValueError, TypeError):
            rating_count = 0
        
        # Ham metrikler
        cart_count = self._parse_count(scraped.get("BasketCount")) or 0
        favorite_count = self._parse_count(scraped.get("FavoriteCount")) or 0
        view_count = self._parse_count(scraped.get("ViewCount")) or 0
        qa_count = self._parse_qa_count(scraped.get("QACount")) or 0
        
        # Mevcut beden sayısı
        sizes = scraped.get("Size", [])
        available_sizes = len(sizes) if isinstance(sizes, list) else 0
        
        # ==================== HESAPLANAN SKORLAR ====================
        
        # Engagement skoru (anlık)
        engagement_score = metrics.calculate_velocity_score(
            basket_count=cart_count,
            favorite_count=favorite_count,
            view_count=view_count,
            use_log_scale=True  # Büyük sayılar için log scale
        )
        
        # Popülerlik skoru
        popularity_score = metrics.calculate_engagement_score(
            rating=avg_rating,
            review_count=rating_count,
            qa_count=qa_count,
            favorite_count=favorite_count
        )
        
        # ==================== ZAMAN BAZLI METRİKLER ====================
        sales_velocity = None
        demand_acceleration = None
        trend_direction = 0
        
        if previous_metric:
            # Önceki metrik ile karşılaştır
            time_diff_hours = self._calculate_hours_diff(previous_metric.recorded_at, datetime.now(timezone.utc))
            
            if time_diff_hours > 0:
                # Saatlik sepet artış hızı
                prev_cart = previous_metric.cart_count or 0
                sales_velocity = (cart_count - prev_cart) / time_diff_hours
                
                # Talep ivmesi
                prev_velocity = previous_metric.sales_velocity or 0
                demand_acceleration = sales_velocity - prev_velocity
                
                # Trend yönü
                if sales_velocity > prev_velocity * 1.1:
                    trend_direction = 1  # Yükseliş
                elif sales_velocity < prev_velocity * 0.9:
                    trend_direction = -1  # Düşüş
                else:
                    trend_direction = 0  # Sabit
        
        return {
            "recorded_at": datetime.now(timezone.utc),
            # Fiyat
            "price": price,
            "discounted_price": discounted_price,
            "discount_rate": discount_rate,
            # Stok
            "stock_status": True,
            "available_sizes": available_sizes,
            # Ham metrikler
            "cart_count": cart_count,
            "favorite_count": favorite_count,
            "view_count": view_count,
            "qa_count": qa_count,
            # Değerlendirmeler
            "rating_count": rating_count,
            "avg_rating": avg_rating,
            # Anlık skorlar
            "engagement_score": engagement_score,
            "popularity_score": popularity_score,
            "velocity_score": engagement_score,  # Geriye uyumluluk
            # Zaman bazlı
            "sales_velocity": sales_velocity,
            "demand_acceleration": demand_acceleration,
            "trend_direction": trend_direction,
        }

    def _calculate_hours_diff(self, start: datetime, end: datetime) -> float:
        """İki zaman arasındaki saat farkını hesaplar."""
        if not start or not end:
            return 0
        diff = end - start
        return diff.total_seconds() / 3600

    # ==================== PRODUCT OPERATIONS ====================

    def get_product_by_code(self, product_code: str) -> Optional[Product]:
        """Ürün koduna göre ürün getirir."""
        return self.db.query(Product).filter(Product.product_code == product_code).first()

    def get_last_metric(self, product_id: int) -> Optional[DailyMetric]:
        """Ürünün son metriğini getirir."""
        return self.db.query(DailyMetric).filter(
            DailyMetric.product_id == product_id
        ).order_by(desc(DailyMetric.recorded_at)).first()

    def create_product(self, scraped: dict, task_id: Optional[int] = None) -> Product:
        """Yeni ürün oluşturur."""
        product_data = self._map_scraped_to_product(scraped, task_id)
        product = Product(**product_data)
        self.db.add(product)
        self.db.flush()
        logger.info(f"Yeni ürün: {product.product_code}")
        return product

    def create_daily_metric(self, product: Product, scraped: dict) -> DailyMetric:
        """Günlük metrik snapshot'ı oluşturur."""
        # Önceki metriği al (velocity hesabı için)
        previous_metric = self.get_last_metric(product.id)
        
        metric_data = self._map_scraped_to_daily_metric(scraped, previous_metric)
        metric_data["product_id"] = product.id
        
        metric = DailyMetric(**metric_data)
        self.db.add(metric)
        
        # Product'ın özet alanlarını güncelle
        product.last_price = metric_data.get("price")
        product.last_discount_rate = metric_data.get("discount_rate")
        product.last_engagement_score = metric_data.get("engagement_score")
        product.last_scraped_at = datetime.now(timezone.utc)
        
        # Ortalama velocity hesapla
        if metric_data.get("sales_velocity") is not None:
            if product.avg_sales_velocity:
                # Hareketli ortalama
                product.avg_sales_velocity = (product.avg_sales_velocity + metric_data["sales_velocity"]) / 2
            else:
                product.avg_sales_velocity = metric_data["sales_velocity"]
        
        return metric

    def upsert_product(self, scraped: dict, task_id: Optional[int] = None) -> Tuple[Product, bool]:
        """Ürün yoksa oluşturur, varsa daily_metric ekler."""
        product_code = str(scraped.get("product_id"))
        existing = self.get_product_by_code(product_code)
        
        if existing:
            self.create_daily_metric(existing, scraped)
            return existing, False
        else:
            new_product = self.create_product(scraped, task_id)
            self.create_daily_metric(new_product, scraped)
            return new_product, True

    def process_scraped_batch(self, products: list[dict], task_id: Optional[int] = None) -> dict:
        """Toplu veri işleme."""
        stats = {"inserted": 0, "updated": 0, "errors": 0}
        
        for scraped in products:
            try:
                product, is_new = self.upsert_product(scraped, task_id)
                if is_new:
                    stats["inserted"] += 1
                else:
                    stats["updated"] += 1
            except Exception as e:
                logger.error(f"Ürün hatası: {scraped.get('product_id')} - {e}")
                stats["errors"] += 1
                continue
        
        self.db.commit()
        logger.info(f"Batch tamamlandı: {stats}")
        
        return stats

    # ==================== STATISTICS ====================
    
    def get_product_count(self) -> int:
        """Toplam ürün sayısını döner."""
        from sqlalchemy import func
        return self.db.query(func.count(Product.id)).scalar()
    
    def get_daily_metric_count(self) -> int:
        """Toplam metrik sayısını döner."""
        from sqlalchemy import func
        return self.db.query(func.count(DailyMetric.id)).scalar()
    
    def get_last_scrape_date(self) -> Optional[datetime]:
        """Son scraping tarihini döner."""
        last = self.db.query(DailyMetric).order_by(desc(DailyMetric.recorded_at)).first()
        return last.recorded_at if last else None
