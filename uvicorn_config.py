"""
Uvicorn configuration with DoS protection (connection limits)
Run with: python uvicorn_config.py
"""
import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app_asgi",
        host="0.0.0.0",
        port=settings.port,
        limit_concurrency=settings.max_connections,  # Max concurrent connections
        timeout_keep_alive=settings.connection_timeout,  # Reduced timeout for DoS protection
        backlog=100,  # Connection backlog
        log_level="info"
    )
