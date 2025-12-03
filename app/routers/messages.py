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
    return message

