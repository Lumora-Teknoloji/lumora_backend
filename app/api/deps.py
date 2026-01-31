from fastapi import Depends, Header, HTTPException, status, Cookie
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.models import User
from app.core.security import decode_token


def get_token_from_cookie(access_token: Optional[str] = Cookie(None)) -> str:
    """Extract token from HttpOnly cookie."""
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - no access token cookie",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return access_token


def get_current_user(
    token: str = Depends(get_token_from_cookie), db: Session = Depends(get_db)
) -> User:
    """JWT token'dan kullanıcıyı alır ve döndürür."""
    payload = decode_token(token)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user = db.get(User, int(user_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz kullanıcı ID",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

