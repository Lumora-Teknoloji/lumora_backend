import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.database import Base, get_db
import time

# Use the actual FastAPI app which connects to Postgres
client = TestClient(app)

def test_create_task():
    response = client.post(
        "/api/scraper/tasks",
        json={
            "task_name": "Test Task",
            "target_platform": "Trendyol",
            "search_term": "unit test shirt",
            "mode": "normal",
            "page_limit": 1,
            "is_active": True
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["search_term"] == "unit test shirt"
    assert data["status"] == "active"
    assert "id" in data
    
    # Check progress fields
    assert "progress_percent" in data
    assert "queue_stats" in data
    
    # Save ID for next tests
    global task_id
    task_id = data["id"]

def test_get_task():
    response = client.get(f"/api/scraper/tasks/{task_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task_id
    assert data["search_term"] == "Test Task"
    assert data["progress_percent"] == 0.0

def test_update_task_status():
    response = client.patch(f"/api/scraper/tasks/{task_id}/status?status=stopped")
    assert response.status_code == 200
    
    # Verify status changed
    get_resp = client.get(f"/api/scraper/tasks/{task_id}")
    assert get_resp.json()["status"] == "stopped"

def test_list_tasks():
    response = client.get("/api/scraper/tasks")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    
    # Check the fields of the first task
    first_task = data[0]
    assert "progress_percent" in first_task
    assert "queue_stats" in first_task
