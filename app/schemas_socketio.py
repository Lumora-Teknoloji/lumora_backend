"""
Pydantic schemas for Socket.IO event validation.
"""
import html
from typing import Optional, Union
from pydantic import BaseModel, Field, field_validator


class UserMessageInput(BaseModel):
    """Validation schema for Socket.IO user_message event."""
    
    conversation_id: Union[int, str, None] = None
    message: str = Field(..., min_length=1, max_length=10000)
    image_url: Optional[str] = Field(None, max_length=2048)
    generate_images: bool = False
    
    @field_validator('message')
    @classmethod
    def sanitize_message(cls, v):
        """Sanitize HTML to prevent XSS attacks"""
        if v:
            return html.escape(v.strip())
        return v
    
    @field_validator('image_url')
    @classmethod
    def sanitize_image_url(cls, v):
        """Sanitize image URL"""
        if v:
            return html.escape(v.strip())
        return v


class GuestGetConversationInput(BaseModel):
    """Validation schema for Socket.IO guest_get_conversation event."""
    
    conversation_id: str = Field(..., min_length=1, max_length=100)
    
    @field_validator('conversation_id')
    @classmethod
    def sanitize_conversation_id(cls, v):
        """Sanitize conversation ID"""
        if v:
            return html.escape(v.strip())
        return v
