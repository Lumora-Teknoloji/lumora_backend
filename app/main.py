import logging
from sqlalchemy import text, inspect
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from socketio import ASGIApp

from .config import settings
from .database import Base, engine
from .routers import auth, users, conversations, messages
from .socketio_handler import sio, cleanup_old_guest_data
from fastapi.staticfiles import StaticFiles
import os

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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


def setup_database():
    """Veritabanı tablolarını oluşturur. Mevcut tabloları ve verileri korur."""
    # Önce tabloların varlığını kontrol et
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    required_tables = ["users", "conversations", "messages"]
    
    missing_tables = [table for table in required_tables if table not in existing_tables]
    
    if missing_tables:
        logger.info(f"Eksik tablolar tespit edildi: {missing_tables}. Oluşturuluyor...")
        Base.metadata.create_all(bind=engine)
        logger.info("Veritabanı tabloları başarıyla oluşturuldu")
    else:
        logger.info("Tüm tablolar mevcut, veritabanı kurulumu gerekmiyor")
    
    # Mevcut tablolar için kolon kontrollerini yap
    ensure_conversation_history_columns()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url="/redoc" if settings.app_env == "development" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = settings.api_prefix.rstrip("/")

app.include_router(auth.router, prefix=api_prefix)
app.include_router(users.router, prefix=api_prefix)
app.include_router(conversations.router, prefix=api_prefix)
app.include_router(messages.router, prefix=api_prefix)

# Static dosyalar için klasör (AI tarafından üretilen görseller için)
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Socket.IO entegrasyonu - Socket.IO'yu FastAPI uygulamasına mount ediyoruz
socketio_app = ASGIApp(sio, app)

# Ana uygulama Socket.IO app'i olacak (hem REST API hem Socket.IO desteği için)
app_asgi = socketio_app


# Startup event: Veritabanı kurulumu ve misafir verilerini temizleme görevini başlat
@app.on_event("startup")
async def startup_event():
    """Uygulama başladığında veritabanını kurar ve misafir verilerini temizleme görevini başlatır."""
    # Veritabanı tablolarını oluştur (mevcut veriler korunur)
    setup_database()
    
    # Misafir verilerini temizleme görevini başlat
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(cleanup_old_guest_data())
    logger.info("Guest data cleanup task started")


# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "environment": settings.app_env}

