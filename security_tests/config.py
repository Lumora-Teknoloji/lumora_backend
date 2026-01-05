
# Security Test Configuration
# Tüm security testleri için merkezi URL konfigürasyonu
# -*- coding: utf-8 -*-
"""
Security Test Configuration
"""

# ============================================================================
# TARGET API - GYM API
# ============================================================================
GYM_API = {
    "BASE_URL": "https://gym-api.algorynth.net",
    "API_URL": "https://gym-api.algorynth.net/api",
    "FRONTEND_URL": "https://gym-tracker.algorynth.net",  # Frontend app
    "AUTH_ENDPOINT": "/auth/login",
    "PROFILE_ENDPOINT": "/profile",
    "HEALTH_ENDPOINT": "/health",
    "LOGIN_FORMAT": "email",  # "email" veya "username"
    "TEST_EMAIL": "test_security@example.com",
    "TEST_PASSWORD": "TestPass123!"
}

# ============================================================================
# TARGET API - LOCALHOST (LEGACY)
# ============================================================================
LOCALHOST_API = {
    "BASE_URL": "http://localhost:5000",
    "API_URL": "http://localhost:5000/api",
    "AUTH_ENDPOINT": "/auth/login",
    "PROFILE_ENDPOINT": "/users/me",
    "HEALTH_ENDPOINT": "/health",
    "LOGIN_FORMAT": "username",
    "TEST_USERNAME": "asdasd1",
    "TEST_PASSWORD": "asdasd1"
}

# ============================================================================
# ACTIVE TARGET - Değiştir: "GYM" veya "LOCALHOST"
# ============================================================================
ACTIVE_TARGET = "GYM"

# Aktif konfigürasyonu ayarla
if ACTIVE_TARGET == "GYM":
    TARGET = GYM_API
else:
    TARGET = LOCALHOST_API

# Kolay erişim için
BASE_URL = TARGET["BASE_URL"]
API_URL = TARGET["API_URL"]
AUTH_ENDPOINT = TARGET["AUTH_ENDPOINT"]
PROFILE_ENDPOINT = TARGET["PROFILE_ENDPOINT"]
HEALTH_ENDPOINT = TARGET["HEALTH_ENDPOINT"]
