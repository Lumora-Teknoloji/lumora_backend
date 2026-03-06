# LANGCHAIN BACKEND — Mimari Dokümantasyon

> Bu dosya AI asistanının ve geliştiricilerin backend sistemini hızlıca anlaması içindir.

## Genel Bakış

FastAPI + Socket.IO tabanlı API servisi. Scrapper yönetimi, AI sohbet, pazar araştırması ve görsel üretimi yapar.

**Toplam:** ~5.000+ satır Python kodu | 45+ API endpoint | 12 servis

## Giriş Noktası

`app/main.py` — FastAPI uygulamasını oluşturur:
1. Middleware zinciri: Security headers → Rate limiting → Trusted host → CORS
2. Router'ları bağlar: auth, users, conversations, messages, scraper, bot_commands, products
3. Socket.IO entegrasyonu (`socketio_app` ASGI wrapper)
4. Static dosya mount
5. Health check endpoint

`run_server.py` — Uvicorn sunucu başlatıcı

## Router'lar (API Endpoint'leri)

### `/api/scraper` — Scraper Yönetimi (1205 satır, 27 endpoint)

**Ana dosya:** `app/routers/scraper.py`

| Endpoint | Metot | Açıklama |
|----------|-------|----------|
| `/scraper/ingest` | POST | Toplu ürün verisi kaydet |
| `/scraper/tasks` | POST | Yeni bot görevi oluştur |
| `/scraper/tasks/{id}` | GET | Görev detayı |
| `/scraper/tasks/{id}/status` | PUT | Görev durumu güncelle |
| `/scraper/tasks/active` | GET | Aktif görevler listesi |
| `/scraper/bots/status` | GET | **Tüm botların durumu** (frontend ana veri kaynağı) |
| `/scraper/status` | GET | Genel scraper istatistikleri |
| `/scraper/bots/linkers` | GET | Worker için linker bot listesi |
| `/scraper/bots/{id}/start` | POST | Bot başlat (dosya köprüsü) |
| `/scraper/bots/{id}/worker` | POST | Worker modunda başlat |
| `/scraper/bots/{id}/stop` | POST | Bot durdur |
| `/scraper/bots/{id}/speed-mode` | POST | Hız modu aktif (max 30dk) |
| `/scraper/bots/{id}` | DELETE | Bot sil |
| `/scraper/bots/{id}/settings` | PATCH | Bot ayarları güncelle |
| `/scraper/logs` | GET | Sistem logları (bot_id filtre) |
| `/scraper/logs/backend` | GET | Backend logları |
| `/scraper/logs/errors` | DELETE | Hata loglarını temizle |
| `/scraper/logs/{id}` | DELETE | Tekil log sil |
| `/scraper/system/health` | GET | Sistem sağlığı (CPU, RAM, disk) |
| `/scraper/live-products` | GET | Son kazınan ürünler |
| `/scraper/monitor/check` | GET | Sağlık kontrolü + webhook alarm |

**Bot Durumu Mantığı (`get_bots_status`):**
- ScrapingTask tablosundan tüm görevleri çeker
- Her görev için: PID dosyası var mı? Log dosyası var mı? Son log ne zaman?
- Kuyrukta bekleyen link sayısı
- `bot_state` hesaplaması: scraping, waiting_ip, blocked, cooldown, queue_empty, critical, error_streak, speed_mode, idle

### `/api/products` — Ürün API (328 satır, 4 endpoint)

| Endpoint | Açıklama |
|----------|----------|
| `/products/` | Ürün listesi (filtre, sıralama, pagination) |
| `/products/quality` | Veri kalitesi istatistikleri |
| `/products/{id}` | Ürün detayı + son 30 gün metrikleri |
| `/products/report-summary` | Son N günün rapor özeti |

### `/api/scheduler` — Komut Kuyruğu (60 satır, 3 endpoint)

In-memory komut kuyruğu (thread-safe):
- `GET /scheduler/commands` — Bekleyen komutları al
- `POST /scheduler/commands/{id}/ack` — Komutu onayla
- `queue_bot_command()` — Internal: kuyruğa komut ekle

### `/api/auth` — Kimlik Doğrulama

- POST `/auth/login` — JWT token al (HttpOnly cookie)
- POST `/auth/register` — Yeni kullanıcı oluştur
- POST `/auth/logout` — Cookie temizle
- POST `/auth/refresh` — Token yenile

### `/api/users` — Kullanıcı

- GET `/users/me` — Mevcut kullanıcı bilgisi

### `/api/conversations` + `/api/messages` — Sohbet CRUD

AI chatbot sohbet geçmişi yönetimi.

## Servisler

### AI Akışı

