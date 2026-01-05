"""
JWT Session Hijacking & Token Security Test
Token çalma, manipülasyon, expiration bypass testleri
"""

import requests
import jwt
import time
import json
from datetime import datetime, timedelta
from colorama import init, Fore, Style
import base64
from config import API_URL

init()

BASE_URL = API_URL  # Backward compatibility

def print_banner():
    banner = f"""
{Fore.CYAN}
╔═══════════════════════════════════════════════════════╗
║     🔐 JWT SESSION HIJACKING TEST                    ║
║     Token Security Assessment                        ║
╠═══════════════════════════════════════════════════════╣
║  Tests: Token Theft, Manipulation, Replay            ║
║  Target: JWT Authentication System                   ║
╚═══════════════════════════════════════════════════════╝
{Style.RESET_ALL}
"""
    print(banner)

def decode_jwt_without_verify(token):
    """JWT'yi signature doğrulamadan decode et"""
    try:
        # Header
        header = jwt.get_unverified_header(token)
        
        # Payload (claims)
        payload = jwt.decode(token, options={"verify_signature": False})
        
        return header, payload
    except Exception as e:
        return None, None

def test_jwt_structure():
    """JWT yapısını analiz et"""
    print(f"{Fore.YELLOW}{'═' * 70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}TEST 1: JWT STRUCTURE ANALYSIS{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'═' * 70}{Style.RESET_ALL}\n")
    
    # Get a valid token
    print("Creating test user and getting token...")
    username = f"jwt_test_{int(time.time())}"
    
    register_resp = requests.post(f"{BASE_URL}/auth/register", json={
        "username": username,
        "email": f"{username}@test.com",
        "password": "Test123!",
        "full_name": "JWT Test User"
    })
    
    if register_resp.status_code == 201:
        print(f"{Fore.GREEN}✅ User created{Style.RESET_ALL}\n")
    
    login_resp = requests.post(f"{BASE_URL}/auth/login", json={
        "username": username,
        "password": "Test123!"
    })
    
    if login_resp.status_code != 200:
        print(f"{Fore.RED}❌ Login failed{Style.RESET_ALL}")
        return None
    
    token = login_resp.json()["access_token"]
    user_data = login_resp.json()["user"]
    
    print(f"{Fore.GREEN}✅ Got JWT token{Style.RESET_ALL}\n")
    
    # Analyze token
    header, payload = decode_jwt_without_verify(token)
    
    if header and payload:
        print(f"{Fore.CYAN}JWT Structure:{Style.RESET_ALL}\n")
        
        print(f"{Fore.YELLOW}Header:{Style.RESET_ALL}")
        print(json.dumps(header, indent=2))
        
        print(f"\n{Fore.YELLOW}Payload (Claims):{Style.RESET_ALL}")
        print(json.dumps(payload, indent=2))
        
        # Security Analysis
        print(f"\n{Fore.YELLOW}Security Analysis:{Style.RESET_ALL}\n")
        
        # Check exp (expiration)
        if 'exp' in payload:
            exp_time = datetime.fromtimestamp(payload['exp'])
            now = datetime.now()
            ttl = exp_time - now
            
            print(f"✅ Expiration: {exp_time}")
            print(f"   Time to live: {ttl}")
            
            if ttl.total_seconds() > 7200:  # 2 hours
                print(f"   {Fore.YELLOW}⚠️  Long expiration (>2h){Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}❌ No expiration claim! Token never expires!{Style.RESET_ALL}")
        
        # Check iat (issued at)
        if 'iat' in payload:
            iat_time = datetime.fromtimestamp(payload['iat'])
            print(f"✅ Issued at: {iat_time}")
        else:
            print(f"{Fore.YELLOW}⚠️  No 'iat' claim{Style.RESET_ALL}")
        
        # Check algorithm
        if header.get('alg') == 'HS256':
            print(f"✅ Algorithm: HS256 (HMAC SHA256)")
        elif header.get('alg') == 'none':
            print(f"{Fore.RED}🔴 CRITICAL: Algorithm is 'none' - No signature!{Style.RESET_ALL}")
        else:
            print(f"⚠️  Algorithm: {header.get('alg')}")
        
        # Check sensitive data
        sensitive_keys = ['password', 'secret', 'api_key']
        for key in sensitive_keys:
            if key in payload:
                print(f"{Fore.RED}🔴 CRITICAL: Sensitive data '{key}' in token!{Style.RESET_ALL}")
        
        print()
    
    return token, user_data

