# app/routers/dashboard.py
"""
Dashboard API — Kullanıcıya özel ürün yönetimi, benzer ürün keşfi,
performans takibi ve istatistikler.

Tüm endpoint'ler get_current_user ile korunur → her kullanıcı sadece
kendi verilerini görür/düzenler.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models import User, Product, DailyMetric
from app.models.user_product import UserProduct

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class UserProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    category: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    attributes: Optional[dict] = None
    product_id: Optional[int] = None  # DB'deki Product ile eşleştirme


class UserProductUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=300)
    category: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    attributes: Optional[dict] = None
    performance_tag: Optional[str] = None
    performance_note: Optional[str] = None
    is_watching: Optional[bool] = None


class PerformanceTagUpdate(BaseModel):
    performance_tag: str = Field(..., pattern="^(bestseller|impactful|potential|flop)$")
    performance_note: Optional[str] = Field(None, max_length=500)


class UserProductOut(BaseModel):
    id: int
    user_id: int
    product_id: Optional[int] = None
    name: str
    category: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    attributes: Optional[dict] = None
    performance_tag: Optional[str] = None
    performance_note: Optional[str] = None
    is_watching: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # Linked product trend info (populated if product_id exists)
    trend_score: Optional[float] = None
    trend_direction: Optional[str] = None

    class Config:
        from_attributes = True


class SimilarProductOut(BaseModel):
    id: int
    product_code: Optional[str] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    last_price: Optional[float] = None
    trend_score: Optional[float] = None
    trend_direction: Optional[str] = None
    dominant_color: Optional[str] = None
    fabric_type: Optional[str] = None
    url: Optional[str] = None
    similarity_reason: Optional[str] = None

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total_products: int = 0
    watching_count: int = 0
    bestseller_count: int = 0
    impactful_count: int = 0
    potential_count: int = 0
    flop_count: int = 0
    trending_count: int = 0  # trend_score > 70 olan linked product sayısı
    avg_trend_score: Optional[float] = None


class WatchlistItem(BaseModel):
    id: int
    name: str
    category: Optional[str] = None
    image_url: Optional[str] = None
    performance_tag: Optional[str] = None
    # Live trend data from linked product
    trend_score: Optional[float] = None
    trend_direction: Optional[str] = None
    last_price: Optional[float] = None
    rank_change_1d: Optional[int] = None

    class Config:
        from_attributes = True


# ─── Helper ───────────────────────────────────────────────────────────────────

def _get_user_product_or_404(
    up_id: int, user: User, db: Session
) -> UserProduct:
    """Kullanıcının kendi ürününü döner veya 404."""
    up = (
        db.query(UserProduct)
        .filter(UserProduct.id == up_id, UserProduct.user_id == user.id)
        .first()
    )
    if not up:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    return up


def _enrich_with_trend(up: UserProduct, db: Session) -> dict:
    """UserProduct'ı trend verisiyle zenginleştirir."""
    data = {
        "id": up.id,
        "user_id": up.user_id,
        "product_id": up.product_id,
        "name": up.name,
        "category": up.category,
        "brand": up.brand,
        "price": up.price,
        "image_url": up.image_url,
        "description": up.description,
        "attributes": up.attributes,
        "performance_tag": up.performance_tag,
        "performance_note": up.performance_note,
        "is_watching": up.is_watching,
        "created_at": up.created_at.isoformat() if up.created_at else None,
        "updated_at": up.updated_at.isoformat() if up.updated_at else None,
        "trend_score": None,
        "trend_direction": None,
    }
    if up.product_id:
        product = db.query(Product).filter(Product.id == up.product_id).first()
        if product:
            data["trend_score"] = product.trend_score
            data["trend_direction"] = product.trend_direction
            if not data["image_url"]:
                data["image_url"] = product.image_url
    return data


# ─── CRUD Endpoints ──────────────────────────────────────────────────────────

