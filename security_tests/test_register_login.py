# -*- coding: utf-8 -*-
"""
Test Registration + Login Flow
"""
import requests
import json
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_URL = "https://gym-api.algorynth.net"

print("="*80)
print("REGISTRATION + LOGIN TEST")
print("="*80)

# Test 1: Find Register Endpoint
print("\n[STEP 1] Finding Registration Endpoint...")
print("-"*80)

register_endpoints = [
    "/api/auth/register",
    "/api/auth/signup",
    "/api/register",
    "/api/signup",
    "/api/users/register",
    "/api/users"
]

found_register = None

for endpoint in register_endpoints:
    try:
        url = API_URL + endpoint
        r = requests.post(url, json={}, timeout=3)
        if r.status_code != 404:
            print(f"[FOUND] {endpoint} -> {r.status_code}")
            print(f"  Response: {r.text[:150]}")
            if found_register is None:
                found_register = endpoint
    except:
        pass

# Test 2: Try to Register
if found_register:
    print(f"\n[STEP 2] Attempting Registration at {found_register}")
    print("-"*80)
    
    # Test user
    test_email = "test_security@example.com"
    test_password = "TestPass123!"
    
    register_data = {
        "email": test_email,
        "password": test_password,
        "name": "Security Test User"
    }
    
    print(f"Registering: {register_data}")
    
    try:
        r = requests.post(API_URL + found_register, json=register_data, timeout=5)
        print(f"\nStatus: {r.status_code}")
        print(f"Response: {r.text}")
        
        if r.status_code in [200, 201]:
            print("\n[SUCCESS] Registration successful!")
            
            # Test 3: Login with new credentials
            print(f"\n[STEP 3] Logging in with new credentials...")
            print("-"*80)
            
            login_data = {
                "email": test_email,
                "password": test_password
            }
            
            login_r = requests.post(f"{API_URL}/api/auth/login", json=login_data, timeout=5)
            print(f"Status: {login_r.status_code}")
            print(f"Response: {login_r.text}")
            print(f"Cookies: {login_r.cookies.get_dict()}")
            print(f"Headers: {dict(login_r.headers)}")
            
            if login_r.status_code == 200:
                print("\n[SUCCESS] Login successful!")
                
                # Test 4: Access Protected Resource
                print(f"\n[STEP 4] Accessing /api/profile...")
                print("-"*80)
                
                # Try with cookies
                session = requests.Session()
                session.cookies.update(login_r.cookies)
                
                profile_r = session.get(f"{API_URL}/api/profile", timeout=5)
                print(f"Status: {profile_r.status_code}")
                print(f"Response: {profile_r.text}")
                
                # Try with Authorization header
                try:
                    response_data = login_r.json()
                    if 'token' in response_data or 'access_token' in response_data:
                        token = response_data.get('token') or response_data.get('access_token')
                        print(f"\n[TESTING WITH TOKEN]")
                        headers = {"Authorization": f"Bearer {token}"}
                        profile_r2 = requests.get(f"{API_URL}/api/profile", headers=headers, timeout=5)
                        print(f"Status: {profile_r2.status_code}")
                        print(f"Response: {profile_r2.text}")
                except:
                    pass
        else:
            print(f"\n[INFO] Registration failed - user may already exist")
            print(f"Trying to login with existing credentials...")
            
            # Try login anyway
            login_data = {
                "email": test_email,
                "password": test_password
            }
            
            login_r = requests.post(f"{API_URL}/api/auth/login", json=login_data, timeout=5)
            print(f"\nLogin Status: {login_r.status_code}")
            print(f"Login Response: {login_r.text}")
            
    except Exception as e:
        print(f"Error: {e}")

else:
    print("\n[INFO] No registration endpoint found")
    print("Try using the original credentials with email format:")
    print('  {"email": "asdasd1@example.com", "password": "asdasd1"}')

# Test 3: Try original credentials with email format
print(f"\n[FINAL TEST] Login with original username as email")
print("-"*80)

# Maybe the username IS the email?
credentials_to_try = [
    {"email": "asdasd1", "password": "asdasd1"},
    {"email": "asdasd1@gym.com", "password": "asdasd1"},
    {"email": "admin@gym.com", "password": "asdasd1"},
]

for cred in credentials_to_try:
    try:
        print(f"\nTrying: {cred}")
        r = requests.post(f"{API_URL}/api/auth/login", json=cred, timeout=5)
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            print(f"  [SUCCESS] {r.text}")
            print(f"  Cookies: {r.cookies.get_dict()}")
            break
        else:
            print(f"  Response: {r.text[:100]}")
    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "="*80)
print("TESTING COMPLETE")
print("="*80)
