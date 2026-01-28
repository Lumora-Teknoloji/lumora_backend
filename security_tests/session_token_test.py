# -*- coding: utf-8 -*-
"""
Session Storage & Token Access Test
Target: Auth system, sessions, tokens
"""
import requests
import json
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_URL = "https://gym-api.algorynth.net"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjo2LCJlbWFpbCI6InRlc3Rfc2VjdXJpdHlAZXhhbXBsZS5jb20iLCJpc3MiOiJneW0tdHJhY2tlci1hcGkiLCJleHAiOjE3Njc0Mzk0ODYsImlhdCI6MTc2NzM1MzA4Nn0.SJFr0yGvNspzbQktTDLB81Lb6DHsREXjcnUEbngUE1c"

print("="*80)
print("SESSION STORAGE & TOKEN ACCESS TEST")
print("="*80)

headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

# Test 1: Session Endpoints
print("\n[TEST 1] Session Management Endpoints")
print("-"*80)

session_endpoints = [
    "/api/sessions",
    "/api/auth/sessions",
    "/api/user/sessions",
    "/api/active-sessions",
    "/sessions",
    "/api/tokens",
    "/api/auth/tokens",
    "/api/user/tokens"
]

for endpoint in session_endpoints:
    try:
        r = requests.get(f"{API_URL}{endpoint}", headers=headers, timeout=3)
        
        if r.status_code == 200:
            print(f"  🚨 FOUND: {endpoint} -> {r.status_code}")
            print(f"     Response: {r.text[:200]}")
            
            # Check for tokens in response
            if "token" in r.text.lower() or "jwt" in r.text.lower():
                print(f"     ⚠️  Response contains tokens!")
        elif r.status_code not in [404, 401]:
            print(f"  ⚠️  {endpoint} -> {r.status_code}")
    except:
        pass

# Test 2: Active Users / Online Users
print("\n[TEST 2] Active Users Endpoints")
print("-"*80)

user_endpoints = [
    "/api/users",
    "/api/users/online",
    "/api/users/active",
    "/api/auth/users",
    "/api/admin/users",
    "/users"
]

for endpoint in user_endpoints:
    try:
        r = requests.get(f"{API_URL}{endpoint}", headers=headers, timeout=3)
        
        if r.status_code == 200:
            print(f"  🚨 ACCESSIBLE: {endpoint}")
            
            try:
                data = r.json()
                if isinstance(data, list):
                    print(f"     Users count: {len(data)}")
                    if len(data) > 0:
                        # Check first user
                        user = data[0]
                        print(f"     Sample user keys: {list(user.keys())}")
                        
                        # Check for sensitive data
                        if "password" in user or "token" in user:
                            print(f"     🚨 CONTAINS PASSWORD/TOKEN!")
                else:
                    print(f"     Response: {str(data)[:150]}")
            except:
                print(f"     Response: {r.text[:150]}")
    except:
        pass

# Test 3: Auth Logs / Login History
print("\n[TEST 3] Authentication Logs")
print("-"*80)

log_endpoints = [
    "/api/logs",
    "/api/auth/logs",
    "/api/login-history",
    "/api/auth/history",
    "/api/audit",
    "/api/audit/logs",
    "/logs"
]

for endpoint in log_endpoints:
    try:
        r = requests.get(f"{API_URL}{endpoint}", headers=headers, timeout=3)
        
        if r.status_code == 200:
            print(f"  🚨 LOGS ACCESSIBLE: {endpoint}")
            print(f"     Response: {r.text[:200]}")
            
            # Check for IP addresses, tokens
            if "ip" in r.text.lower() or "token" in r.text.lower():
                print(f"     ⚠️  Contains IP/token information!")
    except:
        pass

# Test 4: Redis/Cache Access
print("\n[TEST 4] Cache/Redis Access")
print("-"*80)

cache_endpoints = [
    "/api/cache",
    "/api/redis",
    "/redis",
    "/cache",
    "/api/session-store"
]

for endpoint in cache_endpoints:
    try:
        r = requests.get(f"{API_URL}{endpoint}", headers=headers, timeout=3)
        
        if r.status_code == 200:
            print(f"  🚨 CACHE ACCESSIBLE: {endpoint}")
            print(f"     Response: {r.text[:200]}")
    except:
        pass

# Test 5: JWT Secret Disclosure
print("\n[TEST 5] JWT Secret / Config Disclosure")
print("-"*80)

config_files = [
    "/.env",
    "/config.json",
    "/config/default.json",
    "/api/config",
    "/api/env",
    "/.git/config",
    "/package.json"
]

for file_path in config_files:
    try:
        r = requests.get(f"{API_URL}{file_path}", timeout=3)
        
        if r.status_code == 200:
            print(f"  🚨 CONFIG EXPOSED: {file_path}")
            
            if "jwt" in r.text.lower() or "secret" in r.text.lower():
                print(f"     🚨🚨 CONTAINS JWT SECRET!")
                print(f"     {r.text[:300]}")
            else:
                print(f"     {r.text[:150]}")
    except:
        pass

# Test 6: Token Refresh (Get New Token)
print("\n[TEST 6] Token Refresh Endpoint")
print("-"*80)

refresh_endpoints = [
    "/api/auth/refresh",
    "/api/token/refresh",
    "/auth/refresh"
]

for endpoint in refresh_endpoints:
    try:
        r = requests.post(f"{API_URL}{endpoint}", headers=headers, timeout=3)
        
        if r.status_code == 200:
            print(f"  🔑 REFRESH WORKS: {endpoint}")
            
            try:
                data = r.json()
                if "token" in data:
                    print(f"     New token: {data['token'][:50]}...")
            except:
                pass
        elif r.status_code not in [404, 401]:
            print(f"  ⚠️  {endpoint} -> {r.status_code}: {r.text[:100]}")
    except:
        pass

# Test 7: Session Hijacking via ID
print("\n[TEST 7] Session ID Enumeration")
print("-"*80)

for session_id in ["1", "abc123", "00000000-0000-0000-0000-000000000001"]:
    try:
        r = requests.get(f"{API_URL}/api/sessions/{session_id}", headers=headers, timeout=3)
        
        if r.status_code == 200:
            print(f"  🚨 SESSION ACCESSIBLE: {session_id}")
            print(f"     {r.text[:200]}")
    except:
        pass

# Test 8: Leak via Debug/Error
print("\n[TEST 8] Token Leak via Debug Mode")
print("-"*80)

debug_params = [
    {"debug": "true"},
    {"verbose": "true"},
    {"include_tokens": "true"}
]

for params in debug_params:
    try:
        r = requests.get(f"{API_URL}/api/users/me", params=params, headers=headers, timeout=3)
        
        if "token" in r.text and r.status_code == 200:
            print(f"  🚨 TOKEN LEAK: {params}")
            print(f"     {r.text[:200]}")
    except:
        pass

# Summary
print("\n" + "="*80)
print("SESSION STORAGE TEST SUMMARY")
print("="*80)
print("\nCheck for 🚨 markers above!")
print("\nIf no 🚨 found:")
print("  ✅ Session storage protected")
print("  ✅ Token access controlled")
print("  ✅ No config leaks")
print("="*80)
