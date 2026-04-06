from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI

# Global Limiter instance — GÜVENLİK: default 60/dakika
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
    storage_uri="memory://",
)

# Kritik endpoint sınırları (decorator'da kullanılır)
RATE_LIMITS = {
    "auth_login": "5/minute",
    "auth_register": "3/minute",
    "scraper_ingest": "30/minute",
    "scraper_start": "5/minute",
    "scraper_stop": "5/minute",
    "agent_register": "10/minute",
    "agent_heartbeat": "60/minute",
    "agent_sync": "5/minute",
    "intelligence_analyze": "20/minute",
    "intelligence_trigger": "5/minute",
    "bot_commands": "30/minute",
}

def setup_rate_limiting(app: FastAPI):
    """Rate limiting yapılandırmasını uygulamaya ekler."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

