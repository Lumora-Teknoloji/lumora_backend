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


def ensure_vector_extension() -> bool:
    """pgvector eklentisinin yüklü olduğundan emin olur. Başarılıysa True döner."""
    import os
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("✅ vector eklentisi kontrol edildi")
            os.environ["PGVECTOR_AVAILABLE"] = "1"
            return True
    except Exception as e:
        logger.warning(f"⚠️ pgvector eklentisi yüklenemedi (lokal geliştirmede normal): {e}")
        os.environ["PGVECTOR_AVAILABLE"] = "0"
        return False

def ensure_admin_user():
    """Admin kullanıcısı yoksa oluşturur. Varsa dokunmaz."""
    if not check_table_exists("users"):
        return
    
    try:
        from app.models.user import User
        from app.core.security import hash_password
        import uuid
        
        db = SessionLocal()
        try:
            admin = db.query(User).filter(User.username == "admin").first()
            if not admin:
                # Şifreyi env variable'dan al, yoksa random UUID üret (güvenli default)
                admin_password = os.environ.get("ADMIN_INITIAL_PASSWORD", "")
                if not admin_password:
                    admin_password = uuid.uuid4().hex[:16]
                    logger.warning(f"⚠️ ADMIN_INITIAL_PASSWORD env yok — rastgele şifre üretildi: {admin_password}")
                
                admin = User(
                    username="admin",
                    email="admin@lumoraboutique.com",
                    hashed_password=hash_password(admin_password),
                    full_name="System Admin"
                )
                db.add(admin)
                db.commit()
                logger.info("✅ Admin kullanıcısı oluşturuldu")
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
    has_pgvector = ensure_vector_extension()
    
    # pgvector varsa feature_vector kolonunu Product modeline ekle
    if has_pgvector:
        try:
            from app.models.product import _add_vector_column
            _add_vector_column()
        except Exception as e:
            logger.warning(f"feature_vector kolonu eklenemedi: {e}")

    try:
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
    except Exception as e:
        logger.error(f"setup_database hatası: {e}")
        raise

