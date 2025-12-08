import logging
from sqlalchemy import text

from .database import Base, engine

logger = logging.getLogger(__name__)


def ensure_conversation_history_columns():
    """
    conversations tablosuna alias ve history_json kolonlarını ekler (varsa dokunmaz).
    Alembic kullanılmadığı için hafif bir guard ekliyoruz.
    """
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
        # messages tablosundaki image_url kolonunu TEXT tipine dönüştür
        try:
            conn.execute(
                text("ALTER TABLE messages ALTER COLUMN image_url TYPE TEXT")
            )
        except Exception as e:
            # Tablo henüz oluşmamış olabilir, hata vermeden devam et
            logger.info(f"image_url kolon tipi değiştirme uyarısı: {e}")


def setup_database():
    """Veritabanı tablolarını oluşturur."""
    ensure_conversation_history_columns()
    Base.metadata.create_all(bind=engine)
    logger.info("Veritabanı tabloları başarıyla oluşturuldu")


if __name__ == "__main__":
    setup_database()

