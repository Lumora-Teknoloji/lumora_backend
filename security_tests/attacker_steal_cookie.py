"""
ATTACKER SCRIPT 1: Steal Cookie
SEN SALDIRGANSIN! Bu scripti çalıştır.
"""

import json
from colorama import init, Fore, Style

init()

print(f"{Fore.RED}{'='*60}{Style.RESET_ALL}")
print(f"{Fore.RED}🔴 ATTACKER: STEALING COOKIE{Style.RESET_ALL}")
print(f"{Fore.RED}{'='*60}{Style.RESET_ALL}\n")

# Cookie'yi oku
try:
    with open('victim_cookie.json', 'r') as f:
        stolen_cookie = json.load(f)
    
    print(f"{Fore.RED}🔴 [ATTACKER/YOU] Cookie stolen successfully!{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}Stolen cookie details:{Style.RESET_ALL}")
    for key, value in stolen_cookie.items():
        print(f"  {key} = {value}")
    
    # Saldırgan için kopyala
    with open('attacker_cookie.json', 'w') as f:
        json.dump(stolen_cookie, f, indent=2)
    
    print(f"\n✅ Cookie saved to: attacker_cookie.json")
    print(f"   (Senin kullanman için)")
    
    print(f"\n{Fore.RED}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.RED}NEXT STEP:{Style.RESET_ALL}")
    print(f"{Fore.RED}{'='*60}{Style.RESET_ALL}\n")
    print("Şimdi çalınan cookie'yi kullan:")
    print("  py attacker_use_cookie.py")
    
except FileNotFoundError:
    print(f"{Fore.RED}❌ victim_cookie.json not found!{Style.RESET_ALL}")
    print("Önce victim_login.py çalıştır!")
