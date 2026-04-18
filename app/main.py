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

# Scraper Router
from .routers.scraper import router as scraper_router
from .routers.bot_commands import router as bot_commands_router
from .routers.products import router as products_router
from .routers.intelligence import router as intelligence_router
from .routers.dashboard import router as dashboard_router
from .routers.agents import router as agents_router
app.include_router(scraper_router, prefix=api_prefix)
app.include_router(bot_commands_router, prefix=api_prefix)
app.include_router(products_router, prefix=api_prefix)
app.include_router(intelligence_router, prefix=api_prefix)
app.include_router(dashboard_router, prefix=api_prefix)
app.include_router(agents_router, prefix=api_prefix)

# Redis Queue Router (yeni stateless bot mimarisi)
from .routers.redis_queue import router as redis_queue_router
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


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "environment": settings.app_env}


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
