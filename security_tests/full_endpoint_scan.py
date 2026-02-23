# -*- coding: utf-8 -*-
"""
Comprehensive API Endpoint Scanner
https://gym-api.algorynth.net/
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
print("COMPREHENSIVE ENDPOINT DISCOVERY")
print("="*80)
print(f"Target: {API_URL}\n")

results = []

# Kapsamlı endpoint listesi
endpoints = [
    # Health & Info
    "/api/health", "/health", "/api/status", "/status",
    "/api/info", "/info", "/api/version",
    
    # Auth
    "/api/auth/login", "/api/auth/register", "/api/auth/logout",
    "/api/auth/refresh", "/api/auth/verify", "/api/auth/reset",
    "/auth/login", "/login", "/register", "/signup",
    
    # User
    "/api/users", "/api/users/me", "/api/user", "/api/me",
    "/api/profile", "/api/account", "/api/user/profile",
    "/users", "/me", "/profile",
    
    # Gym Specific
    "/api/workouts", "/api/exercises", "/api/trainings",
    "/api/programs", "/api/sessions", "/api/routines",
    "/api/goals", "/api/achievements", "/api/progress",
    "/api/nutrition", "/api/diet", "/api/meals",
    "/api/body-measurements", "/api/stats", "/api/analytics",
    
    # Admin
    "/api/admin", "/api/admin/users", "/api/admin/stats",
    "/admin", "/dashboard",
    
    # Debug
    "/api/debug", "/api/test", "/debug", "/console",
    
    # Docs
    "/docs", "/api/docs", "/swagger", "/openapi.json",
    "/api-docs", "/documentation",
]

# Test without auth
print("[PHASE 1] Testing without authentication")
print("-"*80)
for endpoint in endpoints:
    try:
        url = API_URL + endpoint
        r = requests.get(url, timeout=3)
        
        if r.status_code != 404:
            status_emoji = "✅" if r.status_code == 200 else "🔒" if r.status_code in [401, 403] else "⚠️"
            print(f"{status_emoji} {endpoint:40} -> {r.status_code}")
            
            results.append({
                "endpoint": endpoint,
                "method": "GET",
                "auth": False,
                "status": r.status_code,
                "response_sample": r.text[:100] if r.text else None
            })
    except:
        pass

# Test with auth
print(f"\n[PHASE 2] Testing WITH authentication")
print("-"*80)
headers = {"Authorization": f"Bearer {TOKEN}"}

for endpoint in endpoints:
    try:
        url = API_URL + endpoint
        r = requests.get(url, headers=headers, timeout=3)
        
        if r.status_code != 404:
            status_emoji = "✅" if r.status_code == 200 else "⚠️"
            print(f"{status_emoji} {endpoint:40} -> {r.status_code} (with token)")
            
            results.append({
                "endpoint": endpoint,
                "method": "GET",
                "auth": True,
                "status": r.status_code,
                "response_sample": r.text[:100] if r.text else None
            })
    except:
        pass

# Test POST endpoints
print(f"\n[PHASE 3] Testing POST methods")
print("-"*80)

post_endpoints = [
    "/api/auth/login", "/api/auth/register",
    "/api/workouts", "/api/exercises", "/api/sessions"
]

for endpoint in post_endpoints:
    try:
        url = API_URL + endpoint
        r = requests.post(url, json={}, headers=headers, timeout=3)
        
        if r.status_code != 404:
            print(f"POST {endpoint:40} -> {r.status_code}")
            
            results.append({
                "endpoint": endpoint,
                "method": "POST",
                "auth": True,
                "status": r.status_code
            })
    except:
        pass

# Save results
with open("gym_api_full_scan.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

# Summary
print("\n" + "="*80)
print("SCAN COMPLETE")
print("="*80)

accessible = [r for r in results if r['status'] == 200]
protected = [r for r in results if r['status'] in [401, 403]]
other = [r for r in results if r['status'] not in [200, 401, 403, 404]]

print(f"\nTotal endpoints found: {len(results)}")
print(f"  ✅ Accessible (200): {len(accessible)}")
print(f"  🔒 Protected (401/403): {len(protected)}")
print(f"  ⚠️  Other: {len(other)}")

print(f"\n✅ Accessible endpoints:")
for r in accessible:
    print(f"  {r['method']:6} {r['endpoint']}")

print(f"\n🔒 Protected endpoints (need auth):")
for r in protected:
    print(f"  {r['method']:6} {r['endpoint']}")

print(f"\nResults saved to: gym_api_full_scan.json")
print("="*80)
