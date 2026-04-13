# app/routers/products.py
"""
Products API — Scraper verileriyle dış erişim.
Filtreleme, sıralama, pagination destekli.
"""
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models.product import Product
from app.models.daily_metric import DailyMetric
from app.models.scraping_task import ScrapingTask
from app.models.user_product import UserProduct
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/products", tags=["Products"])


# Staleness trigger cooldown — en fazla saatte 1 Intelligence tetikle
_last_staleness_trigger = None
STALENESS_TRIGGER_COOLDOWN_MIN = 60



# ==================== SCHEMAS ====================

class ProductOut(BaseModel):
    id: int
    product_code: Optional[str] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    seller: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    category_tag: Optional[str] = None
    category: Optional[str] = None
    attributes: Optional[dict] = None
    review_summary: Optional[str] = None
    sizes: Optional[list] = None
    last_price: Optional[float] = None
    last_discount_rate: Optional[float] = None
    avg_sales_velocity: Optional[float] = None
    first_seen_at: Optional[datetime] = None
    last_scraped_at: Optional[datetime] = None
    # Latest metrics
    favorite_count: Optional[int] = None
    cart_count: Optional[int] = None
    view_count: Optional[int] = None
    avg_rating: Optional[float] = None
    rating_count: Optional[int] = None
    qa_count: Optional[int] = None
    # Price details from DailyMetric
    original_price: Optional[float] = None
    discounted_price: Optional[float] = None
    # Search ranking from DailyMetric
    page_number: Optional[int] = None
    search_rank: Optional[int] = None
    absolute_rank: Optional[int] = None
    search_term: Optional[str] = None
    # Bot info
    bot_mode: Optional[str] = None
    task_name: Optional[str] = None
    scrape_mode: Optional[str] = None  # api, dom, speed

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    items: List[ProductOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class DataQualityResponse(BaseModel):
    total_products: int
    seller_filled: int
    seller_pct: float
    attributes_filled: int
    attributes_pct: float
    image_filled: int
    image_pct: float
    review_summary_filled: int
    review_summary_pct: float
    sizes_filled: int
    sizes_pct: float
    avg_rating_filled: int
    avg_rating_pct: float
    cart_filled: int
    cart_pct: float
    favorite_filled: int
    favorite_pct: float


# ==================== ENDPOINTS ====================

@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    brand: Optional[str] = None,
    seller: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_rating: Optional[float] = None,
    search: Optional[str] = None,
    sort_by: str = Query("last_scraped_at", enum=["last_scraped_at", "last_price", "name", "brand", "avg_sales_velocity"]),
    sort_order: str = Query("desc", enum=["asc", "desc"]),
    task_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Ürünleri listele — filtreleme, sıralama, pagination destekli."""
    query = db.query(Product)

    # ── Staleness Guard: 6 saatten eski score varsa Intelligence'ı tetikle ──
    # Mevcut istek anında döner — yeniden hesaplama arka planda olur
    # Cooldown: saatte 1 kez tetikle (yüksek trafikte spam önleme)
    try:
        from datetime import datetime, timezone, timedelta
        global _last_staleness_trigger
        now = datetime.now(timezone.utc)
        cooldown_ok = (
            _last_staleness_trigger is None or
            (now - _last_staleness_trigger).total_seconds() / 60 >= STALENESS_TRIGGER_COOLDOWN_MIN
        )
        if cooldown_ok:
            from sqlalchemy import text as _text
            stale_count = db.execute(_text(
                "SELECT COUNT(*) FROM products WHERE last_scored_at IS NULL "
                "OR last_scored_at < NOW() - INTERVAL '6 hours'"
            )).scalar() or 0
            if stale_count > 0:
                import threading, urllib.request, json as _json
                from app.core.config import settings as _cfg
                _url = f"{_cfg.intelligence_url}/trigger"
                _last_staleness_trigger = now
                def _retrigger():
                    try:
                        body = _json.dumps({"scope": "all", "priority": "low"}).encode()
                        req = urllib.request.Request(
                            _url, data=body,
                            headers={"Content-Type": "application/json"})
                        urllib.request.urlopen(req, timeout=4).read()
                    except Exception:
                        pass
                threading.Thread(target=_retrigger, daemon=True, name="ScoreStalenessCheck").start()
    except Exception:
        pass  # DB hatası → ürünleri yine de listele

    # Filters
    if brand:
        query = query.filter(Product.brand.ilike(f"%{brand}%"))
    if seller:
        query = query.filter(Product.seller.ilike(f"%{seller}%"))
    if min_price is not None:
        query = query.filter(Product.last_price >= min_price)
    if max_price is not None:
        query = query.filter(Product.last_price <= max_price)
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    if task_id is not None:
        query = query.filter(Product.task_id == task_id)
    
    # Total count
    total = query.count()
    
    # Sort
    sort_col = getattr(Product, sort_by, Product.last_scraped_at)
    if sort_order == "desc":
        query = query.order_by(desc(sort_col))
    else:
        query = query.order_by(asc(sort_col))
    
    # Pagination
    offset = (page - 1) * page_size
    products = query.offset(offset).limit(page_size).all()
    
    # Build response with latest metrics
    items = []
    for p in products:
        latest_metric = db.query(DailyMetric).filter(
            DailyMetric.product_id == p.id
        ).order_by(desc(DailyMetric.recorded_at)).first()
        
        # Get bot mode from ScrapingTask
        task_obj = db.query(ScrapingTask).filter(ScrapingTask.id == p.task_id).first() if p.task_id else None
        bot_mode = None
        t_name = None
        if task_obj:
            bot_mode = task_obj.search_params.get("mode", "normal") if task_obj.search_params else "normal"
            t_name = task_obj.task_name

        item = ProductOut(
            id=p.id,
            product_code=p.product_code,
            name=p.name,
            brand=p.brand,
            seller=p.seller,
            url=p.url,
            image_url=p.image_url,
            category_tag=p.category_tag,
            category=p.category,
            attributes=p.attributes,
            review_summary=p.review_summary,
            sizes=p.sizes,
            last_price=p.last_price,
            last_discount_rate=p.last_discount_rate,
            avg_sales_velocity=p.avg_sales_velocity,
            first_seen_at=p.first_seen_at,
            last_scraped_at=p.last_scraped_at,
            favorite_count=latest_metric.favorite_count if latest_metric else None,
            cart_count=latest_metric.cart_count if latest_metric else None,
            view_count=latest_metric.view_count if latest_metric else None,
            avg_rating=latest_metric.avg_rating if latest_metric else None,
            rating_count=latest_metric.rating_count if latest_metric else None,
            qa_count=latest_metric.qa_count if latest_metric else None,
            original_price=latest_metric.price if latest_metric else None,
            discounted_price=latest_metric.discounted_price if latest_metric else None,
            page_number=latest_metric.page_number if latest_metric else None,
            search_rank=latest_metric.search_rank if latest_metric else None,
            absolute_rank=latest_metric.absolute_rank if latest_metric else None,
            search_term=latest_metric.search_term if latest_metric else None,
            bot_mode=bot_mode,
            task_name=t_name,
            scrape_mode=getattr(latest_metric, 'scrape_mode', None) if latest_metric else None,
        )
        items.append(item)
    
    total_pages = (total + page_size - 1) // page_size
    
    return ProductListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/quality", response_model=DataQualityResponse)
async def get_data_quality(db: Session = Depends(get_db)):
    """Veri kalitesi istatistikleri — admin panel için."""
    from sqlalchemy import text
    
    result = db.execute(text("""
        SELECT 
            COUNT(*) AS total,
            COUNT(NULLIF(seller, '')) AS seller_ok,
            COUNT(attributes) FILTER (WHERE attributes IS NOT NULL 
                AND attributes::text NOT IN ('{}', 'null', '[]')) AS attrs_ok,
            COUNT(NULLIF(image_url, '')) AS image_ok,
            COUNT(NULLIF(review_summary, '')) AS summary_ok,
            COUNT(sizes) FILTER (WHERE sizes IS NOT NULL 
                AND sizes::text NOT IN ('null', '[]')) AS sizes_ok
        FROM products
    """)).fetchone()
    
    total = result[0] or 1  # avoid division by zero
    
    # Metrics quality from daily_metrics
    metrics = db.execute(text("""
        SELECT 
            COUNT(DISTINCT dm.product_id) FILTER (WHERE dm.avg_rating > 0) AS rating_ok,
            COUNT(DISTINCT dm.product_id) FILTER (WHERE dm.cart_count > 0) AS cart_ok,
            COUNT(DISTINCT dm.product_id) FILTER (WHERE dm.favorite_count > 0) AS fav_ok
        FROM daily_metrics dm
        INNER JOIN (
            SELECT product_id, MAX(recorded_at) AS max_date
            FROM daily_metrics GROUP BY product_id
        ) latest ON dm.product_id = latest.product_id AND dm.recorded_at = latest.max_date
    """)).fetchone()
    
    pct = lambda x: round(x / total * 100, 1)
    
    return DataQualityResponse(
        total_products=total,
        seller_filled=result[1], seller_pct=pct(result[1]),
        attributes_filled=result[2], attributes_pct=pct(result[2]),
        image_filled=result[3], image_pct=pct(result[3]),
        review_summary_filled=result[4], review_summary_pct=pct(result[4]),
        sizes_filled=result[5], sizes_pct=pct(result[5]),
        avg_rating_filled=metrics[0], avg_rating_pct=pct(metrics[0]),
        cart_filled=metrics[1], cart_pct=pct(metrics[1]),
        favorite_filled=metrics[2], favorite_pct=pct(metrics[2]),
    )


# ==================== PRODUCTION LIST ====================

class ProductionListOut(BaseModel):
    """Kullanıcının üretim listesindeki bir kayıt."""
    list_id: int
    product_id: int
    added_at: Optional[datetime] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    last_price: Optional[float] = None
    trend_direction: Optional[str] = None
    trend_score: Optional[float] = None

    class Config:
        from_attributes = True


@router.get("/production-list", response_model=List[ProductionListOut])
def get_production_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Kullanıcının üretim listesini döner."""
    rows = (
        db.query(UserProduct)
        .filter(UserProduct.user_id == current_user.id, UserProduct.product_id != None)
        .order_by(desc(UserProduct.created_at))
        .all()
    )
    result = []
    for row in rows:
        p = db.get(Product, row.product_id)
        if not p:
            continue
        result.append(ProductionListOut(
            list_id=row.id,
            product_id=p.id,
            added_at=row.created_at,
            name=p.name,
            brand=p.brand,
            category=p.category,
            image_url=p.image_url,
            last_price=p.last_price,
            trend_direction=p.trend_direction,
            trend_score=p.trend_score,
        ))
    return result


class AddToProductionListRequest(BaseModel):
    product_id: int


@router.post("/production-list", response_model=ProductionListOut, status_code=status.HTTP_201_CREATED)
def add_to_production_list(
    body: AddToProductionListRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Veritabanındaki bir ürünü kullanıcının üretim listesine ekler."""
    p = db.get(Product, body.product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")

    existing = db.query(UserProduct).filter(
        UserProduct.user_id == current_user.id,
        UserProduct.product_id == body.product_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Bu ürün zaten listenizde")

    entry = UserProduct(
        user_id=current_user.id,
        product_id=p.id,
        name=p.name or "İsimsiz",
        category=p.category,
        brand=p.brand,
        price=p.last_price,
        image_url=p.image_url,
        is_watching=True,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return ProductionListOut(
        list_id=entry.id,
        product_id=p.id,
        added_at=entry.created_at,
        name=p.name,
        brand=p.brand,
        category=p.category,
        image_url=p.image_url,
        last_price=p.last_price,
        trend_direction=p.trend_direction,
        trend_score=p.trend_score,
    )


@router.delete("/production-list/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_production_list(
    list_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Üretim listesinden bir kaydı siler."""
    entry = db.query(UserProduct).filter(
        UserProduct.id == list_id,
        UserProduct.user_id == current_user.id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Kayıt bulunamadı")
    db.delete(entry)
    db.commit()
    return


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: int, db: Session = Depends(get_db)):
    """Tek ürün detayı."""
    p = db.query(Product).filter(Product.id == product_id).first()
    if not p:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    
    latest_metric = db.query(DailyMetric).filter(
        DailyMetric.product_id == p.id
    ).order_by(desc(DailyMetric.recorded_at)).first()
    
    return ProductOut(
        id=p.id,
        product_code=p.product_code,
        name=p.name,
        brand=p.brand,
        seller=p.seller,
        url=p.url,
        image_url=p.image_url,
        category_tag=p.category_tag,
        category=p.category,
        attributes=p.attributes,
        review_summary=p.review_summary,
        sizes=p.sizes,
        last_price=p.last_price,
        last_discount_rate=p.last_discount_rate,
        avg_sales_velocity=p.avg_sales_velocity,
        first_seen_at=p.first_seen_at,
        last_scraped_at=p.last_scraped_at,
        favorite_count=latest_metric.favorite_count if latest_metric else None,
        cart_count=latest_metric.cart_count if latest_metric else None,
        view_count=latest_metric.view_count if latest_metric else None,
        avg_rating=latest_metric.avg_rating if latest_metric else None,
        rating_count=latest_metric.rating_count if latest_metric else None,
        qa_count=latest_metric.qa_count if latest_metric else None,
        original_price=latest_metric.price if latest_metric else None,
        discounted_price=latest_metric.discounted_price if latest_metric else None,
        page_number=latest_metric.page_number if latest_metric else None,
        search_rank=latest_metric.search_rank if latest_metric else None,
        absolute_rank=latest_metric.absolute_rank if latest_metric else None,
        search_term=latest_metric.search_term if latest_metric else None,
    )


@router.get("/reports/summary")
async def get_report_summary(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """Son N günün rapor özeti — otomatik raporlama için temel endpoint."""
    from sqlalchemy import text
    
    result = db.execute(text("""
        SELECT 
            COUNT(DISTINCT p.id) AS total_products,
            COUNT(DISTINCT CASE WHEN p.first_seen_at >= NOW() - INTERVAL ':days days' THEN p.id END) AS new_products,
            ROUND(AVG(dm.avg_rating)::numeric, 2) AS avg_rating,
            ROUND(AVG(dm.price)::numeric, 2) AS avg_price,
            SUM(dm.favorite_count) AS total_favorites,
            SUM(dm.cart_count) AS total_cart,
            SUM(dm.view_count) AS total_views,
            COUNT(DISTINCT p.brand) AS unique_brands,
            COUNT(DISTINCT p.seller) FILTER (WHERE p.seller IS NOT NULL AND p.seller != '') AS unique_sellers
        FROM products p
        LEFT JOIN LATERAL (
            SELECT * FROM daily_metrics dm2 
            WHERE dm2.product_id = p.id 
            ORDER BY dm2.recorded_at DESC LIMIT 1
        ) dm ON true
        WHERE p.last_scraped_at >= NOW() - INTERVAL ':days days'
    """).bindparams(days=days)).fetchone()
    
    # Top brands by product count
    top_brands = db.execute(text("""
        SELECT brand, COUNT(*) AS cnt 
        FROM products 
        WHERE brand IS NOT NULL AND brand != ''
            AND last_scraped_at >= NOW() - INTERVAL ':days days'
        GROUP BY brand 
        ORDER BY cnt DESC LIMIT 10
    """).bindparams(days=days)).fetchall()
    
    return {
        "period_days": days,
        "total_products": result[0],
        "new_products": result[1],
        "avg_rating": float(result[2]) if result[2] else 0,
        "avg_price": float(result[3]) if result[3] else 0,
        "total_favorites": result[4] or 0,
        "total_cart": result[5] or 0,
        "total_views": result[6] or 0,
        "unique_brands": result[7],
        "unique_sellers": result[8],
        "top_brands": [{"brand": r[0], "count": r[1]} for r in top_brands],
    }


