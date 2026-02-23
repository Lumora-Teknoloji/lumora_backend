from sqlalchemy import text
from app.core.database import engine

def main():
    try:
        with engine.connect() as conn:
            print("Checking ALL tables directly...")
            
            # List all tables
            tables = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).fetchall()
            print("Tables found:", [t[0] for t in tables])
            
            for table_name in ["scraping_tasks", "scraping_queue", "scraping_logs", "products", "daily_metrics"]:
                try:
                    count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                    print(f"{table_name} count: {count}")
                except Exception as e:
                    print(f"{table_name} error: {e}")
                    try:
                        conn.rollback()
                        print("Transaction rolled back.")
                    except:
                        pass
            
            # Check Queue Status Distribution
            print("\nQueue Status Distribution:")
            try:
                dist = conn.execute(text("SELECT status, COUNT(*) FROM scraping_queue GROUP BY status")).fetchall()
                for status, count in dist:
                    print(f"  {status}: {count}")
            except Exception as e:
                print(f"Error checking queue distribution: {e}")

            # Check Errors
            print("\nRecent Failed Items (Top 5):")
            try:
                errors = conn.execute(text("SELECT url, error_msg FROM scraping_queue WHERE status='failed' ORDER BY processed_at DESC LIMIT 5")).fetchall()
                for url, msg in errors:
                    print(f"  URL: {url[:50]}...\n  Error: {msg}\n")
            except Exception as e:
                print(f"Error checking failed items: {e}")

            print("\nRecent Log Errors:")
            try:
                log_errors = conn.execute(text("SELECT error_details FROM scraping_logs WHERE errors > 0 ORDER BY id DESC LIMIT 1")).fetchone()
                if log_errors:
                    print(f"  Log Details: {log_errors[0][:500]}...")
            except Exception as e:
                print(f"Error checking log errors: {e}")

            # Reset Failed Items
            print("\nResetting failed items...")
            try:
                result = conn.execute(text("UPDATE scraping_queue SET status='pending', retry_count=0 WHERE status='failed'"))
                print(f"  Reset count: {result.rowcount}")
                conn.commit()
            except Exception as e:
                print(f"Error resetting failed items: {e}")
                try: conn.rollback() 
                except: pass

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
