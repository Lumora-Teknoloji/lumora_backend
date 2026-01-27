from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
import os
import shutil
import uuid

from .. import schemas, models
from ..dependencies import get_current_user
from ..models import User
from ..database import get_db
from ..core.security import verify_password, hash_password

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


@router.post("/avatar", response_model=schemas.UserOut)
def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Kullanıcı avatarını yükler."""
    
    # İzin verilen dosya tipleri
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    extension = os.path.splitext(file.filename)[1].lower()
    
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Desteklenmeyen dosya formatı. (jpg, png, gif, webp)"
        )

    # Klasör kontrolü (Backend kök dizininde static/avatars)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    UPLOAD_DIR = os.path.join(BASE_DIR, "static", "avatars")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Dosya ismi: user_id + uuid + ext
    filename = f"{current_user.id}_{uuid.uuid4()}{extension}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dosya yüklenirken hata oluştu: {str(e)}"
        )
        
    # URL oluştur (Frontend backend URL'inin sonuna ekleyecek)
    # Örn: /static/avatars/1_uuid.jpg
    avatar_url = f"/static/avatars/{filename}"
    
    current_user.avatar_url = avatar_url
    db.commit()
    db.refresh(current_user)
    
    return current_user
