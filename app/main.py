import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from socketio import ASGIApp

from .config import settings
from .database import Base, engine
from .setup_database import ensure_conversation_history_columns
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

# Veritabanı tablolarını oluştur (sadece development için)
if settings.app_env == "development":
    ensure_conversation_history_columns()
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")

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


# Startup event: Misafir verilerini temizleme görevini başlat
@app.on_event("startup")
async def startup_event():
    """Uygulama başladığında misafir verilerini temizleme görevini başlatır."""
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

