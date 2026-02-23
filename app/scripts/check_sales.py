import sys
from sqlalchemy import text
from app.core.database import engine

def main():
    with engine.connect() as conn:
        print("🔍 LATEST 10 PRICE RECORDS:")
        print("=" * 120)
        
        query = text("""
            SELECT 
                p.brand, 
                p.name, 
                dm.price as original_price,
                dm.discounted_price, 
                dm.discount_rate,
                dm.recorded_at,
                p.url
            FROM daily_metrics dm
            JOIN products p ON dm.product_id = p.id
            ORDER BY dm.recorded_at DESC
            LIMIT 10
        """)
        
        result = conn.execute(query)
        
        for i, row in enumerate(result, 1):
            brand = row[0] or "N/A"
            name = (row[1] or "N/A")[:45]
            orig = row[2] or 0
            disc = row[3] or 0
            rate = row[4] or 0
            date = row[5]
            url = row[6][:70] if row[6] else "N/A"
            
            print(f"\n{i}. [{brand}] {name}")
            print(f"   💰 Discounted: {disc:.2f} TL | Original: {orig:.2f} TL | Discount: %{rate:.1f}")
            print(f"   🕒 {date}")
            print(f"   🔗 {url}")
        
        print("\n" + "=" * 120)
        
        # Check for zero prices
        zero_query = text("""
            SELECT COUNT(*) 
            FROM daily_metrics 
            WHERE discounted_price = 0 OR price = 0
        """)
        zero_count = conn.execute(zero_query).scalar()
        
        valid_query = text("""
            SELECT COUNT(*) 
            FROM daily_metrics 
            WHERE discounted_price > 0 AND price > 0
        """)
        valid_count = conn.execute(valid_query).scalar()
        
        total_query = text("SELECT COUNT(*) FROM daily_metrics")
        total_count = conn.execute(total_query).scalar()
        
        print(f"\n📊 PRICE STATISTICS:")
        print(f"  📦 Total metrics: {total_count}")
        print(f"  ✅ Valid prices (both > 0): {valid_count}")
        print(f"  ❌ Zero prices: {zero_count}")
        if total_count > 0:
            print(f"  📈 Success rate: {(valid_count/total_count*100):.1f}%")
        else:
            print(f"  📈 Success rate: 0%")
        
        # Show zero price examples
        if zero_count > 0:
            print(f"\n🔍 ZERO PRICE EXAMPLES (First 5):")
            print("-" * 120)
            zero_ex_query = text("""
                SELECT p.brand, p.name, dm.price, dm.discounted_price, p.url
                FROM daily_metrics dm
                JOIN products p ON dm.product_id = p.id
                WHERE dm.discounted_price = 0 OR dm.price = 0
                LIMIT 5
            """)
            result = conn.execute(zero_ex_query)
            for i, row in enumerate(result, 1):
                print(f"\n{i}. {row[0]} - {row[1][:50]}")
                print(f"   Price: {row[2]} | Discounted: {row[3]}")
                print(f"   URL: {row[4][:80]}")

if __name__ == "__main__":
    try:
        main()
    except ImportError:
        print("❌ Hata: Bu script'i modül olarak çalıştırmalısınız.")
        print("👉 Kullanım: python -m app.scripts.check_sales")
