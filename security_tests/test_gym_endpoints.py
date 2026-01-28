# -*- coding: utf-8 -*-
"""
Test Found Endpoints + Auth Discovery
"""
import requests
import json
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_URL = "https://gym-api.algorynth.net"

print("="*80)
print("TESTING FOUND ENDPOINTS")
print("="*80)

# Test 1: Health Endpoint
print("\n[TEST 1] /api/health")
print("-"*80)
try:
    r = requests.get(f"{API_URL}/api/health", timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
    print(f"Headers: {dict(r.headers)}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Profile Endpoint (requires auth)
print("\n[TEST 2] /api/profile (without auth)")
print("-"*80)
try:
    r = requests.get(f"{API_URL}/api/profile", timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Auth Endpoint Discovery (manuel test)
print("\n[TEST 3] Searching for Auth Endpoint...")
print("-"*80)

auth_variations = [
    "/api/auth/login",
    "/api/auth/signin", 
    "/api/users/login",
    "/api/login",
    "/api/signin",
    "/api/auth/token",
    "/api/token",
    "/auth/login",
    "/login",
    "/api/authenticate",
    "/api/session/create"
]

found_auth = None

for endpoint in auth_variations:
    url = API_URL + endpoint
    try:
        # POST ile boş body gönder
        r = requests.post(url, json={}, timeout=3)
        if r.status_code != 404:
            print(f"\n[FOUND] {endpoint} -> {r.status_code}")
            print(f"  Response: {r.text[:200]}")
            
            if found_auth is None:
                found_auth = endpoint
            
            # Farklı payload'lar dene
            payloads = [
                {"username": "test", "password": "test"},
                {"email": "test@test.com", "password": "test"},
                {"user": "test", "pass": "test"},
                {"identifier": "test", "password": "test"}
            ]
            
            print(f"\n  Testing different payloads:")
            for i, payload in enumerate(payloads, 1):
                try:
                    r2 = requests.post(url, json=payload, timeout=3)
                    print(f"    {i}. {payload}")
                    print(f"       Status: {r2.status_code}, Response: {r2.text[:100]}")
                except:
                    pass
    except:
        pass

# Test 4: Kullanıcı bilgileri ile login dene
if found_auth:
    print(f"\n[TEST 4] Testing Login with Real Credentials")
    print("-"*80)
    print(f"Endpoint: {found_auth}")
    
    # Gerçek credentials
    real_payloads = [
        {"username": "asdasd1", "password": "asdasd1"},
        {"email": "asdasd1@test.com", "password": "asdasd1"},
    ]
    
    for payload in real_payloads:
        try:
            print(f"\nTrying: {payload}")
            r = requests.post(API_URL + found_auth, json=payload, timeout=5)
            print(f"  Status: {r.status_code}")
            print(f"  Response: {r.text[:300]}")
            
            if r.status_code == 200:
                print(f"\n  [SUCCESS] Login worked!")
                print(f"  Cookies: {r.cookies.get_dict()}")
                print(f"  Headers: {dict(r.headers)}")
                
                # Profile'a erişmeyi dene
                session = requests.Session()
                session.cookies.update(r.cookies)
                
                profile_r = session.get(f"{API_URL}/api/profile", timeout=5)
                print(f"\n  [TESTING PROFILE ACCESS]")
                print(f"  Status: {profile_r.status_code}")
                print(f"  Response: {profile_r.text[:200]}")
                
        except Exception as e:
            print(f"  Error: {e}")
else:
    print("\n[INFO] No auth endpoint found in common paths")
    print("You may need to check the actual API documentation")

# Test 5: OPTIONS request (CORS check)
print("\n[TEST 5] CORS Configuration")
print("-"*80)
try:
    r = requests.options(API_URL, timeout=5)
    print(f"Status: {r.status_code}")
    cors_headers = {k: v for k, v in r.headers.items() if 'access-control' in k.lower()}
    print(f"CORS Headers: {json.dumps(cors_headers, indent=2)}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*80)
print("TESTING COMPLETE")
print("="*80)
