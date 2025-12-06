from fastapi import APIRouter, Depends, HTTPException, status

from .. import schemas, models
from ..dependencies import get_current_user
from ..models import User
from ..database import get_db
from ..core.security import verify_password, hash_password
from sqlalchemy.orm import Session

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=schemas.UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    payload: schemas.PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mevcut şifre hatalı"
        )
    current_user.hashed_password = hash_password(payload.new_password)
    db.add(current_user)
    db.commit()
    return {"detail": "Şifre güncellendi"}

