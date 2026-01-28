from datetime import datetime
from typing import List, Optional
import html

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    
    @field_validator('username', 'full_name')
    @classmethod
    def sanitize_html(cls, v):
        """Sanitize HTML to prevent XSS attacks"""
        if v:
            return html.escape(v)
        return v


class UserCreate(UserBase):
    password: str = Field(min_length=6)


class UserLogin(BaseModel):
    username: str
    password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class UserOut(UserBase):
    id: int
    created_at: datetime
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ConversationCreate(BaseModel):
    title: Optional[str] = None
    alias: Optional[str] = None
    
    @field_validator('title', 'alias')
    @classmethod
    def sanitize_html(cls, v):
        """Sanitize HTML to prevent XSS attacks"""
        if v:
            return html.escape(v)
        return v


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    alias: Optional[str] = None
    
    @field_validator('title', 'alias')
    @classmethod
    def sanitize_html(cls, v):
        """Sanitize HTML to prevent XSS attacks"""
        if v:
            return html.escape(v)
        return v


class ConversationOut(BaseModel):
    id: int
    title: Optional[str]
    alias: Optional[str]
    history_json: Optional[List[dict]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    conversation_id: int
    sender: str
    content: Optional[str] = None
    image_url: Optional[str] = None
    
    @field_validator('sender', 'content')
    @classmethod
    def sanitize_html(cls, v):
        """Sanitize HTML to prevent XSS attacks"""
        if v:
            return html.escape(v)
        return v


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    sender: str
    content: Optional[str]
    image_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationWithMessages(ConversationOut):
    messages: List[MessageOut] = []


class FileUploadOut(BaseModel):
    url: str

