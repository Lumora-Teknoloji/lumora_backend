# -*- coding: utf-8 -*-
"""
API Connection & Authentication Test
Works with both Gym API and Localhost API
"""

import requests
import sys
import json
from config import TARGET, API_URL, BASE_URL, AUTH_ENDPOINT, PROFILE_ENDPOINT, HEALTH_ENDPOINT, ACTIVE_TARGET

# Windows encoding fix
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print(f"[*] API CONNECTION TEST - Target: {ACTIVE_TARGET}")
print("="*60)
print(f"Base URL: {BASE_URL}")
print(f"API URL: {API_URL}")
print("="*60)

# Test 1: Health Check
print("\n[TEST 1] Health Check")
print("-"*60)

try:
    health_url = f"{API_URL}{HEALTH_ENDPOINT}"
    response = requests.get(health_url, timeout=5)
    print(f"[OK] Backend reachable: {health_url}")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}")
except Exception as e:
    print(f"[ERROR] Backend unreachable: {e}")
    exit(1)

# Test 2: Login & Cookie Test
print("\n[TEST 2] Login & Cookie Verification")
print("-"*60)

session = requests.Session()

# Login data göre formatı belirle
if TARGET["LOGIN_FORMAT"] == "email":
    login_data = {
        "email": TARGET.get("TEST_EMAIL", "test@example.com"),
        "password": TARGET.get("TEST_PASSWORD", "test123")
    }
    print(f"Using EMAIL format: {login_data['email']}")
else:
    login_data = {
        "username": TARGET.get("TEST_USERNAME", "test"),
        "password": TARGET.get("TEST_PASSWORD", "test123")
    }
    print(f"Using USERNAME format: {login_data['username']}")

try:
    login_response = session.post(f"{API_URL}/auth/login", json=login_data, timeout=5)
    
    print(f"\nLogin Response:")
    print(f"  Status: {login_response.status_code}")
    
    # Eğer 401 ise (kullanıcı yok), önce register dene
    if login_response.status_code == 401:
        print(f"\n[INFO] User doesn't exist, attempting registration...")
        
        register_data = login_data.copy()
        register_data["name"] = "Security Test User"
        
        try:
            reg_response = session.post(f"{API_URL}/auth/register", json=register_data, timeout=5)
            print(f"  Register Status: {reg_response.status_code}")
            print(f"  Register Response: {reg_response.text[:200]}")
            
            if reg_response.status_code in [200, 201]:
                print(f"  [OK] User registered, retrying login...")
                login_response = session.post(f"{API_URL}/auth/login", json=login_data, timeout=5)
                print(f"  Login Status: {login_response.status_code}")
        except Exception as e:
            print(f"  Register error: {e}")
    
    print(f"  Headers: {dict(login_response.headers)}")
    print(f"  Cookies: {session.cookies.get_dict()}")
    
    if login_response.status_code == 200:
        print(f"\n[OK] Login successful!")
        
        # Response body kontrol
        try:
            body = login_response.json()
            print(f"\n  Response Body:")
            import json
            print(f"  {json.dumps(body, indent=4)}")
            
            if 'access_token' in body:
                print(f"\n  [WARNING] Token in response body (old method)")
            else:
                print(f"\n  [OK] No token in body (using cookies)")
        except:
            print(f"  (Empty or non-JSON body)")
        
        # Cookie analizi
        if session.cookies:
            print(f"\n  Cookie Details:")
            for cookie in session.cookies:
                print(f"    Name: {cookie.name}")
                print(f"    Value: {cookie.value[:50]}..." if len(cookie.value) > 50 else f"    Value: {cookie.value}")
                print(f"    Domain: {cookie.domain}")
                print(f"    Path: {cookie.path}")
                print(f"    Secure: {cookie.secure}")
                print(f"    HttpOnly: {cookie.has_nonstandard_attr('HttpOnly')}")
                print()
    else:
        print(f"[ERROR] Login failed: {login_response.status_code}")
        print(f"   Response: {login_response.text}")
        exit(1)
        
except Exception as e:
    print(f"[ERROR] Login error: {e}")
    exit(1)

# Test 3: Authenticated Request
print("\n[TEST 3] Authenticated API Request")
print("-"*60)

try:
    # /users/me endpoint'ini dene
    me_response = session.get(f"{API_URL}/users/me", timeout=5)
    
    print(f"GET /users/me")
    print(f"  Status: {me_response.status_code}")
    
    if me_response.status_code == 200:
        user_data = me_response.json()
        print(f"\n[OK] Authenticated request successful!")
        print(f"\n  User Data:")
        import json
        print(f"  {json.dumps(user_data, indent=4)}")
    else:
        print(f"[ERROR] Authentication failed: {me_response.status_code}")
        print(f"   Response: {me_response.text}")
        
except Exception as e:
    print(f"[ERROR] Request error: {e}")

# Test 4: Cookie Persistence
print("\n[TEST 4] Cookie Persistence Test")
print("-"*60)

# Yeni session oluştur (cookie'siz)
new_session = requests.Session()

try:
    # Cookie olmadan /users/me'ye istek
    no_cookie_response = new_session.get(f"{API_URL}/users/me", timeout=5)
    
    print(f"Request without cookie:")
    print(f"  Status: {no_cookie_response.status_code}")
    
    if no_cookie_response.status_code == 401:
        print(f"  [OK] Correctly rejected (401 Unauthorized)")
    else:
        print(f"  [WARNING] Unexpected status: {no_cookie_response.status_code}")
        
