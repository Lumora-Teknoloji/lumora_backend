# FastAPI Backend (PostgreSQL)

Bu servis, Lumora frontend'i için kimlik doğrulama, kullanıcı profili ve sohbet geçmişi API'lerini sağlayan bağımsız bir FastAPI uygulamasıdır. PostgreSQL veritabanına bağlanır ve JWT tabanlı auth kullanır.

**Konum:** `C:\bediralvesil-backend`

## Özellikler

- FastAPI + SQLAlchemy 2
- PostgreSQL (psycopg2) desteği
- Kullanıcı kayıt / giriş / profil
- Konuşma oluşturma ve listeleme
- Mesaj kaydetme ve listeleme
- JWT access token
- Socket.IO ile gerçek zamanlı sohbet
- OpenAI GPT-4o ile AI yanıt üretimi
- Tavily ile internet araması ve trend analizi
- Stability AI SDXL ile görsel üretimi
- Misafir kullanıcı desteği (geçici sohbetler)

## Kurulum

1. **Gereksinimler**
   - Python 3.10+
   - Docker ve Docker Compose (PostgreSQL için Docker kullanıyorsanız)

2. **PostgreSQL Veritabanını Docker ile Başlatma**

PostgreSQL'i Docker ile çalıştırmak için:

```bash
# Docker Compose ile PostgreSQL'i başlat
docker-compose up -d

# Container durumunu kontrol et
docker-compose ps

# Logları görüntüle
docker-compose logs -f postgres
```

PostgreSQL container'ı başladıktan sonra `localhost:5432` üzerinden erişilebilir olacaktır.

**Not:** Docker kullanmıyorsanız, sisteminizde kurulu bir PostgreSQL veritabanı kullanabilirsiniz.

3. **Yükleme**

```bash
cd bediralvesil-backend
python -m venv venv
venv\Scripts\activate      # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

4. **Ortam değişkenleri**

`env.template` dosyasını `.env` olarak kopyalayın ve değerleri güncelleyin.

**Windows:**
```bash
copy env.template .env.local
```

**macOS/Linux:**
```bash
cp env.template .env.local
```

### `.env` Dosyası Yapılandırması

`.env` dosyasını açın ve aşağıdaki değerleri güncelleyin:

#### Uygulama Ayarları
```env
APP_NAME=Lumora Backend
API_PREFIX=/api
APP_ENV=development
PORT=8000
```

#### PostgreSQL Veritabanı
```env
POSTGRESQL_HOST=localhost
POSTGRESQL_PORT=5432
POSTGRESQL_DATABASE=bediralvesil_db
POSTGRESQL_USERNAME=postgres
POSTGRESQL_PASSWORD=postgres123
```

**Docker kullanıyorsanız:** Yukarıdaki varsayılan değerleri kullanabilirsiniz.

#### JWT (Kimlik Doğrulama)
```env
JWT_SECRET=change-me                    # Production için mutlaka güçlü bir secret key kullanın!
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120
```

#### CORS (Frontend URL'leri)
```env
FRONTEND_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

#### AI Servisleri API Key'leri

**OpenAI API Key** (Zorunlu - AI yanıt üretimi için)
```env
OPENAI_API_KEY=sk-proj-...
```
- OpenAI API key almak için: https://platform.openai.com/api-keys
- `gpt-4o` modeli kullanılıyor

**Tavily API Key** (Zorunlu - İnternet araması için)
```env
TAVILY_API_KEY=tvly-dev-...
```
- Tavily API key almak için: https://tavily.com/
- Trend ve pazar araştırmaları için kullanılıyor

**FAL AI API Key** (Opsiyonel - Görsel üretimi için, Flux2-pro)
```env
FAL_API_KEY=fal-...
```
- FAL (flux) API key almak için: https://fal.ai/
- Flux2-pro modeli ile görsel üretimi için kullanılıyor
- Ücretlendirme için fal.ai dokümantasyonuna bakın

**Not:** AI API key'leri olmadan da uygulama çalışır ancak AI özellikleri devre dışı kalır.

5. **Veritabanı tablolarını oluşturma**

```bash
python -m app.setup_database
```

6. **Sunucuyu çalıştırma**

**Yöntem 1: Server script ile (önerilen)**
```bash
python run_server.py
```

**Yöntem 2: Uvicorn ile**
```bash
uvicorn app.main:app --reload --port 8000
```

Sunucu başladıktan sonra:
- API dokümantasyonu: http://localhost:8000/docs
- Health check: http://localhost:8000/health

Frontend `.env.local` dosyanıza `NEXT_PUBLIC_BACKEND_URL` değerini (`http://localhost:8000`) eklemeyi unutmayın.

## Docker Komutları

PostgreSQL container'ını yönetmek için:

```bash
# Container'ı durdur
docker-compose down

# Container'ı durdur ve verileri sil (DİKKAT: Tüm veriler silinir!)
docker-compose down -v

# Container'ı yeniden başlat
docker-compose restart

# Container'a bağlan (psql ile)
docker-compose exec postgres psql -U postgres -d bediralvesil_db
```

## Optimizasyonlar

- ✅ Connection pooling (pool_size=10, max_overflow=20)
- ✅ Connection recycling (1 saatte bir)
- ✅ URL encoding ile güvenli connection string
- ✅ Gelişmiş error handling ve logging
- ✅ CORS çoklu origin desteği
- ✅ Query optimizasyonları
- ✅ JWT token validation iyileştirmeleri

