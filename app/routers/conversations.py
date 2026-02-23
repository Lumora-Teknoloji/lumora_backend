from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Conversation, Message, User
from app.schemas.ai import ConversationCreate, ConversationUpdate, ConversationOut, ConversationWithMessages, MessageOut
from app.api.deps import get_current_user
from app.core.exceptions import ConversationNotFoundError, ForbiddenError

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("/", response_model=List[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """Kullanıcının tüm konuşmalarını listeler."""
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.desc())
        .all()
    )
    return conversations


@router.post("/", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Alias boş bırakılıyor ki AI ilk mesajdan başlık oluştursun
    conversation = Conversation(
        title=payload.title or "Yeni Konuşma",  # Title varsayılan değer alabilir
        alias=payload.alias,  # Alias None olabilir, AI dolduracak
        history_json=[],
        user_id=current_user.id,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/{conversation_id}/messages", response_model=List[MessageOut])
def get_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Belirli bir konuşmanın mesajlarını getirir."""
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        )
        .first()
    )
    if not conversation:
        raise ConversationNotFoundError(conversation_id)

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return messages


@router.delete("/{conversation_id}", status_code=status.HTTP_200_OK)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    convo = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        )
        .first()
    )
    if not convo:
        raise ConversationNotFoundError(conversation_id)
    db.delete(convo)
    db.commit()
    return {"detail": "Konuşma silindi"}


@router.put("/{conversation_id}", response_model=ConversationOut)
def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Konuşma başlığını/alias'ını günceller."""
    convo = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id
        )
        .first()
    )
    if not convo:
        raise ConversationNotFoundError(conversation_id)
    
    if payload.title is not None:
        convo.title = payload.title
    if payload.alias is not None:
        convo.alias = payload.alias
    
    db.commit()
    db.refresh(convo)
    return convo
