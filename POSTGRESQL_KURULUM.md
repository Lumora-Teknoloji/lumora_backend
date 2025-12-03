# PostgreSQL Kurulum ve Başlatma Rehberi

## Sorun
Backend uygulaması PostgreSQL veritabanına bağlanamıyor çünkü PostgreSQL çalışmıyor.

## Çözüm Seçenekleri

### Seçenek 1: Docker Desktop ile (ÖNERİLEN)

1. **Docker Desktop'ı indirin ve kurun:**
   - https://www.docker.com/products/docker-desktop/
   - Windows için Docker Desktop'ı indirip kurun
   - Kurulumdan sonra bilgisayarı yeniden başlatın

2. **Docker Desktop'ı başlatın** (sistem tepsisinde Docker ikonu görünmeli)

3. **PostgreSQL'i başlatın:**
   ```powershell
   cd c:\bediralvesil-backend
   docker-compose up -d postgres
   ```

4. **PostgreSQL'in çalıştığını kontrol edin:**
   ```powershell
   docker ps
   ```
   `bediralvesil-postgres` container'ının çalıştığını görmelisiniz.

5. **Backend'i başlatın:**
   ```powershell
   python run_server.py
   ```

### Seçenek 2: Sistem PostgreSQL Kurulumu

Eğer sisteminizde PostgreSQL kuruluysa:

1. **PostgreSQL servisini başlatın:**
   ```powershell
   # Windows Services'ten PostgreSQL servisini başlatın
   # Veya PowerShell'de (yönetici olarak):
   Start-Service postgresql-x64-16
   # (Servis adı PostgreSQL versiyonunuza göre değişebilir)
   ```

2. **`.env` dosyasını düzenleyin:**
   - `POSTGRESQL_HOST=localhost`
   - `POSTGRESQL_PORT=5432` (veya kurulumunuzdaki port)
   - `POSTGRESQL_DATABASE=bediralvesil_db` (veritabanını oluşturmanız gerekebilir)
   - `POSTGRESQL_USERNAME=postgres` (veya kullanıcı adınız)
   - `POSTGRESQL_PASSWORD=postgres123` (veya şifreniz)

3. **Veritabanını oluşturun:**
   ```sql
   CREATE DATABASE bediralvesil_db;
   ```

4. **Backend'i başlatın:**
   ```powershell
   python run_server.py
   ```

### Seçenek 3: PostgreSQL Kurulumu Yoksa

PostgreSQL kurulu değilse:

1. **PostgreSQL'i indirin ve kurun:**
   - https://www.postgresql.org/download/windows/
   - PostgreSQL 16'yı indirip kurun
   - Kurulum sırasında şifre belirleyin (örn: `postgres123`)

2. **Yukarıdaki "Seçenek 2" adımlarını takip edin**

## Hızlı Test

PostgreSQL'in çalışıp çalışmadığını test etmek için:

```powershell
# Port kontrolü
Test-NetConnection -ComputerName localhost -Port 5432
```

Bağlantı başarılıysa `TcpTestSucceeded : True` görmelisiniz.

## Sorun Giderme

- **"Connection refused" hatası:** PostgreSQL çalışmıyor, yukarıdaki adımları takip edin
- **"Authentication failed" hatası:** `.env` dosyasındaki kullanıcı adı/şifreyi kontrol edin
- **"Database does not exist" hatası:** Veritabanını oluşturun: `CREATE DATABASE bediralvesil_db;`

