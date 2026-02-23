from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
import os
import shutil
import uuid

from app.core.database import get_db
from app.models import Message, Conversation, User
from app.schemas.ai import MessageCreate, MessageOut, FileUploadOut
from app.api.deps import get_current_user
from app.core.exceptions import MessageNotFoundError, ForbiddenError, ConversationNotFoundError

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.post("/", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def create_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Yeni bir mesaj oluşturur."""
    # Konuşmanın kullanıcıya ait olduğunu kontrol et
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == payload.conversation_id,
            Conversation.user_id == current_user.id
        )
        .first()
    )
    if not conversation:
        raise ConversationNotFoundError(payload.conversation_id)

    message = Message(
        conversation_id=payload.conversation_id,
        sender=payload.sender,
        content=payload.content,
        image_url=payload.image_url,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    # Sohbet geçmişini JSON olarak güncelle
    history = conversation.history_json or []
    history.append(
        {
            "id": message.id,
            "sender": message.sender,
            "content": message.content,
            "image_url": message.image_url,
            "created_at": message.created_at.isoformat() if message.created_at else None,
        }
    )

    # İlk kullanıcı mesajı geldiyse otomatik takma ad üret
    if not conversation.alias and message.sender == "user":
        auto_alias = (message.content or "Sohbet").strip()
        if len(auto_alias) > 40:
            auto_alias = f"{auto_alias[:40]}..."
        conversation.alias = auto_alias or "Sohbet"

    conversation.history_json = history
    db.add(conversation)
    db.commit()
    db.refresh(message)
    return message


@router.post("/upload", response_model=FileUploadOut)
async def upload_message_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Mesajlar için dosya yükler."""
    
    # İzin verilen dosya tipleri
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".doc", ".docx"}
    extension = os.path.splitext(file.filename)[1].lower()
    
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Desteklenmeyen dosya formatı."
        )

    # Klasör kontrolü (Backend kök dizininde static/uploads)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Dosya ismi: user_id + uuid + ext
    filename = f"{current_user.id}_msg_{uuid.uuid4()}{extension}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dosya yüklenirken hata oluştu: {str(e)}"
        )
        
    return {"url": f"/static/uploads/{filename}"}

