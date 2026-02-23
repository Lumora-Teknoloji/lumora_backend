# -*- coding: utf-8 -*-
"""
GYM API Quick Security Test
https://gym-api.algorynth.net/
"""
import requests
import json
import time

API_URL = "https://gym-api.algorynth.net"

results = {
    "test_name": "Gym API Security Test",
    "target": API_URL,
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "tests": []
}

print("="*60)
print("GYM API SECURITY TEST")
print("="*60)
print(f"Target: {API_URL}\n")

# Test 1: Health/Root Check
print("[TEST 1] API Accessibility")
try:
    r = requests.get(API_URL, timeout=10)
    results["tests"].append({
        "name": "API Root Access",
        "status": "passed" if r.status_code == 200 else "failed",
        "status_code": r.status_code,
        "response_time": r.elapsed.total_seconds(),
        "details": f"Status: {r.status_code}"
    })
    print(f"[OK] Status: {r.status_code} - {r.elapsed.total_seconds():.2f}s")
except Exception as e:
    results["tests"].append({
        "name": "API Root Access",
        "status": "failed",
        "error": str(e)
    })
    print(f"[ERROR] {e}")

# Test 2: Common Endpoints
endpoints = [
    "/api",
    "/health",
    "/api/health",
    "/users",
    "/api/users",
    "/auth/login",
    "/api/auth/login"
]

print(f"\n[TEST 2] Endpoint Discovery")
for endpoint in endpoints:
    try:
        url = API_URL + endpoint
        r = requests.get(url, timeout=5)
        status = "passed" if r.status_code in [200, 401, 403] else "info"
        results["tests"].append({
            "name": f"Endpoint: {endpoint}",
"status": status,
            "status_code": r.status_code,
            "details": f"{r.status_code}"
        })
        print(f"  {endpoint:30} -> {r.status_code}")
    except:
        pass

# Test 3: CORS Headers
print(f"\n[TEST 3] CORS Configuration")
try:
    r = requests.options(API_URL, headers={"Origin": "https://evil.com"}, timeout=5)
    cors_header = r.headers.get("Access-Control-Allow-Origin", "Not Set")
    
    if cors_header == "*":
        status = "vulnerable"
        msg = "CORS allows all origins (*)"
    elif cors_header == "Not Set":
        status = "passed"
        msg = "CORS not configured or restrictive"
    else:
        status = "info"
        msg = f"CORS: {cors_header}"
    
    results["tests"].append({
        "name": "CORS Configuration",
        "status": status,
        "details": msg,
        "cors_header": cors_header
    })
    print(f"  {msg}")
except Exception as e:
    print(f"  [ERROR] {e}")

# Test 4: Security Headers
print(f"\n[TEST 4] Security Headers")
try:
    r = requests.get(API_URL, timeout=5)
    headers_to_check = {
        "X-Frame-Options": "Protects against clickjacking",
        "X-Content-Type-Options": "Prevents MIME-type sniffing",
        "Strict-Transport-Security": "Enforces HTTPS",
        "Content-Security-Policy": "Prevents XSS",
        "X-XSS-Protection": "Legacy XSS protection"
    }
    
    for header, desc in headers_to_check.items():
        value = r.headers.get(header)
        if value:
            print(f"  [OK] {header}: {value}")
            results["tests"].append({
                "name": f"Security Header: {header}",
                "status": "passed",
                "value": value
            })
        else:
            print(f"  [MISSING] {header}")
            results["tests"].append({
                "name": f"Security Header: {header}",
                "status": "warning",
                "details": "Header missing"
            })
except Exception as e:
    print(f"  [ERROR] {e}")

# Save results
with open("gym_api_test_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

# Summary
total = len(results["tests"])
passed = len([t for t in results["tests"] if t["status"] == "passed"])
failed = len([t for t in results["tests"] if t["status"] == "failed"])
vulnerable = len([t for t in results["tests"] if t["status"] == "vulnerable"])

print("\n" + "="*60)
print("SUMMARY")
print("="*60)
print(f"Total Tests: {total}")
print(f"Passed: {passed}")
print(f"Failed: {failed}")
print(f"Vulnerabilities: {vulnerable}")
print(f"\nResults saved to: gym_api_test_results.json")
print("="*60)
