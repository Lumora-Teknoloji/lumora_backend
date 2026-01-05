# Gym API Security Test - Injection Test Script

## Ne Test Eder?

### 1. SQL Injection
- GET parametrelerinde SQL injection
- Payloads: `1' OR '1'='1`, `UNION SELECT`, `DROP TABLE`
- SQL hata mesajlarını arar

### 2. NoSQL Injection  
- MongoDB injection denemeleri
- Payloads: `{"$gt": ""}`, `{"$ne": null}`, `{"$regex": ".*"}`

### 3. Direct Database Access
- `/api/database`, `/api/db`, `/api/mysql` gibi endpoint'ler
- phpMyAdmin, Adminer gibi yönetim panelleri
- `.env`, `database.yml` gibi config dosyaları

### 4. Path Traversal
- `../../../etc/passwd`
- `../../config/database.yml`
- Dosya sistemi erişimi

### 5. Database Backup Files
- `backup.sql`, `dump.sql`, `database.sql`
- Açıkta kalmış DB yedekleri

### 6. GraphQL Introspection
- Schema bilgisinin alınması
- DB yapısının görülmesi

### 7. Error-based Info Disclosure
- Hata mesajlarında DB bilgisi
- Stack trace'lerde hassas bilgi

## Çalıştırma

```bash
python injection_test.py
```

## Beklenen Çıktı

✅ Güvenli ise:
```
✅ SQL Injection blocked
✅ NoSQL Injection blocked
✅ No direct DB access found
✅ Path traversal blocked
✅ No backup files exposed
✅ No GraphQL or introspection disabled
✅ Generic error messages
```

🚨 Vulnerable ise:
```
🚨 VULNERABLE: SQL error exposed
🚨 FOUND: /api/database -> 200
🚨 VULNERABLE: Path traversal
🚨 FOUND BACKUP: /backup.sql
```

## Sonuç Dosyası

`injection_test_results.json` - Tüm bulgular
