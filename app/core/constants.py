"""
Application-wide constants and enumerations.
Centralizes magic strings and provides type-safe options.
"""
from enum import Enum


class MessageSender(str, Enum):
    """Message sender types."""
    USER = "user"
    AI = "ai"


class ConversationType(str, Enum):
    """Conversation types."""
    GUEST = "guest"
    AUTHENTICATED = "authenticated"


class Environment(str, Enum):
    """Application environments."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


# Guest conversation settings
GUEST_DATA_TIMEOUT_MINUTES = 30
GUEST_CLEANUP_INTERVAL_MINUTES = 15

# AI Response settings
MAX_MESSAGE_LENGTH = 10000
MAX_CHAT_HISTORY_LENGTH = 50

# Database settings
DB_POOL_SIZE = 20
DB_MAX_OVERFLOW = 10
