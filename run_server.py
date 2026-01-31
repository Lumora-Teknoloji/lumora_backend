"""
FastAPI backend başlatma scripti.
"""
import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    # Socket.IO entegrasyonu ile birlikte çalışacak şekilde ayarlandı
    uvicorn.run(
        "app.main:app_asgi",
        host=settings.host,
        port=settings.port,
        reload=settings.app_env == "development",
        log_level="debug",
    )

