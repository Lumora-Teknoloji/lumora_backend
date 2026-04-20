"""
Collections & Reactions Router — Ürün koleksiyonları ve beğen/beğenme sistemi

YouTube playlist tarzı koleksiyonlar + Instagram tarzı reaksiyonlar.
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.product_collection import ProductCollection, ProductCollectionItem, ProductReaction
from app.models.product import Product

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["Collections & Reactions"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CollectionCreate(BaseModel):
    name: str
    color: str = "#4cc9f0"
    icon: str = "folder"

class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None

class CollectionOut(BaseModel):
    id: int
    name: str
    color: str
    icon: str
    product_count: int = 0

class CollectionProductAdd(BaseModel):
    product_id: int

class ReactionRequest(BaseModel):
    product_id: int
    reaction: str  # "like" or "dislike"

class ReactionOut(BaseModel):
    product_id: int
    reaction: str


# ─── Collections CRUD ─────────────────────────────────────────────────────────

@router.get("")
def list_collections(db: Session = Depends(get_db)):
    """Kullanıcının tüm koleksiyonlarını listele."""
    # Basit — user_id=1 (admin) varsayıyoruz şimdilik
    collections = db.query(ProductCollection).filter(ProductCollection.user_id == 1).all()
    result = []
    for c in collections:
        count = db.query(ProductCollectionItem).filter(ProductCollectionItem.collection_id == c.id).count()
        result.append(CollectionOut(id=c.id, name=c.name, color=c.color, icon=c.icon, product_count=count))
    return result


@router.post("", status_code=201)
def create_collection(req: CollectionCreate, db: Session = Depends(get_db)):
    """Yeni koleksiyon oluştur."""
    c = ProductCollection(user_id=1, name=req.name, color=req.color, icon=req.icon)
    db.add(c)
    db.commit()
    db.refresh(c)
    return CollectionOut(id=c.id, name=c.name, color=c.color, icon=c.icon, product_count=0)


@router.put("/{collection_id}")
def update_collection(collection_id: int, req: CollectionUpdate, db: Session = Depends(get_db)):
    """Koleksiyon güncelle."""
    c = db.query(ProductCollection).filter(ProductCollection.id == collection_id, ProductCollection.user_id == 1).first()
    if not c:
        raise HTTPException(status_code=404, detail="Koleksiyon bulunamadı")
    if req.name is not None:
        c.name = req.name
    if req.color is not None:
        c.color = req.color
    if req.icon is not None:
        c.icon = req.icon
    db.commit()
    count = db.query(ProductCollectionItem).filter(ProductCollectionItem.collection_id == c.id).count()
    return CollectionOut(id=c.id, name=c.name, color=c.color, icon=c.icon, product_count=count)


@router.delete("/{collection_id}", status_code=204)
def delete_collection(collection_id: int, db: Session = Depends(get_db)):
    """Koleksiyon sil."""
    c = db.query(ProductCollection).filter(ProductCollection.id == collection_id, ProductCollection.user_id == 1).first()
    if not c:
        raise HTTPException(status_code=404, detail="Koleksiyon bulunamadı")
    db.delete(c)
    db.commit()


# ─── Collection Items ─────────────────────────────────────────────────────────

@router.get("/{collection_id}/products")
def list_collection_products(collection_id: int, db: Session = Depends(get_db)):
    """Koleksiyondaki ürünleri listele."""
    items = (
        db.query(ProductCollectionItem)
        .filter(ProductCollectionItem.collection_id == collection_id)
        .all()
    )
    product_ids = [item.product_id for item in items]
    if not product_ids:
        return []
    products = db.query(Product).filter(Product.id.in_(product_ids)).all()
    return products


@router.post("/{collection_id}/products", status_code=201)
def add_product_to_collection(collection_id: int, req: CollectionProductAdd, db: Session = Depends(get_db)):
    """Ürünü koleksiyona ekle."""
    # Koleksiyon var mı?
    c = db.query(ProductCollection).filter(ProductCollection.id == collection_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Koleksiyon bulunamadı")
    # Zaten ekli mi?
    existing = (
        db.query(ProductCollectionItem)
        .filter(ProductCollectionItem.collection_id == collection_id, ProductCollectionItem.product_id == req.product_id)
        .first()
    )
    if existing:
        return {"status": "already_exists"}
    item = ProductCollectionItem(collection_id=collection_id, product_id=req.product_id)
    db.add(item)
    db.commit()
    return {"status": "added"}


@router.delete("/{collection_id}/products/{product_id}", status_code=204)
def remove_product_from_collection(collection_id: int, product_id: int, db: Session = Depends(get_db)):
    """Ürünü koleksiyondan çıkar."""
    item = (
        db.query(ProductCollectionItem)
        .filter(ProductCollectionItem.collection_id == collection_id, ProductCollectionItem.product_id == product_id)
        .first()
    )
    if item:
        db.delete(item)
        db.commit()


# ─── Reactions ────────────────────────────────────────────────────────────────

@router.post("/reactions")
def toggle_reaction(req: ReactionRequest, db: Session = Depends(get_db)):
    """
    Ürüne beğen/beğenme reaksiyonu ver.
    Aynı reaksiyon tekrar gönderilirse kaldırılır (toggle).
    """
    existing = (
        db.query(ProductReaction)
        .filter(ProductReaction.user_id == 1, ProductReaction.product_id == req.product_id)
        .first()
    )
    if existing:
        if existing.reaction == req.reaction:
            # Aynı reaksiyon → kaldır
            db.delete(existing)
            db.commit()
            return {"status": "removed", "reaction": None}
        else:
            # Farklı reaksiyon → güncelle
            existing.reaction = req.reaction
            db.commit()
            return {"status": "updated", "reaction": req.reaction}
    else:
        r = ProductReaction(user_id=1, product_id=req.product_id, reaction=req.reaction)
        db.add(r)
        db.commit()
        return {"status": "added", "reaction": req.reaction}


@router.get("/reactions/all")
def list_all_reactions(db: Session = Depends(get_db)):
    """Kullanıcının tüm reaksiyonlarını getir."""
    reactions = db.query(ProductReaction).filter(ProductReaction.user_id == 1).all()
    return {r.product_id: r.reaction for r in reactions}
