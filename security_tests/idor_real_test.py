"""
IDOR Gerçek Test - Alice'e conversation ekleyip Bob'un görmesini test edelim
"""

import requests
import json

BASE_URL = "http://localhost:8000/api"

print("🔍 IDOR GERÇEKLEŞTİRME TESTİ")
print("=" * 70)

# Alice login
print("\n[1] Alice login oluyor...")
alice_login = requests.post(f"{BASE_URL}/auth/login", json={
    "username": "alice_victim",
    "password": "Alice123!"
})

if alice_login.status_code == 200:
    alice_data = alice_login.json()
    alice_token = alice_data["access_token"]
    alice_id = alice_data["user"]["id"]
    print(f"✅ Alice login - ID: {alice_id}")
    
    # Alice conversation oluştur
    print(f"\n[2] Alice 3 GİZLİ conversation oluşturuyor...")
    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    
    conv_titles = [
        "Banka Şifrelerim",
        "Kredi Kartı Bilgileri", 
        "Kişisel Özel Notlar"
    ]
    
    alice_conv_ids = []
    for title in conv_titles:
        conv_resp = requests.post(
            f"{BASE_URL}/conversations",
            headers=alice_headers,
            json={"title": title}
        )
        if conv_resp.status_code == 201:
            conv_id = conv_resp.json()["id"]
            alice_conv_ids.append(conv_id)
            print(f"   ✅ Created: '{title}' (ID: {conv_id})")
        else:
            print(f"   ❌ Error: {conv_resp.text}")
    
    # Alice kendi conversation'larını görsün
    print(f"\n[3] Alice kendi conversation'larını kontrol ediyor...")
    alice_convs = requests.get(f"{BASE_URL}/conversations", headers=alice_headers)
    if alice_convs.status_code == 200:
        convs = alice_convs.json()
        print(f"   ✅ Alice {len(convs)} conversation görebiliyor (kendi)")
        for conv in convs:
            print(f"      - {conv['title']}")
    
    # BOB SALDIRGAN!
    print(f"\n[4] 🚨 BOB (Saldırgan) login oluyor...")
    bob_login = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "bob_attacker",
        "password": "Bob123!"
    })
    
    if bob_login.status_code == 200:
        bob_data = bob_login.json()
        bob_token = bob_data["access_token"]
        bob_id = bob_data["user"]["id"]
        print(f"✅ Bob login - ID: {bob_id}")
        
        # BOB ALICE'İN CONVERSATION'LARINI ÇALACAK!
        print(f"\n[5] 🔴 IDOR SALDIRISI: Bob, Alice'in conversation'larını istiyor...")
        bob_headers = {"Authorization": f"Bearer {bob_token}"}
        
        # Test 1: Query parameter ile
        print(f"\n   🔍 Test 1: Query parameter (user_id={alice_id})")
        attack_1 = requests.get(
            f"{BASE_URL}/conversations?user_id={alice_id}",
            headers=bob_headers
        )
        print(f"   Status: {attack_1.status_code}")
        
        if attack_1.status_code == 200:
            try:
                stolen_convs = attack_1.json()
                print(f"   🔴 VULNERABLE! Bob {len(stolen_convs)} conversation görebiliyor!")
                if stolen_convs:
                    print(f"\n   💀 ÇALANAN CONVERSATION'LAR:")
                    for conv in stolen_convs:
                        print(f"      🚨 '{conv['title']}' (ID: {conv['id']}, Owner: {conv.get('user_id', 'N/A')})")
                    print(f"\n   ⚠️  Bob (ID: {bob_id}), Alice'in (ID: {alice_id}) özel verilerini gördü!")
                else:
                    print(f"   ⚠️  200 OK döndü ama conversation boş")
                    print(f"   📝 Not: Backend user_id parametresini kabul ediyor (VULNERABLE)")
                    print(f"   📝 Not: 403 Forbidden dönmeliydi!")
            except:
                print(f"   Response: {attack_1.text[:200]}")
        elif attack_1.status_code == 403:
            print(f"   🟢 SAFE! Access denied")
        elif attack_1.status_code == 422:
            print(f"   🟢 SAFE! Validation error")
        else:
            print(f"   Detail: {attack_1.text[:200]}")
        
        # Test 2: Alice'in conversation ID'lerini deneme
        if alice_conv_ids:
            print(f"\n   🔍 Test 2: Direkt conversation ID ile")
            for conv_id in alice_conv_ids[:1]:  # İlk conversation'ı dene
                attack_2 = requests.get(
                    f"{BASE_URL}/conversations/{conv_id}",
                    headers=bob_headers
                )
                print(f"   GET /conversations/{conv_id}")
                print(f"   Status: {attack_2.status_code}")
                
                if attack_2.status_code == 200:
                    print(f"   🔴 VULNERABLE! Bob conversation görebiliyor!")
                    try:
                        conv = attack_2.json()
                        print(f"      Başlık: '{conv.get('title')}'")
                    except:
                        pass
                elif attack_2.status_code == 404:
                    print(f"   🟢 SAFE! Not found (ownership check var)")
                elif attack_2.status_code == 403:
                    print(f"   🟢 SAFE! Forbidden")
                else:
                    print(f"   Response: {attack_2.text[:100]}")

print("\n" + "=" * 70)
print("📊 SONUÇ")
print("=" * 70)
print("""
🎯 IDOR Zafiyeti Var mı?

1️⃣ Eğer Bob, Alice'in conversation'larını GÖREBİLDİ → CRITICAL IDOR!
2️⃣ Eğer 200 OK döndü ama BOŞ → MEDIUM IDOR (parameter kabul ediyor)
3️⃣ Eğer 403/404 döndü → SAFE

💡 200 OK Dönmesi Bile Zafiyet!
   Backend şunu kontrol ETMELİ:
   "user_id parametresi current_user'ın ID'sine eşit mi?"
   
   Eğer eşit değilse → 403 Forbidden dönmeli
   Şu anda → 200 OK dönüyor (Yanlış!)
""")

print("\n✅ Test tamamlandı!")
