from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


def build_connection_string() -> str:
    """PostgreSQL connection string oluşturur. URL encoding ile güvenli hale getirir."""
    username = quote_plus(settings.postgresql_username)
    password = quote_plus(settings.postgresql_password)
    return (
        f"postgresql+psycopg2://{username}:{password}"
        f"@{settings.postgresql_host}:{settings.postgresql_port}/{settings.postgresql_database}"
    )


# Connection pooling optimizasyonları
engine = create_engine(
    build_connection_string(),
    pool_pre_ping=True,  # Bağlantıları test et
    pool_recycle=3600,  # 1 saatte bir bağlantıları yenile
    pool_size=10,  # Pool boyutu
    max_overflow=20,  # Maksimum ekstra bağlantı
    echo=False,  # SQL sorgularını logla (development için False)
    connect_args={
        "connect_timeout": 30,  # Bağlantı timeout'u (saniye)
    },
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """Database session dependency. Her request için yeni session oluşturur."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

