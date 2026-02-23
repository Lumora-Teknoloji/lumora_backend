"""
Cookie Replay Attack - Attacker's Toolkit
SEN SALDIRGANSIN! Bu araçları kullan.

ADIMLAR:
1. victim_login.py - Kurban (ben) login olacak, cookie oluşturacak
2. steal_cookie.py - Sen cookie'yi çalacaksın
3. use_stolen_cookie.py - Sen çalınan cookie ile erişeceksin
"""

import requests
import json
from config import API_URL

print("="*60)
print("STEP 1: VICTIM LOGIN (Kurban - Ben)")
print("="*60)

# Ben (kurban) login oluyorum
victim_session = requests.Session()

print("\n[VICTIM/ME] Logging in...")

login_response = victim_session.post(f"{API_URL}/auth/login", json={
    "username": "asdasd1",
    "password": "asdasd1"
})

if login_response.status_code == 200:
    print("✅ [VICTIM/ME] Login successful!")
    
    # Cookie'leri göster
    victim_cookies = victim_session.cookies.get_dict()
    
    print("\n[VICTIM/ME] My cookies:")
    for key, value in victim_cookies.items():
        print(f"  {key} = {value}")
    
    # Cookie'yi dosyaya kaydet (saldırgan çalacak)
    with open('victim_cookie.json', 'w') as f:
        json.dump(victim_cookies, f, indent=2)
    
    print("\n✅ Cookie saved to: victim_cookie.json")
    print("   (Saldırgan bu dosyayı okuyacak)")
    
    # Kurbanın bilgilerini göster
    me_response = victim_session.get(f"{API_URL}/users/me")
    if me_response.status_code == 200:
        user_data = me_response.json()
        print("\n[VICTIM/ME] My account info:")
        print(json.dumps(user_data, indent=2))
    
    print("\n" + "="*60)
    print("✅ VICTIM SETUP COMPLETE!")
    print("="*60)
    print("\nŞimdi sen (SALDIRGAN) şunu yap:")
    print("1. py attacker_steal_cookie.py")
    print("2. py attacker_use_cookie.py")
    
else:
    print(f"❌ Login failed: {login_response.status_code}")
