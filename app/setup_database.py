import logging
from .database import Base, engine

logger = logging.getLogger(__name__)


def setup_database():
    """Veritabanı tablolarını oluşturur."""
    Base.metadata.create_all(bind=engine)
    logger.info("Veritabanı tabloları başarıyla oluşturuldu")


if __name__ == "__main__":
    setup_database()

