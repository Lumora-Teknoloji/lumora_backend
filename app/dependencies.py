from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from .database import get_db
from .models import User
from .core.security import decode_token


def get_token_header(authorization: Optional[str] = Header(None)) -> str:
    """Authorization header'dan token'ı çıkarır."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header eksik",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz authorization formatı. 'Bearer <token>' formatında olmalıdır.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization.split(" ", 1)[1]


def get_current_user(
    token: str = Depends(get_token_header), db: Session = Depends(get_db)
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

