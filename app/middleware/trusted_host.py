from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from app.core.config import settings

def setup_trusted_host(app: FastAPI):
    """Trusted Host middleware yapılandırmasını ekler."""
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]
    )
