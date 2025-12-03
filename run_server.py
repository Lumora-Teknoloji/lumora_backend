"""
FastAPI backend başlatma scripti.
"""
import uvicorn
from app.config import settings

if __name__ == "__main__":
    # Socket.IO entegrasyonu ile birlikte çalışacak şekilde ayarlandı
    uvicorn.run(
        "app.main:app_asgi",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.app_env == "development",
        log_level="info",
    )

