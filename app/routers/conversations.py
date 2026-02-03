from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..dependencies import get_current_user

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("/", response_model=List[schemas.ConversationOut])
def list_conversations(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    """Kullanıcının tüm konuşmalarını listeler."""
    conversations = (
        db.query(models.Conversation)
        .filter(models.Conversation.user_id == current_user.id)
        .order_by(models.Conversation.created_at.desc())
        .all()
    )
    return conversations


@router.post("/", response_model=schemas.ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: schemas.ConversationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Alias boş bırakılıyor ki AI ilk mesajdan başlık oluştursun
    conversation = models.Conversation(
        title=payload.title or "Yeni Konuşma",  # Title varsayılan değer alabilir
        alias=payload.alias,  # Alias None olabilir, AI dolduracak
        history_json=[],
        user_id=current_user.id,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/{conversation_id}/messages", response_model=List[schemas.MessageOut])
def get_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Belirli bir konuşmanın mesajlarını getirir."""
    conversation = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == conversation_id,
            models.Conversation.user_id == current_user.id
        )
        .first()
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konuşma bulunamadı"
        )

    messages = (
        db.query(models.Message)
        .filter(models.Message.conversation_id == conversation_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )
    return messages


@router.delete("/{conversation_id}", status_code=status.HTTP_200_OK)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    convo = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == conversation_id,
            models.Conversation.user_id == current_user.id
        )
        .first()
    )
    if not convo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konuşma bulunamadı"
        )
    db.delete(convo)
    db.commit()
    return {"detail": "Konuşma silindi"}


@router.put("/{conversation_id}", response_model=schemas.ConversationOut)
def update_conversation(
    conversation_id: int,
    payload: schemas.ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Konuşma başlığını/alias'ını günceller."""
    convo = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.id == conversation_id,
            models.Conversation.user_id == current_user.id
        )
        .first()
    )
    if not convo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Konuşma bulunamadı"
        )
    
    if payload.title is not None:
        convo.title = payload.title
    if payload.alias is not None:
        convo.alias = payload.alias
    
    db.commit()
    db.refresh(convo)
    return convo
