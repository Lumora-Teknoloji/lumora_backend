# app/services/scraper_service.py
"""
Trendyol scraper verilerini veritabanına kaydeden servis.
- Product: Ürün verileri
- DailyMetric: Günlük snapshot'lar
"""
import re
import logging
from datetime import datetime, timedelta, timezone, time
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import Product, DailyMetric
from app.services.data.metrics_service import metrics

logger = logging.getLogger(__name__)

# Intelligence tetikleme cooldown — en az 30 dakikada bir tetikle
_last_intelligence_trigger: Optional[datetime] = None
INTELLIGENCE_COOLDOWN_MINUTES = 30



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
        # Yeni bot image_url (tek string), eski bot Image_URLs (liste) gönderir
        image_urls = scraped.get("Image_URLs", [])
        first_image = image_urls[0] if image_urls else scraped.get("image_url", None)
        
        # Dinamik özellikler — scraper'dan gelen attributes varsa kullan
        raw_attributes = scraped.get("attributes", {})
        if isinstance(raw_attributes, list):
            # [{attribute_name: "Renk", attribute_value: "Siyah"}, ...] → dict
            raw_attributes = {a.get("attribute_name", ""): a.get("attribute_value", "")
                             for a in raw_attributes if a.get("attribute_name")}
        
        attributes = {
            "image_urls": image_urls,
            **raw_attributes,
        }
        
        # Fallback: attributes boşsa eski field mapping
        if not raw_attributes:
            attributes.update({
                "color": scraped.get("Renk") or scraped.get("Color"),
                "fabric_type": scraped.get("Kumaş Tipi") or scraped.get("FabricType"),
                "pattern": scraped.get("Desen"),
                "neck_style": scraped.get("Yaka Tipi"),
                "sleeve_type": scraped.get("Kol Tipi"),
                "length": scraped.get("Boy"),
                "origin": scraped.get("Menşei"),
            })
        
        # Sizes — beden bilgisi
        sizes = scraped.get("sizes") or scraped.get("Size", [])
        if isinstance(sizes, str):
            sizes = [sizes]
        
        # ── Queryable stil kolonları (attributes JSONB'den çıkar) ──────────
        # Hem Türkçe hem İngilizce key'leri destekler
        dominant_color = (
            raw_attributes.get("Renk") or raw_attributes.get("color")
            or raw_attributes.get("Color") or scraped.get("Renk") or scraped.get("Color")
        )
        fabric_type = (
            raw_attributes.get("Kumaş Tipi") or raw_attributes.get("fabric_type")
            or raw_attributes.get("FabricType") or scraped.get("Kumaş Tipi") or scraped.get("FabricType")
        )
        fit_type = (
            raw_attributes.get("Kalıp") or raw_attributes.get("fit_type")
            or raw_attributes.get("FitType") or scraped.get("Kalıp")
        )

        # ── category: arama terimi veya category_tag kaynaklı ─────────────
        category = (
            scraped.get("search_term")       # linker/worker modundan gelir
            or scraped.get("category_tag")   # fallback
        )

        final_task_id = task_id or scraped.get("task_id")

        # Fiyat — yeni bot lowercase, eski bot PascalCase
        try:
            last_price = float(scraped.get("price") or scraped.get("Price") or 0) or None
        except (ValueError, TypeError):
            last_price = None
        try:
            last_discount_rate = int(scraped.get("discount_rate") or 0) or None
        except (ValueError, TypeError):
            last_discount_rate = None

        return {
            "task_id": final_task_id,
            "product_code": str(scraped.get("product_id") or scraped.get("id")),
            "name": scraped.get("name") or scraped.get("ProductName"),
            "brand": scraped.get("brand") or scraped.get("Brand"),
            "seller": scraped.get("seller") or scraped.get("Seller"),
            "url": scraped.get("url") or scraped.get("URL"),
            "image_url": first_image,
            "category": category,
            "category_tag": scraped.get("category_tag"),
            "attributes": attributes,
            "review_summary": scraped.get("review_summary"),
            "sizes": sizes if sizes else None,
            # Fiyat özetleri — doğrudan set et (create_daily_metric'i beklemeden)
            "last_price": last_price,
            "last_discount_rate": last_discount_rate,
            # Queryable stil kolonları
            "dominant_color": dominant_color,
            "fabric_type":    fabric_type,
            "fit_type":       fit_type,
        }

    def _map_scraped_to_daily_metric(self, scraped: dict, previous_metric: Optional[DailyMetric] = None) -> dict:
        """Scraper verisini DailyMetric model alanlarına eşler.
        
        İki format desteklenir:
        - Eski Playwright scraper: PascalCase (Price, Rating, BasketCount vb.)
        - Yeni Redis API bot: lowercase (price, rating, cart_count vb.)
        """
        # Parse fiyatlar — yeni bot lowercase, eski bot PascalCase gönderir
        try:
            raw_price = scraped.get("price") or scraped.get("Price")
            price = float(raw_price) if raw_price else None
        except (ValueError, TypeError):
            price = None
            
        try:
            # Yeni bot org_price, eski bot Discount gönderir
            raw_org = scraped.get("org_price") or scraped.get("Discount")
            discounted_price = float(raw_org) if raw_org else None
        except (ValueError, TypeError):
            discounted_price = None
        
        # İndirim oranı — doğrudan geldiyse kullan, yoksa hesapla
        raw_discount_rate = scraped.get("discount_rate")
        if raw_discount_rate is not None:
            try:
                discount_rate = int(raw_discount_rate)
            except (ValueError, TypeError):
                discount_rate = metrics.calculate_discount_rate(price, discounted_price)
        else:
            discount_rate = metrics.calculate_discount_rate(price, discounted_price)
        
        # Rating — yeni bot: rating/review_count, eski bot: Rating/Review Count
        try:
            raw_rating = scraped.get("rating") or scraped.get("Rating")
            avg_rating = float(raw_rating) if raw_rating else None
        except (ValueError, TypeError):
            avg_rating = None
            
        try:
            rating_count = int(
                scraped.get("review_count")
                or scraped.get("Review Count")
                or 0
            )
        except (ValueError, TypeError):
            rating_count = 0
        
        # Ham metrikler — yeni bot integer, eski bot string+parse gerektirir
        def _get_count(new_key, old_key):
            val = scraped.get(new_key)
            if val is not None:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    pass
            return self._parse_count(scraped.get(old_key)) or 0
        
        cart_count = _get_count("cart_count", "BasketCount")
        favorite_count = _get_count("favorite_count", "FavoriteCount")
        view_count = _get_count("view_count", "ViewCount")
        
        # qa_count — yeni bot integer, eski bot string
        raw_qa = scraped.get("qa_count")
        if raw_qa is not None:
            try:
                qa_count = int(raw_qa)
            except (ValueError, TypeError):
                qa_count = self._parse_qa_count(scraped.get("QACount")) or 0
        else:
            qa_count = self._parse_qa_count(scraped.get("QACount")) or 0
        
        # Mevcut beden sayısı — yeni bot sizes listesi, eski bot Size
        sizes = scraped.get("sizes") or scraped.get("Size", [])
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
            # ── Arama sıralama takibi (Intelligence için kritik sinyal) ──
            "search_term":   scraped.get("search_term") or scraped.get("category_tag"),
            "search_rank":   scraped.get("search_rank"),
            "page_number":   scraped.get("page_number"),
            "absolute_rank": scraped.get("absolute_rank"),
            "scrape_mode":   scraped.get("scrape_mode"),
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

    def get_today_metric(self, product_id: int) -> Optional[DailyMetric]:
        """Ürünün bugüne ait metriğini getirir."""
        today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min).replace(tzinfo=timezone.utc)
        return self.db.query(DailyMetric).filter(
            DailyMetric.product_id == product_id,
            DailyMetric.recorded_at >= today_start
        ).first()

    def get_previous_metric_before_today(self, product_id: int) -> Optional[DailyMetric]:
        """Ürünün bugünden önceki en son metriğini getirir."""
        today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min).replace(tzinfo=timezone.utc)
        return self.db.query(DailyMetric).filter(
            DailyMetric.product_id == product_id,
            DailyMetric.recorded_at < today_start
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
        """Günlük metrik snapshot'ı oluşturur veya mevcut olanı günceller."""
        # Bugüne ait kayıt var mı kontrol et
        today_metric = self.get_today_metric(product.id)
        
        # Karşılaştırma için (hız hesabı vb) bugünden önceki son kaydı kullan
        # Eğer bugün ilk kez çekiliyorsa previous_metric dünkü son kayıt olur.
        # Eğer bugün 2. kez çekiliyorsa previous_metric YİNE dünkü son kayıt olur (günlük farkı korumak için).
        previous_metric = self.get_previous_metric_before_today(product.id)
        
        metric_data = self._map_scraped_to_daily_metric(scraped, previous_metric)
        metric_data["product_id"] = product.id
        
        if today_metric:
            # Güncelle
            for key, value in metric_data.items():
                setattr(today_metric, key, value)
            metric = today_metric
            logger.info(f"Metrik güncellendi (Bugün): {product.product_code}")
        else:
            # Yeni oluştur
            metric = DailyMetric(**metric_data)
            self.db.add(metric)
            logger.info(f"Yeni günlük metrik oluşturuldu: {product.product_code}")
        
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
        """Ürün yoksa oluşturur, varsa günceller ve daily_metric ekler."""
        product_code = str(scraped.get("product_id") or scraped.get("id"))
        existing = self.get_product_by_code(product_code)
        
        if existing:
            # Ensure missing or updated product core fields are also propagated
            product_data = self._map_scraped_to_product(scraped, task_id)
            for key, new_value in product_data.items():
                # Avoid overwriting valid data with empty strings
                if new_value is not None and new_value != "":
                    current_val = getattr(existing, key, None)
                    if current_val != new_value:
                        setattr(existing, key, new_value)
                        
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

        # ── Intelligence'ı tetikle (fire & forget) ────────────────────
        # Yeni veri geldi → scraping bitince Intelligence hemen hesaplasın
        # (gece 02:00'yi beklemeye gerek yok)
        total_written = stats["inserted"] + stats["updated"]
        if total_written >= 5:
            self._trigger_intelligence_async(search_term=None)

        return stats

    def _trigger_intelligence_async(self, search_term: str = None):
        """
        Intelligence /trigger endpoint'ini arka planda çağırır.
        Cooldown: 30 dakikada bir tetiklenebilir (sunucu aşırı yükü önleme).
        """
        global _last_intelligence_trigger
        import threading
        import urllib.request, json
        from datetime import datetime, timezone, timedelta

        # Cooldown kontrolü
        now = datetime.now(timezone.utc)
        if _last_intelligence_trigger is not None:
            elapsed = (now - _last_intelligence_trigger).total_seconds() / 60
            if elapsed < INTELLIGENCE_COOLDOWN_MINUTES:
                remaining = int(INTELLIGENCE_COOLDOWN_MINUTES - elapsed)
                logger.debug(
                    f"Intelligence trigger cooldown: {remaining} dakika bekleniyor"
                )
                return  # Cooldown dolmadı — atla

        _last_intelligence_trigger = now

        def _post():
            try:
                from app.core.config import settings as _cfg
                _trigger_url = f"{_cfg.intelligence_url}/trigger"
                body = json.dumps({
                    "scope": "category" if search_term else "all",
                    "category": search_term,
                    "priority": "normal"
                }).encode()
                req = urllib.request.Request(
                    _trigger_url,
                    data=body,
                    headers={"Content-Type": "application/json"}
                )
                urllib.request.urlopen(req, timeout=5).read()
                logger.info(
                    f"Intelligence tetiklendi (cooldown: {INTELLIGENCE_COOLDOWN_MINUTES}dk): "
                    f"scope={'category' if search_term else 'all'}"
                    + (f" ({search_term})" if search_term else "")
                )
            except Exception as e:
                # Kritik değil — gece nightly_batch yedek olarak çalışır
                logger.debug(f"Intelligence trigger gönderilemedi (normal): {e}")

        t = threading.Thread(target=_post, daemon=True, name="IntelligenceTrigger")
        t.start()


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
