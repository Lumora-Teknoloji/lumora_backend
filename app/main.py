import logging
from fastapi import FastAPI, Request
from socketio import ASGIApp
import asyncio

from .core.config import settings
from .api.v1.endpoints import auth, users, conversations, messages
from app.services.core.socket_manager import sio

# Middleware Imports
from .middleware.security import add_security_headers
from .middleware.rate_limit import setup_rate_limiting, limiter
from .middleware.cors import setup_cors
from .middleware.trusted_host import setup_trusted_host

# Core Modules
from .core.lifespan import lifespan
from .core.logging import setup_logging
from .core.static import mount_static_files
from .core.errors import add_exception_handlers

# Router Imports
from .routers.scraper_tasks import router as scraper_tasks_router
from .routers.scraper_bots import router as scraper_bots_router
from .routers.scraper_metrics import router as scraper_metrics_router
from .routers.scraper_ingest import router as scraper_ingest_router
from .routers.bot_commands import router as bot_commands_router
from .routers.products import router as products_router
from .routers.intelligence import router as intelligence_router
from .routers.dashboard import router as dashboard_router
from .routers.agents import router as agents_router
from .routers.redis_queue import router as redis_queue_router
from .routers.collections import router as collections_router

# Setup Logging
setup_logging()
logger = logging.getLogger(__name__)


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url="/redoc" if settings.app_env == "development" else None,
    lifespan=lifespan,
)

# Security Headers Middleware
app.middleware("http")(add_security_headers)

# Rate Limiting
setup_rate_limiting(app)

# Trusted Host Middleware
setup_trusted_host(app)

# CORS Middleware
setup_cors(app)

api_prefix = settings.api_prefix.rstrip("/")

app.include_router(auth.router, prefix=api_prefix)
app.include_router(users.router, prefix=api_prefix)
app.include_router(conversations.router, prefix=api_prefix)
app.include_router(messages.router, prefix=api_prefix)

# App Routers
app.include_router(scraper_tasks_router, prefix=api_prefix)
app.include_router(scraper_bots_router, prefix=api_prefix)
app.include_router(scraper_metrics_router, prefix=api_prefix)
app.include_router(scraper_ingest_router, prefix=api_prefix)
app.include_router(bot_commands_router, prefix=api_prefix)
app.include_router(products_router, prefix=api_prefix)
app.include_router(intelligence_router, prefix=api_prefix)
app.include_router(dashboard_router, prefix=api_prefix)
app.include_router(agents_router, prefix=api_prefix)
app.include_router(collections_router, prefix=api_prefix)

# Redis Queue Router (yeni stateless bot mimarisi)
app.include_router(redis_queue_router, prefix=f"{api_prefix}/redis")

# Debug routes only in development
if settings.app_env == "development":
    for route in app.routes:
        if hasattr(route, "path"):
            logger.debug(f"Route: {route.path}")

# Mount Static Files
mount_static_files(app)

# Socket.IO entegrasyonu
# Defined at the bottom of the file to capture all FastAPI routes.
app_asgi = app  # Keep backwards compatibility for run_server.py

# Exception Handlers
add_exception_handlers(app)


from sqlalchemy.orm import Session
from .core.database import get_db
from fastapi import Depends, Response

@app.get("/health")
async def health_check(response: Response, db: Session = Depends(get_db)):
    """Health check endpoint."""
    status_dict = {"status": "ok", "environment": settings.app_env, "dependencies": {}}
    
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        status_dict["dependencies"]["database"] = "ok"
    except Exception:
        status_dict["dependencies"]["database"] = "unreachable"
        status_dict["status"] = "degraded"
        
    try:
        from .routers.redis_queue import get_redis
        redis_conn = await get_redis()
        await redis_conn.ping()
        status_dict["dependencies"]["redis"] = "ok"
    except Exception:
        status_dict["dependencies"]["redis"] = "unreachable"
        status_dict["status"] = "degraded"
        
    if status_dict["status"] != "ok":
        response.status_code = 503
        
    return status_dict


# Wrap the final FastAPI app with Socket.IO ASGIApp
fastapi_app = app
app = ASGIApp(sio, fastapi_app)
app_asgi = app  # Keep backwards compatibility for run_server.py


# Server configuration for production deployment
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app_asgi",
        host="0.0.0.0",
        port=settings.port,
        limit_concurrency=settings.max_connections,  # DoS protection
        timeout_keep_alive=settings.connection_timeout,  # Connection timeout
        reload=settings.app_env == "development",
        proxy_headers=True,
        forwarded_allow_ips="*",
        log_level="info"
    )