def sync_schema():
    """
    Tüm modelleri tarar ve veritabanında eksik olan tablo, kolon, index ve FK'ları otomatik oluşturur.
    Başlangıçta çalışır ve detaylı bir rapor çıkarır.
    """
    logger.info("🔄 Schema Senkronizasyonu Başlatılıyor...")
    
    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names())
    
    # İstatistik sayaçları
    stats = {
        "tables_created": [],
        "columns_added": [],
        "indexes_created": [],
        "defaults_set": [],
        "constraints_fixed": [],
        "errors": [],
    }
    
    # SQLAlchemy tiplerini PostgreSQL tiplerine map et
    from sqlalchemy import String, Integer, Boolean, Text, Float, DateTime, BigInteger
    
    def get_column_type(col):
        """SQLAlchemy kolon tipini SQL stringine çevirir."""
        try:
            return col.type.compile(dialect=engine.dialect)
        except Exception:
            if isinstance(col.type, String): return f"VARCHAR({col.type.length})" if col.type.length else "VARCHAR"
            if isinstance(col.type, Integer): return "INTEGER"
            if isinstance(col.type, Boolean): return "BOOLEAN"
            if isinstance(col.type, Text): return "TEXT"
            if isinstance(col.type, Float): return "DOUBLE PRECISION"
            if isinstance(col.type, DateTime): return "TIMESTAMP WITH TIME ZONE"
            return "TEXT"

    def get_default_clause(column):
        """Kolon için SQL default değerini döndürür."""
        if column.server_default is not None:
            return str(column.server_default.arg)
        if column.default is not None:
            val = column.default.arg
            if callable(val):
                return None  # Callable defaults (like list) can't be set as SQL defaults
            if isinstance(val, bool):
                return "TRUE" if val else "FALSE"
            if isinstance(val, (int, float)):
                return str(val)
            if isinstance(val, str):
                return f"'{val}'"
        return None

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            for table_name, table in Base.metadata.tables.items():
                # ──── 1. Eksik Tabloları Oluştur ────
                if table_name not in db_tables:
                    logger.info(f"➕ Tablo oluşturuluyor: {table_name}")
                    table.create(conn)
                    stats["tables_created"].append(table_name)
                    continue
                
                # ──── 2. Eksik Kolonları Ekle ────
                existing_columns = {c['name'] for c in inspector.get_columns(table_name)}
                
                for column in table.columns:
                    if column.name not in existing_columns:
                        col_type = get_column_type(column)
                        # Güvenlik: Yeni kolon her zaman NULLABLE olsun (mevcut satırları kırmaması için)
                        alter_query = f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {col_type}'
                        
                        logger.info(f"🔧 Kolon ekleniyor: {table_name}.{column.name} ({col_type})")
                        conn.execute(text(alter_query))
                        stats["columns_added"].append(f"{table_name}.{column.name}")
                        
                        # Default değer varsa ayarla
                        default_val = get_default_clause(column)
                        if default_val:
                            try:
                                default_query = f'ALTER TABLE "{table_name}" ALTER COLUMN "{column.name}" SET DEFAULT {default_val}'
                                conn.execute(text(default_query))
                                stats["defaults_set"].append(f"{table_name}.{column.name} = {default_val}")
                            except Exception as e:
                                logger.warning(f"⚠️  Default ayarlanamadı {table_name}.{column.name}: {e}")
                
                # ──── 3. Eksik Index'leri Oluştur ────
                existing_indexes = {idx['name'] for idx in inspector.get_indexes(table_name)}
                for index in table.indexes:
                    if index.name and index.name not in existing_indexes:
                        try:
                            index_cols = ", ".join([f'"{c.name}"' for c in index.columns])
                            unique = "UNIQUE " if index.unique else ""
                            create_idx = f'CREATE {unique}INDEX IF NOT EXISTS "{index.name}" ON "{table_name}" ({index_cols})'
                            conn.execute(text(create_idx))
                            stats["indexes_created"].append(f"{index.name} on {table_name}")
                            logger.info(f"📇 Index oluşturuldu: {index.name} on {table_name}")
                        except Exception as e:
                            logger.warning(f"⚠️  Index oluşturulamadı {index.name}: {e}")
                
                # ──── 4. FK Constraint Kontrolü ────
                existing_fks = inspector.get_foreign_keys(table_name)
                existing_fk_cols = {fk['constrained_columns'][0] for fk in existing_fks if fk['constrained_columns']}
                
                for column in table.columns:
                    for fk in column.foreign_keys:
                        if column.name not in existing_fk_cols:
                            try:
                                ref_table, ref_col = str(fk.column).split(".")
                                fk_name = f"fk_{table_name}_{column.name}_{ref_table}"
                                fk_query = f'ALTER TABLE "{table_name}" ADD CONSTRAINT "{fk_name}" FOREIGN KEY ("{column.name}") REFERENCES "{ref_table}"("{ref_col}")'
                                conn.execute(text(fk_query))
                                stats["constraints_fixed"].append(f"{table_name}.{column.name} → {ref_table}.{ref_col}")
                                logger.info(f"🔗 FK eklendi: {table_name}.{column.name} → {ref_table}.{ref_col}")
                            except Exception as e:
                                # FK zaten varsa veya başka bir sorun
                                logger.debug(f"FK kontrol: {table_name}.{column.name}: {e}")

            transaction.commit()
            
            # ──── SONUÇ RAPORU ────
            total_changes = sum(len(v) for v in stats.values())
            
            if total_changes == 0:
                logger.info("✅ Schema senkronizasyonu tamamlandı — değişiklik gerekmiyor, tüm şema güncel.")
            else:
                logger.info("=" * 60)
                logger.info("📊 SCHEMA SENKRONIZASYON RAPORU")
                logger.info("=" * 60)
                
                if stats["tables_created"]:
                    logger.info(f"  ➕ Oluşturulan Tablolar ({len(stats['tables_created'])}): {', '.join(stats['tables_created'])}")
                if stats["columns_added"]:
                    logger.info(f"  🔧 Eklenen Kolonlar ({len(stats['columns_added'])}): {', '.join(stats['columns_added'])}")
                if stats["defaults_set"]:
                    logger.info(f"  📌 Ayarlanan Default Değerler ({len(stats['defaults_set'])}): {', '.join(stats['defaults_set'])}")
                if stats["indexes_created"]:
                    logger.info(f"  📇 Oluşturulan Index'ler ({len(stats['indexes_created'])}): {', '.join(stats['indexes_created'])}")
                if stats["constraints_fixed"]:
                    logger.info(f"  🔗 Eklenen FK Constraint'ler ({len(stats['constraints_fixed'])}): {', '.join(stats['constraints_fixed'])}")
                if stats["errors"]:
                    logger.warning(f"  ❌ Hatalar ({len(stats['errors'])}): {', '.join(stats['errors'])}")
                
                logger.info("=" * 60)
                logger.info(f"✅ Toplam {total_changes} değişiklik uygulandı.")
                
        except Exception as e:
            transaction.rollback()
            logger.error(f"❌ Schema senkronizasyon hatası: {e}")

