# app/routers/intelligence.py
"""
LangChain Backend — Intelligence Proxy Router
/api/intelligence/* → Lumora Intelligence (:8001) servisine iletir.

Çakışma Güvenceleri:
- Intelligence kapalıysa: 503 Service Unavailable döner, backend çökmez
- Timeout: 10 saniye sonra 503 döner
- Error body içeriğini sızdırmaz, temiz mesaj döner
"""
from typing import Optional, Literal
import httpx
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from app.services.intelligence_client import intelligence_client

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])


# ─── Yardımcı: Intelligence servis hatalarını temiz 503'e çevirir ─────────────
def _service_unavailable(detail: str = "Lumora Intelligence servisi şu an erişilemiyor"):
    raise HTTPException(status_code=503, detail=detail)


def _check_result(result: dict | list, key: str = "error") -> None:
    """Dict result'ta error anahtarı varsa 503 fırlatır."""
    if isinstance(result, dict) and key in result:
        raise HTTPException(status_code=503, detail=result[key])


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    product_id: int = Field(..., gt=0)


class FeedbackRequest(BaseModel):
    product_id:         int = Field(..., gt=0)
    sold_quantity:      int = Field(..., ge=0)
    predicted_quantity: int = Field(..., ge=0)


class TriggerRequest(BaseModel):
    scope:    Literal["all", "category"] = "all"
    category: Optional[str]              = None
    priority: Literal["normal", "urgent"] = "normal"


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/health", summary="Intelligence servis sağlık durumu")
async def intelligence_health():
    """
    Intelligence mikro servisinin sağlık durumunu döndürür.
    Servis kapalıysa `status: unreachable` döner (503 fırlatmaz — monitoring amaçlı).
    """
    return await intelligence_client.health()


@router.get("/predict", summary="Trend tahmin listesi")
async def intelligence_predict(
    category: Optional[str] = Query(None,  description="Kategori filtresi (ör: crop, tayt)"),
    top_n:    int            = Query(20,    ge=1, le=200, description="Maksimum ürün sayısı"),
):
    """
    Intelligence servisinden trend tahmin listesi.
    Intelligence kapalıysa 503 döner.
    """
    try:
        results = await intelligence_client.predict(category=category, top_n=top_n)
        return {"count": len(results), "category": category, "results": results}
    except httpx.TimeoutException:
        _service_unavailable("Intelligence servis yanıt vermiyor (timeout)")
    except Exception as e:
        _service_unavailable(f"Intelligence servis hatası: {type(e).__name__}")


@router.post("/analyze", summary="Tekil ürün analizi")
async def intelligence_analyze(request: AnalyzeRequest):
    """
    Tekil ürün için trend analizi.
    Ürün bulunamazsa 404, servis kapalıysa 503 döner.
    """
    try:
        result = await intelligence_client.analyze(request.product_id)
        if isinstance(result, dict) and "error" in result:
            # "bulunamadı" → 404, diğer hatalar → 503
            if "bulunamadı" in result["error"] or "not found" in result["error"].lower():
                raise HTTPException(status_code=404, detail=result["error"])
            _service_unavailable(result["error"])
        return result
    except HTTPException:
        raise
    except httpx.TimeoutException:
        _service_unavailable("Intelligence servis yanıt vermiyor (timeout)")
    except Exception as e:
        _service_unavailable(f"Intelligence servis hatası: {type(e).__name__}")


@router.post("/feedback", summary="Gerçek satış feedback'i")
async def intelligence_feedback(request: FeedbackRequest):
    """
    Gerçek satış verisiyle Intelligence Kalman filter'ını günceller.
    Servis kapalıysa 503 döner (feedback kalıcı kayıp değil, tekrar gönderilebilir).
    """
    try:
        result = await intelligence_client.feedback(
            product_id=request.product_id,
            sold_quantity=request.sold_quantity,
            predicted_quantity=request.predicted_quantity,
        )
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(status_code=422, detail=result.get("message", "Feedback işlenemedi"))
        return result
    except HTTPException:
        raise
    except httpx.TimeoutException:
        _service_unavailable("Intelligence servis yanıt vermiyor (timeout)")
    except Exception as e:
        _service_unavailable(f"Intelligence servis hatası: {type(e).__name__}")


@router.post("/trigger", summary="Manuel analiz tetikle")
async def intelligence_trigger(request: TriggerRequest):
    """
    Intelligence servisinde manuel analiz tetikler.
    Servis kapalıysa 503 döner.
    """
    try:
        return await intelligence_client.trigger(
            scope=request.scope,
            category=request.category,
            priority=request.priority,
        )
    except httpx.TimeoutException:
        _service_unavailable("Intelligence servis yanıt vermiyor (timeout)")
    except Exception as e:
        _service_unavailable(f"Intelligence servis hatası: {type(e).__name__}")


@router.get("/alerts", summary="Trend uyarıları")
async def intelligence_alerts(
    unread_only: bool = Query(False, description="Sadece okunmamış alertler"),
    limit:       int  = Query(50, ge=1, le=200),
):
    """
    Intelligence servisinden trend alertler.
    Servis kapalıysa boş liste döner (non-critical endpoint).
    """
    try:
        alerts = await intelligence_client.get_alerts(unread_only=unread_only, limit=limit)
        return {"count": len(alerts), "alerts": alerts}
    except Exception:
        # Alertler kritik değil — servis kapalıysa boş döner
        return {"count": 0, "alerts": [], "note": "Intelligence servisi erişilemiyor"}


# ─── Callback — Intelligence'dan gelen bildirimler ─────────────────────────────

class IntelligenceCallbackPayload(BaseModel):
    event:       str            = "scoring_complete"
    category:    Optional[str] = None
    trend_count: Optional[int] = None
    timestamp:   Optional[str] = None


@router.post("/callback", summary="Intelligence → Backend bildirim webhook")
async def intelligence_callback(payload: IntelligenceCallbackPayload):
    """
    Intelligence nightly_batch veya trigger tamamlandığında bu endpoint'i çağırır.
    Backend loglayıp Socket.IO üzerinden frontend'e bildirim gönderir.

    Frontend 'intelligence_update' eventini dinleyerek trend listesini yenileyebilir.
    """
    import logging
    cb_logger = logging.getLogger("intelligence.callback")
    cb_logger.info(
        f"Intelligence callback alındı: event={payload.event}, "
        f"category={payload.category}, trend_count={payload.trend_count}"
    )

    # Socket.IO ile frontend'e bildir (sio mevcutsa)
    try:
        from app.core.socket import sio  # noqa: PLC0415
        await sio.emit("intelligence_update", {
            "event":       payload.event,
            "category":    payload.category,
            "trend_count": payload.trend_count,
            "timestamp":   payload.timestamp,
        })
        cb_logger.info("Socket.IO intelligence_update eventi gönderildi")
    except ImportError:
        cb_logger.debug("Socket.IO mevcut degil, event gonderilmedi")
    except Exception as e:
        cb_logger.warning(f"Socket.IO emit hatası: {e}")

    return {
        "status": "received",
        "event": payload.event,
        "category": payload.category,
    }