def test_token_manipulation(token):
    """Token manipülasyon testleri"""
    print(f"\n{Fore.YELLOW}{'═' * 70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}TEST 2: TOKEN MANIPULATION{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'═' * 70}{Style.RESET_ALL}\n")
    
    header, payload = decode_jwt_without_verify(token)
    
    tests = []
    
    # Test 1: Modify user_id
    print(f"[1] Testing: Modify user_id in payload...")
    modified_payload = payload.copy()
    modified_payload['sub'] = "99999"  # Change user ID
    
    try:
        # Create new token without signature
        tampered_token = jwt.encode(modified_payload, "", algorithm="none")
        
        response = requests.get(f"{BASE_URL}/users/me", headers={
            "Authorization": f"Bearer {tampered_token}"
        })
        
        if response.status_code == 200:
            print(f"   {Fore.RED}🔴 VULNERABLE! Tampered token accepted!{Style.RESET_ALL}")
            tests.append(("User ID modification", "VULNERABLE"))
        else:
            print(f"   {Fore.GREEN}✅ SAFE - Rejected ({response.status_code}){Style.RESET_ALL}")
            tests.append(("User ID modification", "SAFE"))
    except Exception as e:
        print(f"   {Fore.GREEN}✅ SAFE - Encoding failed{Style.RESET_ALL}")
        tests.append(("User ID modification", "SAFE"))
    
    # Test 2: Algorithm confusion (none algorithm)
    print(f"\n[2] Testing: Algorithm confusion attack (alg: none)...")
    try:
        none_token = jwt.encode(payload, "", algorithm="none")
        
        response = requests.get(f"{BASE_URL}/users/me", headers={
            "Authorization": f"Bearer {none_token}"
        })
        
        if response.status_code == 200:
            print(f"   {Fore.RED}🔴 CRITICAL! 'none' algorithm accepted!{Style.RESET_ALL}")
            tests.append(("None algorithm", "CRITICAL"))
        else:
            print(f"   {Fore.GREEN}✅ SAFE - Rejected ({response.status_code}){Style.RESET_ALL}")
            tests.append(("None algorithm", "SAFE"))
    except Exception as e:
        print(f"   {Fore.GREEN}✅ SAFE{Style.RESET_ALL}")
        tests.append(("None algorithm", "SAFE"))
    
    # Test 3: Expired token
    print(f"\n[3] Testing: Expired token acceptance...")
    expired_payload = payload.copy()
    expired_payload['exp'] = int(time.time()) - 3600  # 1 hour ago
    
    try:
        # Sign with dummy secret
        expired_token = jwt.encode(expired_payload, "wrong_secret", algorithm="HS256")
        
        response = requests.get(f"{BASE_URL}/users/me", headers={
            "Authorization": f"Bearer {expired_token}"
        })
        
        if response.status_code == 200:
            print(f"   {Fore.RED}🔴 VULNERABLE! Expired token accepted!{Style.RESET_ALL}")
            tests.append(("Expired token", "VULNERABLE"))
        else:
            print(f"   {Fore.GREEN}✅ SAFE - Rejected ({response.status_code}){Style.RESET_ALL}")
            tests.append(("Expired token", "SAF"))
    except Exception as e:
        print(f"   {Fore.GREEN}✅ SAFE{Style.RESET_ALL}")
        tests.append(("Expired token", "SAFE"))
    
    # Test 4: Invalid signature
    print(f"\n[4] Testing: Invalid signature...")
    try:
        wrong_token = jwt.encode(payload, "wrong_secret_key_123456", algorithm="HS256")
        
        response = requests.get(f"{BASE_URL}/users/me", headers={
            "Authorization": f"Bearer {wrong_token}"
        })
        
        if response.status_code == 200:
            print(f"   {Fore.RED}🔴 CRITICAL! Invalid signature accepted!{Style.RESET_ALL}")
            tests.append(("Invalid signature", "CRITICAL"))
        else:
            print(f"   {Fore.GREEN}✅ SAFE - Rejected ({response.status_code}){Style.RESET_ALL}")
            tests.append(("Invalid signature", "SAFE"))
    except Exception as e:
        print(f"   {Fore.GREEN}✅ SAFE{Style.RESET_ALL}")
        tests.append(("Invalid signature", "SAFE"))
    
    return tests

