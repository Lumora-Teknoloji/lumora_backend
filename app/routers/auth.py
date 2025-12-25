from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import models, schemas
from ..core.security import create_access_token, hash_password, verify_password
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["Auth"])

# Rate limiter for auth endpoints (stricter than global)
limiter = Limiter(key_func=get_remote_address)


@router.post("/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")  # Strict limit: 3 registration attempts per minute
def register(request: Request, user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    # Kullanıcı adı veya email kontrolü
    existing_user = (
        db.query(models.User)
        .filter(
            (models.User.username == user_in.username)
            | (models.User.email == user_in.email)
        )
        .first()
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kullanıcı adı veya email zaten kullanılıyor"
        )

    user = models.User(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=hash_password(user_in.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
@limiter.limit("5/minute")  # Strict limit: 5 login attempts per minute
def login(request: Request, payload: schemas.UserLogin, db: Session = Depends(get_db)):
    user = (
        db.query(models.User)
        .filter(models.User.username == payload.username)
        .first()
    )
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya şifre hatalı"
        )

    token = create_access_token({"sub": str(user.id)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": schemas.UserOut.model_validate(user)
    }

