from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from jwt import PyJWTError
import jwt, bcrypt
from fastapi import HTTPException, status
from .config import settings


def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_passwd = bcrypt.hashpw(pwd_bytes, salt)
    #veri tabanına kaydetmek için decode ediyoruz str olarak
    return hashed_passwd.decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    pwd_bytes = password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(pwd_bytes, hashed_bytes)

def create_access_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def set_auth_cookie(response, token: str):
    """Set JWT token as HttpOnly cookie for XSS protection"""
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,  # Prevents JavaScript access (XSS protection)
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",  # CSRF protection
        max_age=settings.access_token_expire_minutes * 60,
        path="/"
    )


def clear_auth_cookie(response):
    """Clear authentication cookie on logout"""
    response.delete_cookie(key="access_token", path="/")