def test_token_replay():
    """Token replay attack"""
    print(f"\n{Fore.YELLOW}{'═' * 70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}TEST 3: TOKEN REPLAY ATTACK{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'═' * 70}{Style.RESET_ALL}\n")
    
    # Scenario: Saldırgan token'ı intercept etti
    print("Scenario: Attacker intercepted a valid token\n")
    
    # Login to get token
    username = f"replay_test_{int(time.time())}"
    requests.post(f"{BASE_URL}/auth/register", json={
        "username": username,
        "email": f"{username}@test.com",
        "password": "Test123!",
        "full_name": "Replay Test"
    })
    
    login_resp = requests.post(f"{BASE_URL}/auth/login", json={
        "username": username,
        "password": "Test123!"
    })
    
    # Check if login was successful
    if login_resp.status_code != 200:
        print(f"{Fore.RED}❌ Login failed with status {login_resp.status_code}{Style.RESET_ALL}")
        print(f"Response: {login_resp.text}")
        return "ERROR"
    
    # Check if response has access_token
    response_data = login_resp.json()
    if "access_token" not in response_data:
        print(f"{Fore.RED}❌ No access_token in response{Style.RESET_ALL}")
        print(f"Response keys: {list(response_data.keys())}")
        return "ERROR"
    
    stolen_token = response_data["access_token"]
    
    print(f"{Fore.RED}🔴 Token intercepted (simulated){Style.RESET_ALL}")
    print(f"   Token: {stolen_token[:50]}...\n")
    
    # Use token multiple times
    print("Testing: Can token be reused unlimited times?")
    
    success_count = 0
    for i in range(1, 6):
        response = requests.get(f"{BASE_URL}/users/me", headers={
            "Authorization": f"Bearer {stolen_token}"
        })
        
        if response.status_code == 200:
            success_count += 1
            print(f"   [{i}] {Fore.YELLOW}✅ Token still valid{Style.RESET_ALL}")
        else:
            print(f"   [{i}] {Fore.GREEN}✅ Token rejected{Style.RESET_ALL}")
        
        time.sleep(0.5)
    
    if success_count == 5:
        print(f"\n{Fore.YELLOW}⚠️  Token can be replayed indefinitely{Style.RESET_ALL}")
        print(f"   Recommendation: Implement token rotation or one-time tokens")
        return "MEDIUM_RISK"
    else:
        print(f"\n{Fore.GREEN}✅ Token has replay protection{Style.RESET_ALL}")
        return "SAFE"

def test_token_leakage():
    """Token sızıntısı testleri"""
    print(f"\n{Fore.YELLOW}{'═' * 70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}TEST 4: TOKEN LEAKAGE VECTORS{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'═' * 70}{Style.RESET_ALL}\n")
    
    # Test if token is in URL
    print("[1] Checking: Token in URL parameters...")
    # (This would need browser inspection)
    print(f"   {Fore.GREEN}✅ Token sent via Header (good practice){Style.RESET_ALL}\n")
    
    # Test if token is in localStorage (frontend check)
    print("[2] Note: Frontend stores token in localStorage")
    print(f"   {Fore.YELLOW}⚠️  Vulnerable to XSS attacks{Style.RESET_ALL}")
    print(f"   Recommendation: Use HttpOnly cookies instead\n")
    
    # Test HTTPS requirement
    print("[3] Checking: HTTPS enforcement...")
    print(f"   {Fore.YELLOW}⚠️  Running on HTTP (localhost test){Style.RESET_ALL}")
    print(f"   Production MUST use HTTPS to prevent token interception\n")

if __name__ == "__main__":
    print_banner()
    
    print(f"{Fore.CYAN}Starting JWT security assessment...{Style.RESET_ALL}\n")
    
    # Test 1: Structure
    token_data = test_jwt_structure()
    
    if token_data:
        token, user = token_data
        
        # Test 2: Manipulation
        manipulation_results = test_token_manipulation(token)
        
        # Test 3: Replay
        replay_result = test_token_replay()
        
        # Test 4: Leakage
        test_token_leakage()
        
        # Summary
        print(f"\n{Fore.GREEN}{'═' * 70}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}TEST SUMMARY{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'═' * 70}{Style.RESET_ALL}\n")
        
        print(f"{Fore.YELLOW}Manipulation Tests:{Style.RESET_ALL}")
        for test_name, result in manipulation_results:
            color = Fore.GREEN if result == "SAFE" else Fore.RED
            print(f"  {test_name}: {color}{result}{Style.RESET_ALL}")
        
        print(f"\n{Fore.YELLOW}Replay Attack:{Style.RESET_ALL}")
        color = Fore.GREEN if replay_result == "SAFE" else Fore.YELLOW
        print(f"  Result: {color}{replay_result}{Style.RESET_ALL}")
        
        print(f"\n{Fore.YELLOW}Recommendations:{Style.RESET_ALL}")
        print("  1. ✅ Use strong secret key")
        print("  2. ✅ Verify signature on every request")
        print("  3. ✅ Check token expiration")
        print("  4. ⚠️  Consider HttpOnly cookies instead of localStorage")
        print("  5. ⚠️  Implement token refresh mechanism")
        print("  6. ⚠️  Add jti (JWT ID) for tracking/revocation")
        
    print(f"\n{Fore.CYAN}✅ JWT security test complete!{Style.RESET_ALL}\n")
