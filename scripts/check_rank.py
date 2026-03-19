# scripts/check_rank.py
"""
Diagnostic script: DB'deki rank verilerini ve aktif scraping görevlerini kontrol eder.
Kullanım: python -m scripts.check_rank
"""
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

engine = create_engine(
    f"postgresql://{os.getenv('POSTGRESQL_USERNAME')}:{os.getenv('POSTGRESQL_PASSWORD')}"
    f"@{os.getenv('POSTGRESQL_HOST','localhost')}:{os.getenv('POSTGRESQL_PORT','5432')}"
    f"/{os.getenv('POSTGRESQL_DATABASE')}"
)

with engine.connect() as conn:
    # Rank data samples
    result = conn.execute(text("""
        SELECT dm.search_term, dm.search_rank, dm.page_number, dm.absolute_rank, 
               dm.recorded_at, p.name, p.brand
        FROM daily_metrics dm
        JOIN products p ON p.id = dm.product_id
        WHERE dm.search_rank IS NOT NULL 
        ORDER BY dm.recorded_at DESC LIMIT 10
    """))
    rows = result.fetchall()
    print(f"=== RANK DATA ({len(rows)} rows) ===")
    for row in rows:
        print(f"  [{row[0] or 'EMPTY'}] rank={row[1]}, page={row[2]}, abs={row[3]} | {row[6]} {row[5][:30]}")
    
    # Task URL check
    result2 = conn.execute(text("SELECT id, task_name, target_url FROM scraping_tasks WHERE is_active=true"))
    print("\n=== ACTIVE TASKS ===")
    for row in result2.fetchall():
        print(f"  task_id={row[0]}, name={row[1]}, url={row[2][:60]}...")