```
Kullanıcı mesajı → Socket.IO → user_message event
  → analyze_user_intent()        # intent.py: niyet analizi
     ├─ intent: "analysis"
     │    → deep_market_research()        # research.py: Tavily araştırma
     │    → get_google_trends()           # trends.py: SerpApi
     │    → generate_strategic_report()   # research.py: OpenAI rapor
     │    → generate_custom_images()      # image_gen_service.py: FAL AI
     │
     ├─ intent: "chat"
     │    → handle_general_chat()         # intent.py: OpenAI sohbet
     │
     ├─ intent: "image"
     │    → extract_image_request()       # image_gen_service.py
     │    → generate_custom_images()      # FAL AI görsel üretimi
     │
     └─ intent: "follow_up"
          → handle_follow_up()            # intent.py
```

### Servis Dosyaları

| Servis | Satır | Açıklama |
|--------|------:|----------|
| `socket_manager.py` | 536 | Socket.IO event handler'ları, misafir/auth kullanıcı desteği, streaming |
| `ai_orchestrator.py` | 336 | Ana AI yanıt motoru — niyet → araştırma → rapor → görsel pipeline |
| `intent.py` | 327 | Kullanıcı niyet analizi (OpenAI), genel sohbet işleme |
| `scraper_service.py` | 351 | TrendyolScraperService — ürün upsert, DailyMetric oluşturma/güncelleme |
| `image_gen_service.py` | 360 | FAL AI görsel üretim + Vision API doğrulama |
| `research.py` | 247 | Tavily araştırma + stratejik rapor üretimi |
| `metrics_service.py` | 227 | Skor formülleri (aşağıda detay) |
| `scheduler.py` | 240 | Dosya tabanlı bot komut köprüsü — mode-aware başlatma (linker/worker/normal), page_limit desteği |
| `trends.py` | 147 | Google Trends verisi (SerpApi) |
| `clients.py` | 76 | OpenAI + Tavily + SerpApi client başlatma |
| `title_generator.py` | 62 | AI sohbet başlığı oluşturma |

### Skor Formülleri (MetricsService)

`metrics_service.py` singleton:

```python
# Velocity (ürün popülerlik hızı):
velocity = (sepet × 3.0) + (favori × 2.0) + görüntülenme
# Log scale: log(sepet+1)×3 + log(favori+1)×2 + log(görüntülenme+1)

# Engagement (kullanıcı etkileşim):
engagement = (rating × 20) + log(review+1)×10 + log(qa+1)×5 + log(fav+1)×5

# Trend:
trend = (velocity_norm × 0.4) + (rating_norm × 0.3) + (growth × 0.3)

# İndirim:
discount_rate = ((orijinal - indirimli) / orijinal) × 100

# Stok sağlığı:
stock_health = (mevcut_beden / toplam_beden) × 100
```

## Veritabanı

### Bağlantı
- `app/core/database.py` — Connection pooling (pool_size=10, max_overflow=5, recycle=3600)
- `sync_schema()` — Başlangıçta eksik tablo/kolon/index/FK otomatik oluşturur
- `ensure_admin_user()` — İlk admin kullanıcı otomatik oluşturur

### Modeller (`app/models/`)

**Product** — Ürün kimliği:
- `product_code` (unique), `name`, `brand`, `seller`
- `url`, `image_url`, `category`, `category_tag`
- `feature_vector` (pgvector 1536 boyut — AI embedding)
- `attributes` (JSONB — renk, kumaş, vb.)
- `review_summary`, `sizes` (JSONB)
- `last_price`, `last_discount_rate`, `last_engagement_score`, `avg_sales_velocity`

**DailyMetric** — Günlük snapshot:
- Fiyat: `price`, `discounted_price`, `discount_rate`
- Sosyal: `cart_count`, `favorite_count`, `view_count`
- Değerlendirme: `rating_count`, `avg_rating`, `qa_count`
- Sıralama: `search_term`, `search_rank`, `page_number`, `absolute_rank`
- Hesaplanan: `engagement_score`, `popularity_score`, `sales_velocity`, `demand_acceleration`, `trend_direction`, `velocity_score`

**ScrapingTask** — Bot görev:
- `task_name`, `target_url`, `target_platform`
- `search_params` (JSONB): `mode` (linker/worker/normal), `page_limit`, `source_task_id`, `search_term`
- `start_time`, `end_time`, `is_active`, `scrape_interval_hours`

## Middleware

| Dosya | Açıklama |
|-------|----------|
| `security.py` | X-Content-Type-Options, X-Frame-Options, X-XSS-Protection |
| `cors.py` | CORS_ORIGINS env'den, credentials=true |
| `rate_limit.py` | SlowAPI rate limiting |
| `trusted_host.py` | ALLOWED_HOSTS kontrolü |

## Yapılandırma

`app/core/config.py` — Pydantic BaseSettings:
- `.env` + `.env.local` dosyalarından okur
- Production'da docs/redoc devre dışı
- DoS koruması: max_connections=200, connection_timeout=5

## Çalıştırma

```bash
# Docker
docker-compose up -d backend

# Manuel
pip install -r requirements.txt
python run_server.py  # http://0.0.0.0:8000
```
