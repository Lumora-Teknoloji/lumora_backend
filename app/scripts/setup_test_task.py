import sys
from app.core.database import SessionLocal
from app.models.scraping_task import ScrapingTask
from datetime import datetime

def main():
    db = SessionLocal()
    try:
        # Check if test task exists
        task = db.query(ScrapingTask).filter(ScrapingTask.task_name == "TEST_TASK").first()
        if not task:
            task = ScrapingTask(
                task_name="TEST_TASK",
                target_platform="Trendyol",
                target_url="https://www.trendyol.com/sr?q=kalem",
                search_params={"search_term": "kalem"},
                scrape_interval_hours=24,
                is_active=True,
                start_time="09:00",
                end_time="18:00",
                next_run_at=datetime.now()
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            print(f"Created new test task with ID: {task.id}")
        else:
            print(f"Using existing test task with ID: {task.id}")
            
        return task.id
    except Exception as e:
        print(f"Error: {e}")
        return None
    finally:
        db.close()

if __name__ == "__main__":
    main()
