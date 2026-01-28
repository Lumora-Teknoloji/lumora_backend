"""
Lumora AI Chatbot - Otomatik Güvenlik Test Suite
Profesyonel penetrasyon testleri için kapsamlı test senaryoları
"""

import requests
import json
import time
from typing import Dict, List, Any
from datetime import datetime
from config import BASE_URL, API_URL


class SecurityTester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.api_url = API_URL
        self.results = []
        self.vulnerabilities = []
        
    def log_test(self, category: str, test_name: str, status: str, details: str, severity: str = "INFO"):
        """Test sonuçlarını kaydet"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "test_name": test_name,
            "status": status,
            "details": details,
            "severity": severity
        }
        self.results.append(result)
        if status == "VULNERABLE":
            self.vulnerabilities.append(result)
        print(f"[{severity}] {category} - {test_name}: {status}")
        
    def test_sql_injection(self):
        """SQL Injection testleri"""
        print("\n=== SQL Injection Testleri ===")
        
        payloads = [
            "admin' OR '1'='1",
            "admin'--",
            "admin' OR 1=1--",
            "' OR '1'='1' /*",
            "admin'; DROP TABLE users--",
            "1' UNION SELECT NULL, NULL, NULL--"
        ]
        
        for payload in payloads:
            try:
                response = requests.post(
                    f"{self.api_url}/auth/login",
                    json={"username": payload, "password": "test"},
                    timeout=5
                )
                
                if response.status_code == 200:
                    self.log_test(
                        "SQL Injection",
                        f"Login with payload: {payload}",
                        "VULNERABLE",
                        f"SQL injection başarılı! Response: {response.status_code}",
                        "CRITICAL"
                    )
                else:
                    self.log_test(
                        "SQL Injection",
                        f"Login with payload: {payload}",
                        "SAFE",
                        f"Payload reddedildi: {response.status_code}",
                        "INFO"
                    )
            except Exception as e:
                self.log_test(
                    "SQL Injection",
                    f"Login with payload: {payload}",
                    "ERROR",
                    str(e),
                    "WARNING"
                )
    
    def test_broken_authentication(self):
        """Authentication güvenlik testleri"""
        print("\n=== Authentication Testleri ===")
        
        # Zayıf şifre testi
        weak_passwords = ["123", "12345", "pass", "a", ""]
        
        for pwd in weak_passwords:
            try:
                response = requests.post(
                    f"{self.api_url}/auth/register",
                    json={
                        "username": f"test_{pwd}",
                        "email": f"test_{pwd}@test.com",
                        "password": pwd
                    },
                    timeout=5
                )
                
                if response.status_code == 201:
                    self.log_test(
                        "Weak Password",
                        f"Register with password: '{pwd}'",
                        "VULNERABLE",
                        f"Zayıf şifre kabul edildi! Length: {len(pwd)}",
                        "HIGH"
                    )
                else:
                    self.log_test(
                        "Weak Password",
                        f"Register with password: '{pwd}'",
                        "SAFE",
                        f"Zayıf şifre reddedildi: {response.status_code}",
                        "INFO"
                    )
            except Exception as e:
                self.log_test(
                    "Weak Password",
                    f"Register with password: '{pwd}'",
                    "ERROR",
                    str(e),
                    "WARNING"
                )
        
        # JWT token manipülasyonu
        fake_tokens = [
            "Bearer fake.token.here",
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
            "Bearer null",
            "Bearer admin"
        ]
        
        for token in fake_tokens:
            try:
                response = requests.get(
                    f"{self.api_url}/users/me",
                    headers={"Authorization": token},
                    timeout=5
                )
                
                if response.status_code == 200:
                    self.log_test(
                        "JWT Security",
                        f"Access with fake token",
                        "VULNERABLE",
                        f"Fake token kabul edildi!",
                        "CRITICAL"
                    )
                else:
                    self.log_test(
                        "JWT Security",
                        f"Access with fake token",
                        "SAFE",
                        f"Fake token reddedildi: {response.status_code}",
                        "INFO"
                    )
            except Exception as e:
                self.log_test(
                    "JWT Security",
                    f"Access with fake token",
                    "ERROR",
                    str(e),
                    "WARNING"
                )
    
    def test_authorization(self):
        """Yetkilendirme testleri"""
        print("\n=== Authorization Testleri ===")
        
        # Auth olmadan protected endpoint'lere erişim
        protected_endpoints = [
            "/users/me",
            "/conversations",
            "/messages"
        ]
        
        for endpoint in protected_endpoints:
            try:
                response = requests.get(f"{self.api_url}{endpoint}", timeout=5)
                
                if response.status_code == 200:
                    self.log_test(
                        "Authorization",
                        f"Access {endpoint} without auth",
                        "VULNERABLE",
                        f"Protected endpoint auth olmadan erişilebilir!",
                        "CRITICAL"
                    )
                elif response.status_code == 401:
                    self.log_test(
                        "Authorization",
                        f"Access {endpoint} without auth",
                        "SAFE",
                        "Unauthorized doğru şekilde döndü",
                        "INFO"
                    )
                else:
                    self.log_test(
                        "Authorization",
                        f"Access {endpoint} without auth",
                        "WARNING",
                        f"Beklenmeyen response: {response.status_code}",
                        "MEDIUM"
                    )
            except Exception as e:
                self.log_test(
                    "Authorization",
                    f"Access {endpoint} without auth",
                    "ERROR",
                    str(e),
                    "WARNING"
                )
    
    def test_xss(self):
        """XSS (Cross-Site Scripting) testleri"""
        print("\n=== XSS Testleri ===")
        
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "'-alert('XSS')-'",
        ]
        
        for payload in xss_payloads:
            try:
                # Register ile XSS test et
                response = requests.post(
                    f"{self.api_url}/auth/register",
                    json={
                        "username": payload,
                        "email": f"xss@test.com",
                        "password": "password123"
                    },
                    timeout=5
                )
                
                # Response'da payload sanitize edilmiş mi kontrol et
                if response.status_code == 201 or response.status_code == 400:
                    response_text = response.text
                    if payload in response_text and "<script>" in payload:
                        self.log_test(
                            "XSS",
                            f"XSS payload in username: {payload[:30]}",
                            "VULNERABLE",
                            "XSS payload sanitize edilmeden döndürüldü!",
                            "HIGH"
                        )
                    else:
                        self.log_test(
                            "XSS",
                            f"XSS payload in username: {payload[:30]}",
                            "SAFE",
                            "XSS payload sanitize edildi veya reddedildi",
                            "INFO"
                        )
            except Exception as e:
                self.log_test(
                    "XSS",
                    f"XSS payload: {payload[:30]}",
                    "ERROR",
                    str(e),
                    "WARNING"
                )
    
    def test_information_disclosure(self):
        """Bilgi sızıntısı testleri"""
        print("\n=== Information Disclosure Testleri ===")
        
        # Error messages analizi
        try:
            response = requests.post(
                f"{self.api_url}/auth/login",
                json={"username": "nonexistent", "password": "wrong"},
                timeout=5
            )
            
            if "kullanıcı adı veya şifre" in response.text.lower():
                self.log_test(
                    "Information Disclosure",
                    "Login error message",
                    "SAFE",
                    "Generic error message kullanılıyor",
                    "INFO"
                )
            elif "kullanıcı bulunamadı" in response.text.lower():
                self.log_test(
                    "Information Disclosure",
                    "Login error message",
                    "VULNERABLE",
                    "Hata mesajı kullanıcı varlığını ifşa ediyor",
                    "MEDIUM"
                )
        except Exception as e:
            self.log_test(
                "Information Disclosure",
                "Login error message",
                "ERROR",
                str(e),
                "WARNING"
            )
        
        # Stack trace kontrolü
        try:
            response = requests.get(f"{self.base_url}/nonexistent", timeout=5)
            if "traceback" in response.text.lower() or "exception" in response.text.lower():
                self.log_test(
                    "Information Disclosure",
                    "Stack trace exposure",
                    "VULNERABLE",
                    "Stack trace production'da açık!",
                    "MEDIUM"
                )
            else:
                self.log_test(
                    "Information Disclosure",
                    "Stack trace exposure",
                    "SAFE",
                    "Stack trace gizleniyor",
                    "INFO"
                )
        except Exception as e:
            self.log_test(
                "Information Disclosure",
                "Stack trace exposure",
                "ERROR",
                str(e),
                "WARNING"
            )
    
    def test_rate_limiting(self):
        """Rate limiting testleri"""
        print("\n=== Rate Limiting Testleri ===")
        
        # Brute force simülasyonu
        try:
            successful_requests = 0
            for i in range(50):
                response = requests.post(
                    f"{self.api_url}/auth/login",
                    json={"username": "test", "password": f"pass{i}"},
                    timeout=2
                )
                if response.status_code != 429:  # 429 = Too Many Requests
                    successful_requests += 1
                time.sleep(0.1)
            
            if successful_requests >= 45:
                self.log_test(
                    "Rate Limiting",
                    "Brute force protection",
                    "VULNERABLE",
                    f"Rate limiting yok! {successful_requests}/50 request başarılı",
                    "HIGH"
                )
            else:
                self.log_test(
                    "Rate Limiting",
                    "Brute force protection",
                    "SAFE",
                    f"Rate limiting mevcut: {successful_requests}/50",
                    "INFO"
                )
        except Exception as e:
            self.log_test(
                "Rate Limiting",
                "Brute force protection",
                "ERROR",
                str(e),
                "WARNING"
            )
    
    def test_cors(self):
        """CORS yapılandırma testleri"""
        print("\n=== CORS Testleri ===")
        
        try:
            response = requests.get(
                f"{self.base_url}/health",
                headers={"Origin": "http://evil.com"},
                timeout=5
            )
            
            cors_header = response.headers.get("Access-Control-Allow-Origin", "")
            
            if cors_header == "*":
                self.log_test(
                    "CORS",
                    "Allow-Origin wildcard",
                    "VULNERABLE",
                    "CORS wildcard (*) kullanılıyor!",
                    "MEDIUM"
                )
            elif "evil.com" in cors_header:
                self.log_test(
                    "CORS",
                    "CORS with malicious origin",
                    "VULNERABLE",
                    "Kötü niyetli origin kabul edildi!",
                    "HIGH"
                )
            else:
                self.log_test(
                    "CORS",
                    "CORS configuration",
                    "SAFE",
                    f"CORS doğru şekilde yapılandırılmış: {cors_header}",
                    "INFO"
                )
        except Exception as e:
            self.log_test(
                "CORS",
                "CORS configuration",
                "ERROR",
                str(e),
                "WARNING"
            )
    
    def test_security_headers(self):
        """Security headers kontrolü"""
        print("\n=== Security Headers Testleri ===")
        
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            headers = response.headers
            
            required_headers = {
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": ["DENY", "SAMEORIGIN"],
                "Strict-Transport-Security": "max-age",
                "Content-Security-Policy": True
            }
            
            for header, expected in required_headers.items():
                value = headers.get(header, "")
                
                if not value:
                    self.log_test(
                        "Security Headers",
                        f"Missing header: {header}",
                        "VULNERABLE",
                        f"{header} header eksik!",
                        "MEDIUM"
                    )
                else:
                    if isinstance(expected, list):
                        if any(exp in value for exp in expected):
                            self.log_test(
                                "Security Headers",
                                f"Header present: {header}",
                                "SAFE",
                                f"{header}: {value}",
                                "INFO"
                            )
                    elif isinstance(expected, str):
                        if expected in value:
                            self.log_test(
                                "Security Headers",
                                f"Header present: {header}",
                                "SAFE",
                                f"{header}: {value}",
                                "INFO"
                            )
        except Exception as e:
            self.log_test(
                "Security Headers",
                "Header check",
                "ERROR",
                str(e),
                "WARNING"
            )
    
    def run_all_tests(self):
        """Tüm testleri çalıştır"""
        print("🔒 Lumora AI Chatbot - Otomatik Güvenlik Testi Başlatılıyor...")
        print(f"Target: {self.base_url}")
        print("=" * 60)
        
        self.test_sql_injection()
        self.test_broken_authentication()
        self.test_authorization()
        self.test_xss()
        self.test_information_disclosure()
        self.test_rate_limiting()
        self.test_cors()
        self.test_security_headers()
        
        print("\n" + "=" * 60)
        print("✅ Testler tamamlandı!")
        
    def generate_report(self) -> Dict[str, Any]:
        """Test raporunu oluştur"""
        total_tests = len(self.results)
        vulnerabilities = [r for r in self.results if r["status"] == "VULNERABLE"]
        safe_tests = [r for r in self.results if r["status"] == "SAFE"]
        
        severity_count = {
            "CRITICAL": len([v for v in vulnerabilities if v["severity"] == "CRITICAL"]),
            "HIGH": len([v for v in vulnerabilities if v["severity"] == "HIGH"]),
            "MEDIUM": len([v for v in vulnerabilities if v["severity"] == "MEDIUM"]),
            "LOW": len([v for v in vulnerabilities if v["severity"] == "LOW"])
        }
        
        return {
            "summary": {
                "total_tests": total_tests,
                "vulnerabilities_found": len(vulnerabilities),
                "safe_tests": len(safe_tests),
                "severity_breakdown": severity_count
            },
            "vulnerabilities": vulnerabilities,
            "all_results": self.results
        }

if __name__ == "__main__":
    tester = SecurityTester()
    tester.run_all_tests()
    
    # Rapor oluştur ve kaydet
    report = tester.generate_report()
    
    with open("security_test_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📊 Rapor Özeti:")
    print(f"   Toplam Test: {report['summary']['total_tests']}")
    print(f"   Güvenlik Açığı: {report['summary']['vulnerabilities_found']}")
    print(f"   Güvenli: {report['summary']['safe_tests']}")
    print(f"\n⚠️  Severity Dağılımı:")
    for severity, count in report['summary']['severity_breakdown'].items():
        if count > 0:
            print(f"   {severity}: {count}")
    
    print(f"\n📄 Detaylı rapor: security_test_results.json")
