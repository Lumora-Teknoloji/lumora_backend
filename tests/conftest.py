import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.models import User

# PostgreSQL for testing
from app.core.config import settings
from urllib.parse import quote_plus

username = quote_plus(settings.postgresql_username)
password = quote_plus(settings.postgresql_password)
test_db_name = f"test_{settings.postgresql_database}"

SQLALCHEMY_DATABASE_URL = (
    f"postgresql+psycopg2://{username}:{password}"
    f"@{settings.postgresql_host}:{settings.postgresql_port}/{test_db_name}"
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Yeni bir veritabanı oturumu oluştur ve tabloları yarat"""
    # Patch engine everywhere it is used
    import app.core.database as database_module
    import app.main as main_module
    
    database_module.engine = engine
    main_module.engine = engine
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    """TestClient oluştur ve get_db dependency'sini override et"""
    
    # Patch engine again just in case, though db_session runs first
    import app.core.database as database_module
    import app.main as main_module
    database_module.engine = engine
    main_module.engine = engine
    
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def test_user(db_session):
    """Test kullanıcısı oluştur"""
    user = User(
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        hashed_password="hashedpassword" # In real test we might not need valid hash unless we test login logic deeply
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def auth_headers(test_user):
    """Test kullanıcısı için auth cookie oluştur"""
    token = create_access_token({"sub": str(test_user.id)})
    # Cookie olarak gönderiyoruz çünkü dependency cookie'den okuyor
    return {"access_token": token}
