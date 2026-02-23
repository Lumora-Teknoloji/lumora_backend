from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI

# Global Limiter instance
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

def setup_rate_limiting(app: FastAPI):
    """Rate limiting yapılandırmasını uygulamaya ekler."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