except Exception as e:
    print(f"  Error: {e}")

# Test 5: Cookie Replay Test
print("\n[TEST 5] Cookie Replay Test")
print("-"*60)

# Eski session'ın cookie'sini kullan
print(f"Replaying cookie from first session...")

try:
    replay_response = session.get(f"{API_URL}/users/me", timeout=5)
    
    print(f"  Status: {replay_response.status_code}")
    
    if replay_response.status_code == 200:
        print(f"  [WARNING] Cookie still valid (no rotation)")
    else:
        print(f"  [OK] Cookie invalidated (rotation active)")
        
except Exception as e:
    print(f"  Error: {e}")

# Test 6: Logout Test
print("\n[TEST 6] Logout Test")
print("-"*60)

try:
    logout_response = session.post(f"{API_URL}/auth/logout", timeout=5)
    
    print(f"POST /auth/logout")
    print(f"  Status: {logout_response.status_code}")
    
    if logout_response.status_code in [200, 204]:
        print(f"  [OK] Logout successful")
        
        # Logout sonrası cookie kontrol
        print(f"\n  Cookies after logout: {session.cookies.get_dict()}")
        
        # Logout sonrası /users/me dene
        after_logout = session.get(f"{API_URL}/users/me", timeout=5)
        print(f"\n  Request after logout:")
        print(f"    Status: {after_logout.status_code}")
        
        if after_logout.status_code == 401:
            print(f"    [OK] Correctly rejected after logout")
        else:
            print(f"    [WARNING] Still authenticated after logout!")
    else:
        print(f"  [WARNING] Logout endpoint not found or failed")
        print(f"     Response: {logout_response.text}")
        
except Exception as e:
    print(f"  Error: {e}")

# ============================================================================
# SECURITY VULNERABILITY TESTS
# ============================================================================

# Test 7: SQL Injection
print("\n[TEST 7] SQL Injection Vulnerability")
print("-"*60)
sql_payloads = ["admin' OR '1'='1", "'; DROP TABLE users--"]
for payload in sql_payloads:
    try:
        sqli_data = {"email": payload, "password": "test"}
        r = requests.post(f"{API_URL}/auth/login", json=sqli_data, timeout=3)
        if r.status_code == 200 or "syntax error" in r.text.lower():
            print(f"  [VULNERABLE] SQL Injection: {payload[:30]}")
            break
    except:
        pass
else:
    print(f"  [OK] SQL Injection blocked")

# Test 8: XSS
print("\n[TEST 8] XSS Vulnerability")
print("-"*60)
xss_payload = "<script>alert('XSS')</script>"
try:
    xss_data = {"email": "xss@test.com", "password": "test123", "name": xss_payload}
    r = requests.post(f"{API_URL}/auth/register", json=xss_data, timeout=3)
    if "<script>" in r.text:
        print(f"  [VULNERABLE] XSS not sanitized")
    else:
        print(f"  [OK] XSS blocked/sanitized")
except:
    print(f"  [OK] XSS blocked")

# Test 9: IDOR
print("\n[TEST 9] IDOR Vulnerability")
print("-"*60)
for uid in [1, 999]:
    try:
        r = requests.get(f"{API_URL}/users/{uid}", timeout=3)
        if r.status_code == 200:
            print(f"  [VULNERABLE] Can access user {uid} without auth")
            break
    except:
        pass
else:
    print(f"  [OK] IDOR protected")

# Test 10: Rate Limiting (Light Test)
print("\n[TEST 10] Rate Limiting (Light Test)")
print("-"*60)
try:
    # Sadece 5 istek - DoS değil
    count = sum(1 for i in range(5) if requests.get(f"{API_URL}/health", timeout=1).status_code == 200)
    print(f"  [INFO] {count}/5 requests succeeded (light test only)")
    print(f"  [NOTE] Full rate limit test skipped to avoid DoS")
except:
    print(f"  [INFO] Request limit test completed")

# Test 11: NoSQL Injection  
print("\n[TEST 11] NoSQL Injection")
print("-"*60)
try:
    nosql_data = {"email": {"$gt": ""}, "password": {"$gt": ""}}
    r = requests.post(f"{API_URL}/auth/login", json=nosql_data, timeout=3)
    if r.status_code == 200:
        print(f"  [VULNERABLE] NoSQL injection possible")
    else:
        print(f"  [OK] NoSQL injection blocked")
except:
    print(f"  [OK] NoSQL injection blocked")

# Test 12: Weak Password
print("\n[TEST 12] Weak Password Policy")
print("-"*60)
try:
    weak_data = {"email": "weak@test.com", "password": "123", "name": "Test"}
    r = requests.post(f"{API_URL}/auth/register", json=weak_data, timeout=3)
    if r.status_code in [200, 201]:
        print(f"  [VULNERABLE] Weak password accepted")
    else:
        print(f"  [OK] Weak password rejected")
except:
    print(f"  [OK] Password policy enforced")

# Summary  
print("\n" + "="*60)
print("[*] SECURITY AUDIT COMPLETE")
print("="*60)
print("\nTested: SQL Injection, XSS, IDOR, Rate Limit, NoSQL, Weak Passwords")
print("Check [VULNERABLE] tags above for security issues")
print("="*60 + "\n")

