# app/services/intelligence_client.py
"""
Lumora Intelligence HTTP Client
LangChain Backend → Intelligence Mikro Servis (:8001) iletişimi.
"""
import logging
from typing import Optional
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# ─── Tip tanımları (lightweight, Pydantic gerektirmez) ──────────────────────
PredictionResult = dict  # {product_id, trend_label, trend_score, confidence, ...}
AnalysisResult   = dict  # {product_id, trend_label, trend_score, signals, ...}
AlertItem        = dict  # {id, type, product_id, category, message, created_at, is_read}


class IntelligenceClient:
    """
    Intelligence mikro servisine bağlanan async HTTP client.
    app lifecycle boyunca tek instance kullanılır (lifespan'de oluşturulur).
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    def _build_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        key = getattr(settings, "intelligence_internal_key", "")
        if key:
            headers["X-Internal-Key"] = key
        return headers

    async def startup(self):
        """Uygulama başlangıcında HTTP client'ı oluşturur."""
        self._client = httpx.AsyncClient(
            base_url=getattr(settings, "intelligence_url", "http://localhost:8001"),
            timeout=httpx.Timeout(60.0, connect=10.0),
            headers=self._build_headers(),
        )
        logger.info(f"IntelligenceClient başlatıldı → {self._client.base_url}")

    async def shutdown(self):
        """Uygulama kapanışında client'ı kapatır."""
        if self._client:
            await self._client.aclose()
            logger.info("IntelligenceClient kapatıldı")

    def _client_or_raise(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("IntelligenceClient henüz başlatılmadı (startup() çağrılmadı)")
        return self._client

    # ──────────────────────────────────────────────────────────────────────────
    # API Metodları
    # ──────────────────────────────────────────────────────────────────────────

    async def health(self) -> dict:
        """Intelligence servisinin sağlık durumunu döndürür. Hata durumunda dict döner (exception atmaz)."""
        try:
            resp = await self._client_or_raise().get("/health")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Intelligence /health erişilemiyor: {type(e).__name__}: {e}")
            return {"status": "unreachable", "error": str(e)}

    async def predict(
        self,
        category: Optional[str] = None,
        top_n: int = 20,
    ) -> list[PredictionResult]:
        """
        Kategori trend tahmin listesi alır.
        Raises: httpx.TimeoutException, httpx.ConnectError — proxy router 503'e çevirir.
        """
        params = {"top_n": top_n}
        if category:
            params["category"] = category

        resp = await self._client_or_raise().get("/predict", params=params)
        resp.raise_for_status()
        return resp.json().get("results", [])

    async def analyze(self, product_id: int) -> AnalysisResult:
        """
        Tekil ürün analizi alır.
        Raises: httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError
        """
        resp = await self._client_or_raise().post(
            "/analyze", json={"product_id": product_id}
        )
        if resp.status_code == 404:
            return {"error": f"product_id={product_id} bulunamadı"}
        resp.raise_for_status()
        return resp.json()

    async def feedback(
        self,
        product_id: int,
        sold_quantity: int,
        predicted_quantity: int,
    ) -> dict:
        """
        Gerçek satış verisiyle feedback gönderir.
        Raises: httpx.TimeoutException, httpx.ConnectError
        """
        resp = await self._client_or_raise().post(
            "/feedback",
            json={
                "product_id":         product_id,
                "sold_quantity":      sold_quantity,
                "predicted_quantity": predicted_quantity,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def trigger(
        self,
        scope: str = "all",
        category: Optional[str] = None,
        priority: str = "normal",
    ) -> dict:
        """
        Manuel analiz tetikler.
        Raises: httpx.TimeoutException, httpx.ConnectError
        """
        payload = {"scope": scope, "priority": priority}
        if category:
            payload["category"] = category

        resp = await self._client_or_raise().post("/trigger", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def get_alerts(self, unread_only: bool = False, limit: int = 50) -> list[AlertItem]:
        """Trend alertlerini alır. Hata durumunda boş liste döner (non-critical)."""
        try:
            resp = await self._client_or_raise().get(
                "/alerts",
                params={"unread_only": unread_only, "limit": limit},
            )
            resp.raise_for_status()
            return resp.json().get("alerts", [])
        except Exception as e:
            logger.warning(f"Intelligence /alerts erişilemiyor: {type(e).__name__}")
            return []


# ─── Global singleton (lifespan'de startup/shutdown çağrılır) ─────────────────
intelligence_client = IntelligenceClient()
