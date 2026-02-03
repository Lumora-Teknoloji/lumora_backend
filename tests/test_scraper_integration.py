# test_scraper_integration.py
"""
Scraper entegrasyonu test scripti.
1. 10 mock ürün oluşturur
2. Günlük metriklerle simülasyon yapar
3. Veritabanındaki daily_metrics'i kontrol eder
"""
import os
import sys
import random
from datetime import datetime, timedelta

# LangChain backend path'ini ekle (tests klasöründen bir üst dizin)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.database import build_connection_string
from app.models import Product, DailyMetric


def create_mock_product(product_id: str, category: str = "elbise") -> dict:
    """Gerçekçi mock ürün verisi oluşturur."""
    return {
        "product_id": product_id,
        "ProductName": f"Test Ürün {product_id}",
        "Brand": "Test Marka",
        "Seller": "Test Satıcı",
        "URL": f"https://www.trendyol.com/test/test-urun-p-{product_id}",
        "Price": str(random.randint(100, 1000)),
        "Discount": str(random.randint(50, 99)),
        "Rating": str(round(random.uniform(3.5, 5.0), 1)),
        "Review Count": str(random.randint(10, 500)),
        "Size": ["S", "M", "L", "XL"],
        "Image_URLs": [f"https://cdn.example.com/{product_id}_1.jpg"],
        "BasketCount": f"{random.randint(50, 500)} kişinin sepetinde",
        "FavoriteCount": f"{random.randint(1, 10)}B kişi favoriledi!",
        "ViewCount": f"{random.randint(100, 1000)} kişi görüntüledi",
        "QACount": f"Satıcı Soruları ({random.randint(1, 50)})",
        "category_tag": category,
        "Renk": random.choice(["Siyah", "Beyaz", "Kırmızı", "Mavi"]),
        "Kumaş Tipi": random.choice(["Pamuk", "Polyester", "İpek"]),
        "Desen": random.choice(["Düz", "Çizgili", "Puantiyeli"]),
    }


def create_day2_mock(original: dict) -> dict:
    """Mevcut ürün verisini 1 gün sonraki değerlerle günceller."""
    updated = original.copy()
    
    old_price = float(original.get("Price", 100))
    price_change = old_price * random.uniform(-0.15, 0.15)
    updated["Price"] = str(round(old_price + price_change, 2))
    updated["BasketCount"] = f"{random.randint(100, 800)} kişinin sepetinde"
    updated["FavoriteCount"] = f"{random.randint(2, 15)}B kişi favoriledi!"
    updated["ViewCount"] = f"{random.randint(200, 2000)} kişi görüntüledi"
    
    old_review = int(original.get("Review Count", 10))
    updated["Review Count"] = str(old_review + random.randint(1, 20))
    updated["QACount"] = f"Satıcı Soruları ({random.randint(5, 60)})"
    
    return updated


# Import service after path is set
from app.services.scraper_service import TrendyolScraperService


def run_test():
    """Ana test fonksiyonu."""
    print("=" * 70)
    print("SCRAPER ENTEGRASYON TESTİ")
    print("=" * 70)
    
    # Veritabanı bağlantısı
    try:
        engine = create_engine(build_connection_string())
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        print("✓ Veritabanı bağlantısı başarılı")
    except Exception as e:
        print(f"✗ Veritabanı bağlantı hatası: {e}")
        return
    
    service = TrendyolScraperService(db)
    
    # ==================== GÜN 1: İLK SCRAPE ====================
    print("\n" + "-" * 70)
    print("GÜN 1: İLK SCRAPE (10 ürün)")
    print("-" * 70)
    
    # 10 mock ürün oluştur
    day1_products = []
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    for i in range(1, 11):
        product_id = f"TEST_{timestamp}_{i:03d}"
        mock = create_mock_product(product_id)
        day1_products.append(mock)
        print(f"  Ürün {i}: {product_id}")
    
    # Toplu kayıt
    print("\n→ Veritabanına kaydediliyor...")
    stats1 = service.process_scraped_batch(day1_products)
    print(f"  Sonuç: {stats1['inserted']} yeni, {stats1['updated']} güncellendi, {stats1['errors']} hata")
    
    # ==================== GÜN 2: İKİNCİ SCRAPE ====================
    print("\n" + "-" * 70)
    print("GÜN 2: İKİNCİ SCRAPE (Mock - değişen metrikler)")
    print("-" * 70)
    
    day2_products = []
    for original in day1_products:
        updated = create_day2_mock(original)
        day2_products.append(updated)
    
    print(f"  {len(day2_products)} ürün güncellenmiş metriklerle hazır")
    
    # Toplu kayıt (bu sefer UPDATE olmalı)
    print("\n→ Veritabanına kaydediliyor...")
    stats2 = service.process_scraped_batch(day2_products)
    print(f"  Sonuç: {stats2['inserted']} yeni, {stats2['updated']} güncellendi, {stats2['errors']} hata")
    
    # ==================== DOĞRULAMA ====================
    print("\n" + "-" * 70)
    print("DOĞRULAMA")
    print("-" * 70)
    
    all_passed = True
    
    for p in day1_products:
        pid = p["product_id"]
        product = service.get_product_by_code(pid)
        
        if not product:
            print(f"  ✗ {pid}: Ürün bulunamadı!")
            all_passed = False
            continue
        
        metrics = db.query(DailyMetric).filter(
            DailyMetric.product_id == product.id
        ).order_by(DailyMetric.recorded_at.asc()).all()
        
        expected_count = 2  # Gün 1 + Gün 2
        
        if len(metrics) >= expected_count:
            m1, m2 = metrics[0], metrics[-1]
            print(f"  ✓ {pid}: {len(metrics)} metrik")
            print(f"      Gün1: Fiyat={m1.price}, Rating={m1.avg_rating}, Velocity={m1.velocity_score}")
            print(f"      Gün2: Fiyat={m2.price}, Rating={m2.avg_rating}, Velocity={m2.velocity_score}")
        else:
            print(f"  ✗ {pid}: Beklenen >= {expected_count}, bulunan {len(metrics)}")
            all_passed = False
    
    # ==================== ÖZET ====================
    print("\n" + "=" * 70)
    if all_passed and stats1['inserted'] == 10 and stats2['updated'] == 10:
        print("✓ TEST BAŞARILI")
        print("  - 10 yeni ürün oluşturuldu")
        print("  - 10 ürün güncellendi (yeni daily_metrics)")
    else:
        print("✗ TEST BAŞARISIZ")
    print("=" * 70)
    
    # Veritabanı istatistikleri
    total_products = db.query(func.count(Product.id)).scalar()
    total_metrics = db.query(func.count(DailyMetric.id)).scalar()
    
    print(f"\nVeritabanı Durumu:")
    print(f"  Products: {total_products}")
    print(f"  DailyMetrics: {total_metrics}")
    
    db.close()


if __name__ == "__main__":
    run_test()
