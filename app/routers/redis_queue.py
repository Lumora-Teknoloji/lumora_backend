"""
VPS Redis API Proxy — FastAPI Endpoint'leri

Botlar Redis'e doğrudan bağlanmaz. Bu proxy üzerinden erişir.
Port 6379 asla dışarıya açılmaz — güvenli HTTP katmanı.

Mevcut FastAPI uygulamanıza router olarak ekleyin:
    from vps.redis_api import router as redis_router
    app.include_router(redis_router, prefix="/redis")

Ortam Değişkenleri:
    REDIS_URL       — redis://localhost:6379 (varsayılan)
    AGENT_SECRET    — bot kimlik doğrulama anahtarı

Redis Key Şeması:
    links:pending       LIST  — kazılacak URL'ler
    links:processing    LIST  — şu anda işlenen URL'ler (BRPOPLPUSH ile)
    links:retry         LIST  — başarısız, tekrar denenecek URL'ler
    results:buffer      LIST  — flusher'ın boşaltacağı sonuçlar
    scraped:urls        SET   — duplicate kontrolü için kazılmış URL'ler
    bot:{id}:status     HASH  — bot canlılık durumu
"""

import json
import os
import time
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel
import asyncio
from contextlib import asynccontextmanager
import logging
from starlette.concurrency import run_in_threadpool

from app.core.database import SessionLocal
from app.services.data.scraper_service import TrendyolScraperService

logger = logging.getLogger(__name__)

from app.core.config import settings

# ─── Config ───────────────────────────────────────────────────────────────────
REDIS_URL = settings.redis_url
AGENT_SECRET = settings.agent_secret


# Processing listesindeki URL'lerin maksimum işlem süresi (saniye)
# Bu süre aşıldıktan sonra recovery job geri koyar.
PROCESSING_TIMEOUT_S = 300  # 5 dakika

def _sync_save_batch(batch_data: list):
    """Senkron veritabanı işlemi (threadpool içinde çalışır)."""
    db = SessionLocal()
    try:
        service = TrendyolScraperService(db)
        # task_id None olarak geçer çünkü agent kendi context'inden bağımsız ürün yollar
        service.process_scraped_batch(batch_data, task_id=None)
    except Exception as e:
        logger.error(f"results:buffer DB kayit hatasi: {e}")
    finally:
        db.close()

async def _results_flusher_loop():
    """results:buffer → PostgreSQL"""
    while True:
        try:
            r = await get_redis()
            batch = await r.lrange("results:buffer", 0, 99)
            if batch:
                parsed_batch = []
                for raw in batch:
                    try:
                        parsed_batch.append(json.loads(raw))
                    except json.JSONDecodeError:
                        pass
                
                if parsed_batch:
                    await run_in_threadpool(_sync_save_batch, parsed_batch)
                
                # Başarılı save sonrası kuyruğun başından batch uzunluğu kadarını sil
                await r.ltrim("results:buffer", len(batch), -1)
                logger.info(f"Flusher: {len(batch)} ürün başarıyla veritabanına işlendi.")
            else:
                await asyncio.sleep(5)  # Eğer kuyruk boşsa kısa bekle
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Flusher loop hatası: {e}")
            await asyncio.sleep(10)

async def _recovery_loop():
    """Processing kuyruğunda askıda kalan linkleri kurtarır."""
    while True:
        await asyncio.sleep(300)  # 5 dakikada bir
        try:
            r = await get_redis()
            processing_urls = await r.lrange("links:processing", 0, -1)
            now = time.time()
            recovered = 0
            for url in processing_urls:
                try:
                    meta = await r.hgetall(f"processing:meta:{url}")
                    started_at = float(meta.get("started_at", now))
                    if now - started_at > PROCESSING_TIMEOUT_S:
                        # Zaman aşımı — geri koy
                        await r.lrem("links:processing", 1, url)
                        await r.lpush("links:pending", url)
                        await r.delete(f"processing:meta:{url}")
                        recovered += 1
                except Exception:
                    pass
            if recovered > 0:
                logger.info(f"[Redis Queue] {recovered} zaman aşımına uğrayan işlem kurtarıldı.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Recovery loop hatası: {e}")

@asynccontextmanager
async def redis_lifespan(app):
    recv_task = asyncio.create_task(_recovery_loop())
    flush_task = asyncio.create_task(_results_flusher_loop())
    yield
    recv_task.cancel()
    flush_task.cancel()

router = APIRouter(tags=["Redis Queue"], lifespan=redis_lifespan)

# ─── Redis Bağlantı Havuzu ────────────────────────────────────────────────────
_redis_pool: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = await aioredis.from_url(
            REDIS_URL, encoding="utf-8", decode_responses=True
        )
    return _redis_pool


# ─── Auth ─────────────────────────────────────────────────────────────────────
async def verify_secret(x_agent_secret: str = Header(...)):
    if not AGENT_SECRET:
        if settings.app_env == "production":
            raise HTTPException(status_code=401, detail="AGENT_SECRET yapılandırılmamış")
        return  # sadece dev'de skip
    if x_agent_secret != AGENT_SECRET:
        raise HTTPException(status_code=401, detail="Geçersiz agent anahtarı")


