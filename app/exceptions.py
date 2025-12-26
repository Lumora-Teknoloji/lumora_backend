"""
Custom exception classes for the application.
Provides user-friendly error messages and proper HTTP status codes.
"""
from typing import Any, Optional


class AppException(Exception):
    """Base exception for all application errors."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ConversationNotFoundError(AppException):
    """Raised when a conversation is not found."""
    
    def __init__(self, conversation_id: int | str):
        super().__init__(
            message=f"Konuşma bulunamadı (ID: {conversation_id})",
            status_code=404,
            details={"conversation_id": conversation_id}
        )


class MessageNotFoundError(AppException):
    """Raised when a message is not found."""
    
    def __init__(self, message_id: int):
        super().__init__(
            message=f"Mesaj bulunamadı (ID: {message_id})",
            status_code=404,
            details={"message_id": message_id}
        )


class UnauthorizedError(AppException):
    """Raised when user is not authenticated."""
    
    def __init__(self, message: str = "Giriş yapmanız gerekiyor"):
        super().__init__(
            message=message,
            status_code=401
        )


class ForbiddenError(AppException):
    """Raised when user doesn't have permission."""
    
    def __init__(self, message: str = "Bu işlem için yetkiniz yok"):
        super().__init__(
            message=message,
            status_code=403
        )


class ValidationError(AppException):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        details = {"field": field} if field else {}
        super().__init__(
            message=message,
            status_code=422,
            details=details
        )


class AIServiceError(AppException):
    """Raised when AI service fails."""
    
    def __init__(self, message: str = "AI servisi şu anda kullanılamıyor", service: Optional[str] = None):
        details = {"service": service} if service else {}
        super().__init__(
            message=message,
            status_code=503,
            details=details
        )


class DatabaseError(AppException):
    """Raised when database operation fails."""
    
    def __init__(self, message: str = "Veritabanı hatası oluştu"):
        super().__init__(
            message=message,
            status_code=500
        )
