from .database import Base, engine


def setup_database():
    """Veritabanı tablolarını oluşturur."""
    Base.metadata.create_all(bind=engine)
    print("Veritabani tablolari basariyla olusturuldu!")


if __name__ == "__main__":
    setup_database()

