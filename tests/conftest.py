import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os

# Override environment variables for testing
os.environ["POSTGRESQL_HOST"] = "localhost"
os.environ["POSTGRESQL_DATABASE"] = "test_db"
os.environ["POSTGRESQL_USERNAME"] = "test_user"
os.environ["POSTGRESQL_PASSWORD"] = "test_pass"
os.environ["JWT_SECRET"] = "test_secret"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["APP_ENV"] = "testing"

from unittest.mock import MagicMock, patch
from app.main import fastapi_app as app
from app.core.database import get_db

@pytest.fixture()
def db_session():
    # Return a MagicMock that acts like a sqlalchemy Session
    session = MagicMock()
    # Provide default return values for common query chains if needed
    # session.query.return_value.filter.return_value.first.return_value = None
    yield session

@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session
            
    app.dependency_overrides[get_db] = override_get_db
    with patch("app.core.lifespan.setup_database"):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()
