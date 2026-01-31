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

**Minimum Gerekli Ayarlar:**
```env
APP_NAME=Lumora Backend
API_PREFIX=/api
APP_ENV=development
PORT=8000

# PostgreSQL bağlantısı - Docker kullanıyorsanız varsayılan değerleri kullanabilirsiniz
POSTGRESQL_HOST=localhost
POSTGRESQL_PORT=5432
POSTGRESQL_DATABASE=bediralvesil_db
POSTGRESQL_USERNAME=postgres
POSTGRESQL_PASSWORD=postgres123

# JWT
JWT_SECRET=change-me
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120

# CORS
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000,http://localhost:3001

OPENAI_API_KEY=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
TAVILY_API_KEY=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
STABILITY_API_KEY=sk-kjo9aoUlN8qeqYI8GPDgqjGpA3MCVr92nnBaQa7s5XHfvur0
FAL_API_KEY=68a9e3a1-59b0-4df4-8c4e-cfce378a2641:535db392c23ce433b7002e71a920c69c
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
