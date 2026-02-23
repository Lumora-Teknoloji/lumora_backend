from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

def setup_cors(app: FastAPI):
    """CORS middleware yapılandırmasını ekler."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.cors_origins == "*" else settings.allowed_origins,
        allow_credentials=True,  # Required for HttpOnly cookies
        allow_methods=["*"],
        allow_headers=["*"],
    )
