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

3. **Ortam değişkenleri**

`env.template` dosyasını `.env` olarak kopyalayın ve değerleri güncelleyin.

**Windows:**
```bash
copy env.template .env
```

**macOS/Linux:**
```bash
cp env.template .env
```

`.env` dosyasını açın ve aşağıdaki değerleri güncelleyin:
- `POSTGRESQL_HOST`: PostgreSQL sunucu adresi (Docker kullanıyorsanız: `localhost`)
- `POSTGRESQL_PORT`: PostgreSQL portu (varsayılan: `5432`)
- `POSTGRESQL_DATABASE`: Veritabanı adınız (Docker için varsayılan: `bediralvesil_db`)
- `POSTGRESQL_USERNAME`: Veritabanı kullanıcı adınız (Docker için varsayılan: `postgres`)
- `POSTGRESQL_PASSWORD`: Veritabanı şifreniz (Docker için varsayılan: `postgres123`)
- `JWT_SECRET`: Güçlü bir secret key (production için mutlaka değiştirin!)
- `CORS_ORIGINS`: Frontend URL'leri (virgülle ayrılmış)

**Docker kullanıyorsanız:** `docker-compose.yml` dosyasındaki varsayılan değerlerle uyumlu olması için `.env` dosyanızı şu şekilde ayarlayabilirsiniz:
```
POSTGRESQL_HOST=localhost
POSTGRESQL_PORT=5432
POSTGRESQL_DATABASE=bediralvesil_db
POSTGRESQL_USERNAME=postgres
POSTGRESQL_PASSWORD=postgres123
```

4. **Veritabanı tablolarını oluşturma**

```bash
python -m app.setup_database
```

5. **Sunucuyu çalıştırma**

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

