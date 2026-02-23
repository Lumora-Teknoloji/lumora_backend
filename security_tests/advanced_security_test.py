"""
Kapsamlı Güvenlik Test Suite
Tüm major güvenlik zafiyetlerini test eder
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api"

print("🔒 KAPSAMLI GÜVENLİK TESTLERİ BAŞLIYOR")
print("=" * 60)

results = {
    "total_tests": 0,
    "vulnerabilities": [],
    "safe": [],
    "warnings": []
}

def log_result(category, test, status, details, severity="INFO"):
    """Test sonucunu kaydet"""
    results["total_tests"] += 1
    result = {
        "category": category,
        "test": test,
        "status": status,
        "details": details,
        "severity": severity
    }
    
    if status == "VULNERABLE":
        results["vulnerabilities"].append(result)
        print(f"🔴 {category} - {test}: VULNERABLE ({severity})")
    elif status == "SAFE":
        results["safe"].append(result)
        print(f"🟢 {category} - {test}: SAFE")
    elif status == "WARNING":
        results["warnings"].append(result)
        print(f"🟡 {category} - {test}: WARNING ({severity})")
    
    print(f"   └─ {details}")

# ============================================================================
# TEST 1: IDOR (Insecure Direct Object Reference)
# ============================================================================
print("\n[1/6] 🔍 IDOR Testleri...")
print("-" * 60)

# Önce bir kullanıcı oluştur ve login ol
try:
    # User 1 oluştur
    r1 = requests.post(f"{API_URL}/auth/register", json={
        "username": "idor_test_user1",
        "email": "idor1@test.com",
        "password": "Test1234!",
        "full_name": "IDOR Test 1"
    })
    
    # User 2 oluştur  
    r2 = requests.post(f"{API_URL}/auth/register", json={
        "username": "idor_test_user2",
        "email": "idor2@test.com",
        "password": "Test1234!",
        "full_name": "IDOR Test 2"
    })
    
    # User 1 login
    login1 = requests.post(f"{API_URL}/auth/login", json={
        "username": "idor_test_user1",
        "password": "Test1234!"
    })
    
    if login1.status_code == 200:
        token1 = login1.json()["access_token"]
        user1_id = login1.json()["user"]["id"]
        
        # User 2'nin ID'sini tahmin et (genelde sequential)
        user2_id = user1_id + 1
        
        # User 1'in token'ı ile User 2'nin conversation'larını almayı dene
        headers1 = {"Authorization": f"Bearer {token1}"}
        
        # Kendi conversation'larını al
        my_convs = requests.get(f"{API_URL}/conversations", headers=headers1)
        
        # Başka user'ın conversation'larına erişmeyi dene (tahmini ID ile)
        # Not: Bu endpoint var mı bilmiyoruz ama test ediyoruz
        try:
            other_conv = requests.get(f"{API_URL}/conversations?user_id={user2_id}", headers=headers1)
            
            if other_conv.status_code == 200:
                log_result(
                    "IDOR",
                    "Access other user's conversations",
                    "VULNERABLE",
                    f"User {user1_id} başka user'ın ({user2_id}) conversation'larına erişebildi!",
                    "CRITICAL"
                )
            else:
                log_result(
                    "IDOR",
                    "Access other user's conversations",
                    "SAFE",
                    "Başka user'ın verilerine erişim engellendi"
                )
        except:
            log_result(
                "IDOR",
                "Access other user's conversations",
                "SAFE",
                "Endpoint mevcut değil veya korunuyor"
            )
            
except Exception as e:
    log_result("IDOR", "General IDOR test", "WARNING", f"Test hatası: {str(e)}", "MEDIUM")

# ============================================================================
# TEST 2: CSRF (Cross-Site Request Forgery)
# ============================================================================
print("\n[2/6] 🎭 CSRF Testleri...")
print("-" * 60)

try:
    # CSRF token olmadan state-changing operation yapabilir miyiz?
    # Örnek: Şifre değiştirme
    
    # Önce login ol
    login = requests.post(f"{API_URL}/auth/login", json={
        "username": "idor_test_user1",
        "password": "Test1234!"
    })
    
    if login.status_code == 200:
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # CSRF token olmadan şifre değiştirmeyi dene
        # (Gerçek CSRF saldırısında bu farklı bir origin'den gelir)
        csrf_test = requests.post(
            f"{API_URL}/users/change-password",
            headers=headers,
            json={
                "current_password": "Test1234!",
                "new_password": "NewPass123!"
            }
        )
        
        if csrf_test.status_code == 200:
            log_result(
                "CSRF",
                "Change password without CSRF token",
                "VULNERABLE",
                "CSRF token kontrolü yok! State-changing işlemler korunmasız.",
                "HIGH"
            )
        elif "csrf" in csrf_test.text.lower() or "token" in csrf_test.text.lower():
            log_result(
                "CSRF",
                "Change password without CSRF token",
                "SAFE",
                "CSRF token gerekli"
            )
        else:
            log_result(
                "CSRF",
                "Change password without CSRF token",
                "WARNING",
                "CSRF koruması belirsiz, manuel kontrol gerekli",
                "MEDIUM"
            )
except Exception as e:
    log_result("CSRF", "General CSRF test", "WARNING", f"Test hatası: {str(e)}", "MEDIUM")

# ============================================================================
# TEST 3: Mass Assignment
# ============================================================================
print("\n[3/6] 📝 Mass Assignment Testleri...")
print("-" * 60)

try:
    # Kullanıcı kaydında is_admin=true göndermeyi dene
    mass_assign = requests.post(f"{API_URL}/auth/register", json={
        "username": "mass_assign_test",
        "email": "mass@test.com",
        "password": "Test1234!",
        "full_name": "Mass Test",
        "is_admin": True,  # Unauthorized field
        "role": "admin",    # Unauthorized field
        "is_superuser": True  # Unauthorized field
    })
    
    if mass_assign.status_code == 201:
        user_data = mass_assign.json()
        
        # Response'da admin alanları var mı kontrol et
        if user_data.get("is_admin") or user_data.get("role") == "admin":
            log_result(
                "Mass Assignment",
                "Set admin privileges via registration",
                "VULNERABLE",
                "Kullanıcı kendi kendine admin olabilir!",
                "CRITICAL"
            )
        else:
            log_result(
                "Mass Assignment",
                "Set admin privileges via registration",
                "SAFE",
                "Unauthorized field'lar ignore edildi"
            )
    elif mass_assign.status_code == 422:
        log_result(
            "Mass Assignment",
            "Set admin privileges via registration",
            "SAFE",
            "Extra field'lar validation'dan geçmedi"
        )
    elif mass_assign.status_code == 400:
        log_result(
            "Mass Assignment",
            "Set admin privileges via registration",
            "WARNING",
            "User zaten var, test tamamlanamadı",
            "LOW"
        )
        
except Exception as e:
    log_result("Mass Assignment", "General test", "WARNING", f"Test hatası: {str(e)}", "MEDIUM")

# ============================================================================
# TEST 4: API Fuzzing - Malformed Requests
# ============================================================================
print("\n[4/6] 💥 API Fuzzing...")
print("-" * 60)

# Malformed JSON
try:
    bad_json = requests.post(
        f"{API_URL}/auth/login",
        data="{'invalid json",  # Geçersiz JSON
        headers={"Content-Type": "application/json"}
    )
    
    if bad_json.status_code == 500:
        log_result(
            "API Fuzzing",
            "Malformed JSON handling",
            "VULNERABLE",
            "Server error! Malformed JSON crash ediyor.",
            "MEDIUM"
        )
    elif bad_json.status_code in [400, 422]:
        log_result(
            "API Fuzzing",
            "Malformed JSON handling",
            "SAFE",
            "Malformed JSON doğru şekilde handle ediliyor"
        )
except Exception as e:
    log_result("API Fuzzing", "Malformed JSON", "WARNING", f"Request hatası: {str(e)}", "LOW")

# Very large payload
try:
    huge_payload = {
        "username": "a" * 1000000,  # 1 MB username
        "password": "Test1234!",
        "email": "huge@test.com"
    }
    
    large_req = requests.post(f"{API_URL}/auth/register", json=huge_payload, timeout=5)
    
    if large_req.status_code == 201:
        log_result(
            "API Fuzzing",
            "Large payload handling",
            "VULNERABLE",
            "Çok büyük payload kabul edildi! DoS riski.",
            "HIGH"
        )
    elif large_req.status_code in [400, 413, 422]:
        log_result(
            "API Fuzzing",
            "Large payload handling",
            "SAFE",
            "Büyük payload reddedildi"
        )
except requests.Timeout:
    log_result(
        "API Fuzzing",
        "Large payload handling",
        "VULNERABLE",
        "Server timeout! DoS riski var.",
        "HIGH"
    )
except Exception as e:
    log_result("API Fuzzing", "Large payload", "WARNING", f"Test hatası: {str(e)}", "LOW")

# ============================================================================
# TEST 5: Authentication Bypass
# ============================================================================
print("\n[5/6] 🔐 Authentication Bypass Testleri...")
print("-" * 60)

# Empty token
try:
    empty_token = requests.get(
        f"{API_URL}/users/me",
        headers={"Authorization": "Bearer "}
    )
    
    if empty_token.status_code == 200:
        log_result(
            "Auth Bypass",
            "Empty token",
            "VULNERABLE",
            "Boş token ile erişim başarılı!",
            "CRITICAL"
        )
    else:
        log_result(
            "Auth Bypass",
            "Empty token",
            "SAFE",
            "Boş token reddedildi"
        )
except Exception as e:
    log_result("Auth Bypass", "Empty token", "WARNING", f"Test hatası: {str(e)}", "LOW")

# SQL Injection in token
try:
    sql_token = requests.get(
        f"{API_URL}/users/me",
        headers={"Authorization": "Bearer ' OR '1'='1"}
    )
    
    if sql_token.status_code == 200:
        log_result(
            "Auth Bypass",
            "SQL injection in token",
            "VULNERABLE",
            "SQL injection başarılı!",
            "CRITICAL"
        )
    else:
        log_result(
            "Auth Bypass",
            "SQL injection in token",
            "SAFE",
            "SQL injection engellendi"
        )
except Exception as e:
    log_result("Auth Bypass", "SQL injection", "WARNING", f"Test hatası: {str(e)}", "LOW")

# ============================================================================
# TEST 6: Sensitive Data Exposure
# ============================================================================
print("\n[6/6] 🔍 Sensitive Data Exposure...")
print("-" * 60)

try:
    # API dokümantasyonu production'da açık mı?
    docs = requests.get(f"{BASE_URL}/docs")
    
    if docs.status_code == 200:
        log_result(
            "Data Exposure",
            "API docs in production",
            "VULNERABLE",
            "API dokümantasyonu herkese açık! /docs kapatılmalı.",
            "MEDIUM"
        )
    else:
        log_result(
            "Data Exposure",
            "API docs in production",
            "SAFE",
            "API dokümantasyonu korunuyor"
        )
        
    # Error messages stack trace içeriyor mu?
    error_test = requests.get(f"{API_URL}/nonexistent-endpoint-12345")
    
    if "traceback" in error_test.text.lower() or "exception" in error_test.text.lower():
        log_result(
            "Data Exposure",
            "Stack trace in errors",
            "VULNERABLE",
            "Error mesajları stack trace içeriyor!",
            "MEDIUM"
        )
    else:
        log_result(
            "Data Exposure",
            "Stack trace in errors",
            "SAFE",
            "Error mesajları temiz"
        )
        
except Exception as e:
    log_result("Data Exposure", "General test", "WARNING", f"Test hatası: {str(e)}", "LOW")

# ============================================================================
# SONUÇLAR
# ============================================================================
print("\n" + "=" * 60)
print("📊 TEST SONUÇLARI")
print("=" * 60)

print(f"\n✅ Toplam Test: {results['total_tests']}")
print(f"🔴 Zafiyet: {len(results['vulnerabilities'])}")
print(f"🟢 Güvenli: {len(results['safe'])}")
print(f"🟡 Uyarı: {len(results['warnings'])}")

if results['vulnerabilities']:
    print(f"\n⚠️  KRİTİK ZAFİYETLER:")
    for vuln in results['vulnerabilities']:
        print(f"  • [{vuln['severity']}] {vuln['category']}: {vuln['test']}")
        print(f"    └─ {vuln['details']}")

# JSON rapor kaydet
with open('advanced_security_test_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n📄 Detaylı rapor: advanced_security_test_results.json")
print("✅ Testler tamamlandı!")
