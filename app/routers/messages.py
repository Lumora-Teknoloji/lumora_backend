from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..dependencies import get_current_user

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.post("/", response_model=schemas.MessageOut, status_code=status.HTTP_201_CREATED)
def create_message(
    payload: schemas.MessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Yeni bir mesaj oluşturur."""
    # Konuşmanın kullanıcıya ait olduğunu kontrol et
    conversation = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == payload.conversation_id,
            models.Conversation.user_id == current_user.id
        )
        .first()
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konuşma bulunamadı"
        )

    message = models.Message(
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

