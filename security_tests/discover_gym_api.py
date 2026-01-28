# -*- coding: utf-8 -*-
"""
Gym API Endpoint Discovery
https://gym-api.algorynth.net/
"""
import requests
import json

API_URL = "https://gym-api.algorynth.net"

print("="*60)
print("GYM API ENDPOINT DISCOVERY")
print("="*60)

# Test farklı login formatları
login_variants = [
    {"endpoint": "/api/auth/login", "data": {"username": "asdasd1", "password": "asdasd1"}},
    {"endpoint": "/api/auth/login", "data": {"email": "asdasd1", "password": "asdasd1"}},
    {"endpoint": "/auth/login", "data": {"username": "asdasd1", "password": "asdasd1"}},
    {"endpoint": "/login", "data": {"username": "asdasd1", "password": "asdasd1"}},
    {"endpoint": "/api/login", "data": {"user": "asdasd1", "pass": "asdasd1"}},
]

print("\n[TEST] Login Endpoint Discovery")
for variant in login_variants:
    url = API_URL + variant["endpoint"]
    try:
        r = requests.post(url, json=variant["data"], timeout=5)
        print(f"\nEndpoint: {variant['endpoint']}")
        print(f"  Data: {variant['data']}")
        print(f"  Status: {r.status_code}")
        if r.status_code != 404:
            try:
                print(f"  Response: {r.json()}")
            except:
                print(f"  Response: {r.text[:200]}")
    except Exception as e:
        print(f"  Error: {e}")

# Common endpoints
print("\n" + "="*60)
print("[TEST] Common Endpoints")
print("="*60)

endpoints = [
    "/api/docs",
    "/api/openapi.json",
    "/docs",
    "/swagger",
    "/api/v1",
    "/api/health",
    "/health",
    "/api/users",
    "/users"
]

for endpoint in endpoints:
    try:
        r = requests.get(API_URL + endpoint, timeout=3)
        if r.status_code != 404:
            print(f"{endpoint:30} -> {r.status_code}")
    except:
        pass

print("\n" + "="*60)
