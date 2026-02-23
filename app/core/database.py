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

def ensure_admin_user():
    """Admin kullanıcısı yoksa oluşturur. Varsa dokunmaz."""
    if not check_table_exists("users"):
        return
    
    try:
        from app.models.user import User
        from app.core.security import hash_password
        
        db = SessionLocal()
        try:
            admin = db.query(User).filter(User.username == "admin").first()
            if not admin:
                admin = User(
                    username="admin",
                    email="admin@lumoraboutique.com",
                    hashed_password=hash_password("admin123"),
                    full_name="System Admin"
                )
                db.add(admin)
                db.commit()
                logger.info("✅ Admin kullanıcısı oluşturuldu (admin / admin123)")
            else:
                logger.info("✅ Admin kullanıcısı zaten mevcut.")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Admin kullanıcısı kontrol edilirken uyarı: {e}")


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
    metadata_tables = set(Base.metadata.tables.keys())
    
    logger.info(f"🔍 Veritabanı Şeması Kontrol Ediliyor...")
    logger.info(f"📋 Model Tanımları ({len(metadata_tables)}): {sorted(list(metadata_tables))}")
    logger.info(f"🗄️  Mevcut Tablolar ({len(existing_tables)}): {sorted(existing_tables)}")
    
    missing_tables = metadata_tables - set(existing_tables)
    
    if missing_tables:
        logger.warning(f"⚠️  Eksik Tablolar Tespit Edildi ({len(missing_tables)}): {missing_tables}")
        logger.info("🛠️  Tablolar oluşturuluyor...")
        try:
            Base.metadata.create_all(bind=engine)
            
            # Doğrulama Testi
            inspector = inspect(engine)
            new_tables = set(inspector.get_table_names())
            still_missing = metadata_tables - new_tables
            
            if still_missing:
                logger.error(f"❌ KRİTİK HATA: Tablolar oluşturulamadı: {still_missing}")
                raise RuntimeError(f"Tablo oluşturma başarısız: {still_missing}")
            
            logger.info("✅ Eksik tablolar başarıyla oluşturuldu.")
        except Exception as e:
            logger.error(f"❌ Tablo oluşturma sırasında hata: {e}")
            raise
    else:
        logger.info("✅ Tüm tablolar eksiksiz mevcut.")
    
    # Mevcut tablolar için kolon kontrollerini yap
    ensure_conversation_history_columns()
    ensure_user_avatar_column()
    
    # Generic Schema Sync (Eksik tablo/kolon otomatik tamamlama)
    sync_schema()
    
    # Admin kullanıcısını kontrol et/oluştur
    ensure_admin_user()

def sync_schema():
    """
    Tüm modelleri tarar ve veritabanında eksik olan kolonları otomatik oluşturur.
    Not: Bu basit bir migration sistemidir. Tip değişikliklerini veya silinen kolonları yönetmez.
    """
    logger.info("🔄 Schema Senkronizasyonu Başlatılıyor...")
    
    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names())
    
    # SQLAlchemy tiplerini PostgreSQL tiplerine map et
    from sqlalchemy.dialects.postgresql import JSONB, DOUBLE_PRECISION, TIMESTAMP, UUID
    from sqlalchemy import String, Integer, Boolean, Text, Float, DateTime, BigInteger
    
    def get_column_type(col):
        """SQLAlchemy kolon tipini SQL stringine çevirir."""
        try:
            # Tipin compile edilmiş halini al (dialect-specific)
            return col.type.compile(dialect=engine.dialect)
        except Exception:
            # Fallback (basit tipler)
            if isinstance(col.type, String): return f"VARCHAR({col.type.length})" if col.type.length else "VARCHAR"
            if isinstance(col.type, Integer): return "INTEGER"
            if isinstance(col.type, Boolean): return "BOOLEAN"
            if isinstance(col.type, Text): return "TEXT"
            if isinstance(col.type, Float): return "DOUBLE PRECISION"
            if isinstance(col.type, DateTime): return "TIMESTAMP WITH TIME ZONE"
            if isinstance(col.type, JSONB): return "JSONB"
            return "TEXT" # En güvenli fallback

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            for table_name, table in Base.metadata.tables.items():
                if table_name not in db_tables:
                    logger.info(f"➕ Tablo oluşturuluyor: {table_name}")
                    table.create(conn)
                    continue
                
                # Tablo var, kolonları kontrol et
                existing_columns = {c['name'] for c in inspector.get_columns(table_name)}
                
                for column in table.columns:
                    if column.name not in existing_columns:
                        col_type = get_column_type(column)
                        nullable = "NULL" if column.nullable else "NOT NULL"
                        default = ""
                        # Default değer basitleştirilmiş (karmaşık SQL fonksiyonları desteklenmeyebilir)
                        
                        alter_query = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}"
                        logger.info(f"🔧 Kolon ekleniyor: {table_name}.{column.name} ({col_type})")
                        conn.execute(text(alter_query))
                        
            transaction.commit()
            logger.info("✅ Schema senkronizasyonu tamamlandı.")
        except Exception as e:
            transaction.rollback()
            logger.error(f"❌ Schema senkronizasyon hatası: {e}")