@router.post("/products", response_model=UserProductOut, status_code=201)
def create_user_product(
    payload: UserProductCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kullanıcının dashboard'una yeni ürün ekler."""
    # Eğer product_id verilmişse, var mı kontrol et
    if payload.product_id:
        exists = db.query(Product).filter(Product.id == payload.product_id).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Bağlanmak istenen ürün DB'de bulunamadı")
    
    up = UserProduct(
        user_id=user.id,
        product_id=payload.product_id,
        name=payload.name,
        category=payload.category,
        brand=payload.brand,
        price=payload.price,
        image_url=payload.image_url,
        description=payload.description,
        attributes=payload.attributes,
    )
    db.add(up)
    db.commit()
    db.refresh(up)
    return _enrich_with_trend(up, db)


@router.get("/products", response_model=List[UserProductOut])
def list_user_products(
    category: Optional[str] = None,
    performance_tag: Optional[str] = None,
    watching_only: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kullanıcının kayıtlı ürünlerini listeler."""
    q = db.query(UserProduct).filter(UserProduct.user_id == user.id)

    if category:
        q = q.filter(UserProduct.category.ilike(f"%{category}%"))
    if performance_tag:
        q = q.filter(UserProduct.performance_tag == performance_tag)
    if watching_only:
        q = q.filter(UserProduct.is_watching == True)

    q = q.order_by(UserProduct.created_at.desc())
    items = q.all()
    return [_enrich_with_trend(up, db) for up in items]


@router.get("/products/{up_id}", response_model=UserProductOut)
def get_user_product(
    up_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kullanıcının tek ürün detayı."""
    up = _get_user_product_or_404(up_id, user, db)
    return _enrich_with_trend(up, db)


@router.put("/products/{up_id}", response_model=UserProductOut)
def update_user_product(
    up_id: int,
    payload: UserProductUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kullanıcının ürün bilgilerini günceller."""
    up = _get_user_product_or_404(up_id, user, db)
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(up, key, value)
    db.commit()
    db.refresh(up)
    return _enrich_with_trend(up, db)


@router.delete("/products/{up_id}", status_code=204)
def delete_user_product(
    up_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kullanıcının ürününü siler."""
    up = _get_user_product_or_404(up_id, user, db)
    db.delete(up)
    db.commit()
    return None


# ─── Performance Tagging ─────────────────────────────────────────────────────

@router.patch("/products/{up_id}/tag", response_model=UserProductOut)
def update_performance_tag(
    up_id: int,
    payload: PerformanceTagUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ürüne performans etiketi atar (bestseller/impactful/potential/flop)."""
    up = _get_user_product_or_404(up_id, user, db)
    up.performance_tag = payload.performance_tag
    up.performance_note = payload.performance_note
    db.commit()
    db.refresh(up)
    return _enrich_with_trend(up, db)


# ─── Similar Product Discovery ───────────────────────────────────────────────

@router.get("/products/{up_id}/similar", response_model=List[SimilarProductOut])
def find_similar_products(
    up_id: int,
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Kullanıcının ürününe benzer ürünleri DB'den bulur.
    Eşleştirme kriterleri:
      1. Aynı kategori
      2. Benzer renk / kumaş / kalıp
      3. Fiyat aralığı yakınlığı (±%30)
      4. Trend skoru bazlı sıralama
    """
    up = _get_user_product_or_404(up_id, user, db)

    # Temel sorgu — product tablosundan
    q = db.query(Product)

    # Kendi bağlı ürününü hariç tut
    if up.product_id:
        q = q.filter(Product.id != up.product_id)

    # Kategori filtresi
    filters = []
    similarity_parts = []

    if up.category:
        filters.append(Product.category.ilike(f"%{up.category}%"))
        similarity_parts.append("aynı kategori")

    # Özellik eşleştirme (attributes JSONB)
    attrs = up.attributes or {}
    color = attrs.get("renk") or attrs.get("color")
    fabric = attrs.get("kumaş") or attrs.get("fabric")

    if color:
        filters.append(Product.dominant_color.ilike(f"%{color}%"))
    if fabric:
        filters.append(Product.fabric_type.ilike(f"%{fabric}%"))

    # Fiyat aralığı (±%30)
    if up.price and up.price > 0:
        low = up.price * 0.7
        high = up.price * 1.3
        filters.append(Product.last_price.between(low, high))
        similarity_parts.append(f"fiyat aralığı ({low:.0f}-{high:.0f}₺)")

    # En az bir filtre olmalı
    if not filters and up.category:
        filters.append(Product.category.ilike(f"%{up.category}%"))

    if filters:
        q = q.filter(or_(*filters))

    # Trend skoru ile sırala (yüksekten düşüğe)
    q = q.order_by(Product.trend_score.desc().nullslast())
    products = q.limit(limit).all()

    reason = ", ".join(similarity_parts) if similarity_parts else "genel eşleştirme"

    return [
        SimilarProductOut(
            id=p.id,
            product_code=p.product_code,
            name=p.name,
            brand=p.brand,
            category=p.category,
            image_url=p.image_url,
            last_price=p.last_price,
            trend_score=p.trend_score,
            trend_direction=p.trend_direction,
            dominant_color=p.dominant_color,
            fabric_type=p.fabric_type,
            url=p.url,
            similarity_reason=reason,
        )
        for p in products
    ]


# ─── Dashboard Stats ─────────────────────────────────────────────────────────

@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kullanıcının dashboard istatistikleri."""
    base = db.query(UserProduct).filter(UserProduct.user_id == user.id)

    total = base.count()
    watching = base.filter(UserProduct.is_watching == True).count()
    bestseller = base.filter(UserProduct.performance_tag == "bestseller").count()
    impactful = base.filter(UserProduct.performance_tag == "impactful").count()
    potential = base.filter(UserProduct.performance_tag == "potential").count()
    flop = base.filter(UserProduct.performance_tag == "flop").count()

    # Trend olan linked product sayısı
    trending = (
        base.join(Product, UserProduct.product_id == Product.id)
        .filter(Product.trend_score > 70)
        .count()
    )

    # Ortalama trend skoru
    avg_score = (
        db.query(func.avg(Product.trend_score))
        .join(UserProduct, UserProduct.product_id == Product.id)
        .filter(UserProduct.user_id == user.id)
        .scalar()
    )

    return DashboardStats(
        total_products=total,
        watching_count=watching,
        bestseller_count=bestseller,
        impactful_count=impactful,
        potential_count=potential,
        flop_count=flop,
        trending_count=trending,
        avg_trend_score=round(avg_score, 1) if avg_score else None,
    )


# ─── Watchlist ────────────────────────────────────────────────────────────────

@router.get("/watchlist", response_model=List[WatchlistItem])
def get_watchlist(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kullanıcının takip ettiği ürünlerin anlık trend durumu."""
    items = (
        db.query(UserProduct)
        .filter(UserProduct.user_id == user.id, UserProduct.is_watching == True)
        .order_by(UserProduct.created_at.desc())
        .all()
    )

    result = []
    for up in items:
        entry = {
            "id": up.id,
            "name": up.name,
            "category": up.category,
            "image_url": up.image_url,
            "performance_tag": up.performance_tag,
            "trend_score": None,
            "trend_direction": None,
            "last_price": up.price,
            "rank_change_1d": None,
        }
        if up.product_id:
            product = db.query(Product).filter(Product.id == up.product_id).first()
            if product:
                entry["trend_score"] = product.trend_score
                entry["trend_direction"] = product.trend_direction
                entry["last_price"] = product.last_price or up.price
                # Son rank değişimi
                last_metric = (
                    db.query(DailyMetric)
                    .filter(DailyMetric.product_id == product.id)
                    .order_by(DailyMetric.recorded_at.desc())
                    .first()
                )
                if last_metric:
                    entry["rank_change_1d"] = last_metric.rank_change_1d
        result.append(WatchlistItem(**entry))

    return result
