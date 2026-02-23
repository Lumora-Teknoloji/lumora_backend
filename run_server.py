
import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app_asgi",
        host=settings.host,
        port=settings.port,
        limit_concurrency=settings.max_connections,
        timeout_keep_alive=settings.connection_timeout,
        reload=settings.app_env == "development",
        log_level="info"
    )
