from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

def setup_cors(app: FastAPI):
    """CORS middleware yapılandırmasını ekler."""
    # Note: allow_origins=["*"] + allow_credentials=True is rejected by browsers.
    # Always use explicit origins so HttpOnly cookies work correctly.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,  # Required for HttpOnly cookies
        allow_methods=["*"],
        allow_headers=["*"],
    )
