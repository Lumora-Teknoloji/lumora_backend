# FastAPI Backend (PostgreSQL)

FastAPI tabanlı backend servisi - PostgreSQL veritabanı, JWT kimlik doğrulama ve Socket.IO gerçek zamanlı sohbet desteği.

## 🚀 Hızlı Başlangıç

### 1. Ortam Değişkenlerini Ayarlayın

`.env.local` dosyası oluşturun (varsa `env.template` dosyasını kopyalayın):

```bash
# Windows
copy env.template .env.local

# macOS/Linux
cp env.template .env.local
```

**Minimum Gerekli Ayarlar** (`.env.example` dosyasını `.env` olarak kopyalayın):
```env
# PostgreSQL bağlantısı
POSTGRESQL_HOST=localhost
POSTGRESQL_PORT=5432
POSTGRESQL_DATABASE=lumora_db
POSTGRESQL_USERNAME=postgres
POSTGRESQL_PASSWORD=postgres

# JWT
JWT_SECRET=change-me-to-a-strong-random-string

# Frontend & CORS
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000,http://localhost:3001

# Scrapper dizini (opsiyonel, belirtilmezse otomatik algılanır)
# SCRAPPER_DIR=C:\Users\Admin\Documents\vscode\Scrapper

# AI Keys
OPENAI_API_KEY=your-openai-api-key-here
TAVILY_API_KEY=your-tavily-api-key-here
```

### 2. Docker ile Çalıştırma (Önerilen)

> **Not:** Bu proje `pgvector` eklentisine ihtiyaç duyar. `docker-compose.yml` dosyası `pgvector/pgvector:pg16` imajını kullanacak şekilde yapılandırılmıştır.

```bash
# Tüm servisleri başlat (PostgreSQL + Backend)
docker-compose up -d

# Logları görüntüle
docker-compose logs -f

# Servisleri durdur
docker-compose down
```

✅ **Veritabanı tabloları otomatik oluşturulur** - Herhangi bir manuel işlem gerekmez.

### 3. Manuel Çalıştırma

```bash
# Bağımlılıkları yükle
pip install -r requirements.txt

# Sunucuyu başlat
python run_server.py
```

**Not:** Manuel çalıştırma için PostgreSQL'in çalışıyor olması gerekir.

## 📍 Erişim

- **API Dokümantasyonu:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health
- **API Endpoint:** http://localhost:8000/api

## 🔧 Temel Docker Komutları

```bash
# Başlat
docker-compose up -d

# Durdur (veriler korunur)
docker-compose down

# Durdur ve verileri sil
docker-compose down -v

# Logları görüntüle
docker-compose logs -f backend

# Yeniden başlat
docker-compose restart
```

## 📂 Proje Yapısı

```
.
├── app/                  # 🧠 Ana uygulama mantığı
│   ├── api/              # 🌐 API Katmanı
│   │   ├── v1/endpoints/ # 🛣️ API Rotaları (Auth, Users, Conversations)
│   │   └── deps.py       # 🛡️ Bağımlılıklar (Auth, DB)
│   ├── core/             # ⚙️ Çekirdek Yapılandırma & Utility
│   │   ├── config.py     # 🔧 Uygulama ayarları
│   │   ├── database.py   # 🗄️ Veritabanı bağlantısı
│   │   ├── security.py   # 🔐 Güvenlik fonksiyonları
│   │   ├── lifespan.py   # 🔄 Startup/Shutdown olayları
│   │   ├── logging.py    # 📝 Loglama yapılandırması
│   │   └── errors.py     # ⚠️ Exception handler'lar
│   ├── middleware/       # 🛡️ Middleware Katmanı (Yeni)
│   │   ├── security.py   # 🔒 Güvenlik başlıkları
│   │   ├── cors.py       # 🌐 CORS ayarları
│   │   └── rate_limit.py # 🚦 Rate limiting
│   ├── services/         # 🤖 İş Mantığı & AI Servisleri
│   │   ├── ai_orchestrator.py # 🧠 AI Orkestrasyonu
│   │   ├── clients.py    # 🔌 OpenAI/Tavily istemcileri
│   │   └── research.py   # 🔍 Pazar araştırması
│   ├── models/           # 🏗️ Veritabanı Modelleri (Modüler)
│   ├── schemas/          # 📋 Pydantic Şemaları (Modüler)
│   ├── main.py           # 🚀 Uygulama giriş noktası
│   └── socket_manager.py # 🔌 WebSocket yönetimi
├── tests/                # 🧪 Testler (Pytest)
├── static/               # 📁 Statik dosyalar
├── .env                  # 🔑 Ortam değişkenleri
├── docker-compose.yml    # 🐳 Docker konfigürasyonu
├── Dockerfile            # 🐳 Docker imaj tanımı
└── requirements.txt      # 📦 Bağımlılıklar
```

## 📝 Notlar

- Veritabanı tabloları backend başladığında **otomatik** oluşturulur
- Mevcut veriler **korunur** - her başlatmada sıfırlanmaz
- AI API key'leri olmadan da çalışır (AI özellikleri devre dışı kalır)

## 🧪 Testleri Çalıştırma

Proje `pytest` kullanmaktadır. Testler çalıştırılırken `pgvector` destekli bir PostgreSQL veritabanı gereklidir (`test_postgres` veritabanı otomatik oluşturulur).

```bash
# Testleri çalıştır
./myenv/bin/python -m pytest tests/

# Veya sanal ortam aktifse
pytest tests/
```

## 🆘 Sorun Giderme

**Veritabanı bağlantı hatası:**
```bash
docker-compose ps postgres
docker-compose logs postgres
```

**Backend başlamıyor:**
```bash
docker-compose logs backend
```

**Tablolar oluşturulmadı:**
- Backend loglarını kontrol edin: `docker-compose logs backend | grep -i "tablo\|database"`
- PostgreSQL'in hazır olduğundan emin olun
