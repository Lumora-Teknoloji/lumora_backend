from datetime import datetime
from typing import Optional
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