# ─── Request Modelleri ────────────────────────────────────────────────────────
class PopRequest(BaseModel):
    timeout: int = 30  # BRPOPLPUSH blok süresi (saniye)


class FailRequest(BaseModel):
    url: str


class HeartbeatRequest(BaseModel):
    status: str
    stats: dict = {}


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/queue/pop", dependencies=[Depends(verify_secret)])
async def queue_pop(req: PopRequest, x_bot_id: str = Header(...)):
    """
    Atomik BRPOPLPUSH: links:pending → links:processing.
    Kuyruk boşsa timeout süresince bloklar.
    """
    r = await get_redis()
    url = await r.brpoplpush("links:pending", "links:processing", timeout=req.timeout)

    if url is None:
        from fastapi import Response
        return Response(status_code=204)  # Kuyruk boş

    # İşlem başlangıç zamanını kaydet (timeout recovery için)
    await r.hset(f"processing:meta:{url}", mapping={
        "bot_id": x_bot_id,
        "started_at": time.time(),
    })
    await r.expire(f"processing:meta:{url}", PROCESSING_TIMEOUT_S * 2)

    return {"url": url}


@router.post("/queue/push_result", dependencies=[Depends(verify_secret)])
async def queue_push_result(request: Request):
    """Başarılı scrape sonucunu results:buffer'a at."""
    r = await get_redis()
    body = await request.body()

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Geçersiz JSON")

    url = data.get("url", "")
    if not url:
        raise HTTPException(status_code=400, detail="url alanı eksik")

    # Sonucu buffer'a ekle
    await r.lpush("results:buffer", body.decode("utf-8"))

    # Duplicate seti güncelle
    await r.sadd("scraped:urls", url)

    # Processing listesinden temizle
    await r.lrem("links:processing", 1, url)
    if url:
        await r.delete(f"processing:meta:{url}")

    return {"ok": True}


@router.post("/queue/fail", dependencies=[Depends(verify_secret)])
async def queue_fail(req: FailRequest):
    """Başarısız URL'yi retry kuyruğuna gönder ve processing'den temizle."""
    r = await get_redis()

    await r.lpush("links:retry", req.url)
    await r.lrem("links:processing", 1, req.url)
    await r.delete(f"processing:meta:{req.url}")

    return {"ok": True}


@router.get("/queue/stats", dependencies=[Depends(verify_secret)])
async def queue_stats():
    """Kuyruk boyutlarını döndür — monitoring dashboard için."""
    r = await get_redis()

    pending = await r.llen("links:pending")
    processing = await r.llen("links:processing")
    retry = await r.llen("links:retry")
    results_buffer = await r.llen("results:buffer")
    scraped_total = await r.scard("scraped:urls")

    return {
        "pending": pending,
        "processing": processing,
        "retry": retry,
        "results_buffer": results_buffer,
        "scraped_total": scraped_total,
        "throughput_estimate": {
            "desc": "pending / bot sayısına bölün → tamamlanma süresi (dk)",
        },
    }


@router.post("/bot/heartbeat", dependencies=[Depends(verify_secret)])
async def bot_heartbeat(req: HeartbeatRequest, x_bot_id: str = Header(...)):
    """Bot canlılık bildirimi — VPS botları izler."""
    r = await get_redis()

    await r.hset(f"bot:{x_bot_id}:status", mapping={
        "status": req.status,
        "last_seen": time.time(),
        **{k: str(v) for k, v in req.stats.items()},
    })
    # 10 dakika TTL — bot ölürse otomatik temizlenir
    await r.expire(f"bot:{x_bot_id}:status", 600)

    return {"ok": True}


@router.get("/bots", dependencies=[Depends(verify_secret)])
async def list_bots():
    """Tüm aktif botların durumunu listele."""
    r = await get_redis()
    keys = await r.keys("bot:*:status")
    bots = {}
    for key in keys:
        bot_id = key.split(":")[1]
        data = await r.hgetall(key)
        data["last_seen_ago"] = round(time.time() - float(data.get("last_seen", 0)))
        bots[bot_id] = data
    return bots


@router.post("/queue/recover", dependencies=[Depends(verify_secret)])
async def recover_stale():
    """
    Timeout aşan processing URL'lerini pending'e geri taşı.
    Cron veya scheduler tarafından periyodik çağrılır (ör: her 5dk).
    """
    r = await get_redis()
    processing_urls = await r.lrange("links:processing", 0, -1)

    recovered = 0
    now = time.time()

    for url in processing_urls:
        meta = await r.hgetall(f"processing:meta:{url}")
        started_at = float(meta.get("started_at", now))

        if now - started_at > PROCESSING_TIMEOUT_S:
            # Zaman aşımı — geri koy
            await r.lrem("links:processing", 1, url)
            await r.lpush("links:pending", url)
            await r.delete(f"processing:meta:{url}")
            recovered += 1

    return {"recovered": recovered}
