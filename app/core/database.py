from urllib.parse import quote_plus
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import logging

from .config import settings

logger = logging.getLogger(__name__)

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


def check_table_exists(table_name: str) -> bool:
    """Belirtilen tablonun veritabanında var olup olmadığını kontrol eder."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def ensure_conversation_history_columns():
    """
    conversations tablosuna alias ve history_json kolonlarını ekler (varsa dokunmaz).
    Sadece tablo mevcutsa çalışır.
    """
    if not check_table_exists("conversations"):
        logger.info("conversations tablosu henüz oluşturulmamış, kolon ekleme atlanıyor")
        return
    
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS alias VARCHAR(255)"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS history_json JSONB"
                )
            )
            logger.info("conversations tablosu kolonları kontrol edildi")
    except Exception as e:
        logger.warning(f"conversations tablosu kolonları kontrol edilirken uyarı: {e}")
    
    # messages tablosundaki image_url kolonunu TEXT tipine dönüştür
    if check_table_exists("messages"):
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE messages ALTER COLUMN image_url TYPE TEXT")
                )
        except Exception as e:
            # Kolon tipi zaten TEXT olabilir veya başka bir sorun olabilir
            logger.info(f"image_url kolon tipi değiştirme uyarısı: {e}")


def ensure_user_avatar_column():
    """users tablosuna avatar_url kolonunu ekler."""
    if not check_table_exists("users"):
        return
    
    try:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(500)")
            )
            logger.info("users tablosu avatar_url kolonu kontrol edildi")
    except Exception as e:
        logger.warning(f"users tablosu avatar_url kolonu kontrol edilirken uyarı: {e}")


def ensure_vector_extension():
    """pgvector eklentisinin yüklü olduğundan emin olur."""
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("vector eklentisi kontrol edildi")
    except Exception as e:
        logger.warning(f"vector eklentisi kontrol edilirken uyarı: {e}")

def setup_database():
    """Veritabanı tablolarını oluşturur. Mevcut tabloları ve verileri korur."""
    # Modelleri yükle ki Base.metadata dolsun
    import app.models  # noqa
    
    # Vector eklentisini kontrol et
    ensure_vector_extension()

    # Önce tabloların varlığını kontrol et
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    # Metadata'daki beklenen tablolar
    metadata_tables = list(Base.metadata.tables.keys())
    logger.info(f"Beklenen tablolar (Metadata): {metadata_tables}")
    
    missing_tables = [table for table in metadata_tables if table not in existing_tables]
    
    if missing_tables:
        logger.info(f"Eksik tablolar tespit edildi: {missing_tables}. Oluşturuluyor...")
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Veritabanı tabloları başarıyla senkronize edildi.")
        except Exception as e:
            logger.error(f"❌ Tablo oluşturma hatası: {e}")
            raise
    else:
        logger.info("✅ Tüm tablolar mevcut, veritabanı şeması güncel.")
    
    # Mevcut tablolar için kolon kontrollerini yap
    ensure_conversation_history_columns()
    ensure_user_avatar_column()
