"""
New Backend Security Test Suite
Yeni authentication, Socket.IO ve exception handling testleri
"""

import requests
import json
import time
from datetime import datetime
from colorama import init, Fore, Style
import sys
from config import BASE_URL, API_URL, FRONTEND_URL

init()

class NewBackendSecurityTester:
    def __init__(self):
        self.base_url = BASE_URL
        self.api_url = API_URL
        self.results = []
        self.vulnerabilities = []
        
    def log_result(self, category, test_name, status, details, severity="INFO"):
        """Test sonucunu kaydet"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "test_name": test_name,
            "status": status,
            "details": details,
            "severity": severity
        }
        self.results.append(result)
        
        # Renk seç
        if status == "VULNERABLE":
            color = Fore.RED
            self.vulnerabilities.append(result)
        elif status == "SAFE":
            color = Fore.GREEN
        elif status == "WARNING":
            color = Fore.YELLOW
        else:
            color = Fore.CYAN
            
        print(f"{color}[{severity}] {category} - {test_name}: {status}{Style.RESET_ALL}")
        if details:
            print(f"  {details}")
    
    def test_auth_response_structure(self):
        """Test 1.1: Authentication Response Structure Analysis"""
        print(f"\n{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}TEST 1: AUTHENTICATION RESPONSE STRUCTURE{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")
        
        try:
            # Test user oluştur
            username = f"auth_test_{int(time.time())}"
            
            # Register
            reg_resp = requests.post(f"{self.api_url}/auth/register", json={
                "username": username,
                "email": f"{username}@test.com",
                "password": "Test123!",
                "full_name": "Auth Test"
            }, timeout=5)
            
            # Login
            login_resp = requests.post(f"{self.api_url}/auth/login", json={
                "username": username,
                "password": "Test123!"
            }, timeout=5)
            
            if login_resp.status_code != 200:
                self.log_result(
                    "Authentication",
                    "Login Response",
                    "ERROR",
                    f"Login failed: {login_resp.status_code}",
                    "HIGH"
                )
                return
            
            # Response analizi
            print(f"{Fore.YELLOW}Response Analysis:{Style.RESET_ALL}")
            print(f"  Status Code: {login_resp.status_code}")
            print(f"  Headers: {dict(login_resp.headers)}")
            print(f"  Cookies: {login_resp.cookies.get_dict()}")
            
            # Cookie kontrolü
            if 'Set-Cookie' in login_resp.headers:
                cookie_header = login_resp.headers['Set-Cookie']
                print(f"\n{Fore.YELLOW}Cookie Analysis:{Style.RESET_ALL}")
                print(f"  {cookie_header}")
                
                # HttpOnly flag
                if 'HttpOnly' in cookie_header:
                    self.log_result(
                        "Cookie Security",
                        "HttpOnly Flag",
                        "SAFE",
                        "HttpOnly flag present - JavaScript cannot access cookie",
                        "INFO"
                    )
                else:
                    self.log_result(
                        "Cookie Security",
                        "HttpOnly Flag",
                        "VULNERABLE",
                        "HttpOnly flag missing - XSS can steal cookie!",
                        "HIGH"
                    )
                
                # Secure flag
                if 'Secure' in cookie_header:
                    self.log_result(
                        "Cookie Security",
                        "Secure Flag",
                        "SAFE",
                        "Secure flag present - HTTPS only",
                        "INFO"
                    )
                else:
                    self.log_result(
                        "Cookie Security",
                        "Secure Flag",
                        "WARNING",
                        "Secure flag missing - HTTP allowed (MITM risk)",
                        "MEDIUM"
                    )
                
                # SameSite flag
                if 'SameSite' in cookie_header:
                    self.log_result(
                        "Cookie Security",
                        "SameSite Flag",
                        "SAFE",
                        "SameSite present - CSRF protection active",
                        "INFO"
                    )
                else:
                    self.log_result(
                        "Cookie Security",
                        "SameSite Flag",
                        "VULNERABLE",
                        "SameSite missing - CSRF attacks possible!",
                        "HIGH"
                    )
            
            # Body kontrolü
            try:
                body = login_resp.json()
                print(f"\n{Fore.YELLOW}Response Body:{Style.RESET_ALL}")
                print(f"  {json.dumps(body, indent=2)}")
                
                if 'access_token' in body:
                    self.log_result(
                        "Token Storage",
                        "Token in Response Body",
                        "WARNING",
                        "Token in response body - should use HttpOnly cookie",
                        "MEDIUM"
                    )
                else:
                    self.log_result(
                        "Token Storage",
                        "Token in Response Body",
                        "SAFE",
                        "No token in body - using cookies (good practice)",
                        "INFO"
                    )
            except:
                print("  (Empty or non-JSON body)")
                
        except Exception as e:
            self.log_result(
                "Authentication",
                "Response Structure Test",
                "ERROR",
                str(e),
                "HIGH"
            )
    
    def test_cookie_replay_attack(self):
        """Test 1.2: Cookie Replay Attack"""
        print(f"\n{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}TEST 2: COOKIE REPLAY ATTACK{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")
        
        try:
            # Test user oluştur
            username = f"replay_test_{int(time.time())}"
            
            requests.post(f"{self.api_url}/auth/register", json={
                "username": username,
                "email": f"{username}@test.com",
                "password": "Test123!",
                "full_name": "Replay Test"
            }, timeout=5)
            
            # Login ve cookie al
            login_resp = requests.post(f"{self.api_url}/auth/login", json={
                "username": username,
                "password": "Test123!"
            }, timeout=5)
            
            if login_resp.status_code != 200:
                self.log_result(
                    "Cookie Replay",
                    "Login Failed",
                    "ERROR",
                    f"Cannot test replay - login failed: {login_resp.status_code}",
                    "HIGH"
                )
                return
            
            # Cookie'yi çal
            stolen_cookies = login_resp.cookies
            
            print(f"{Fore.RED}🔴 Simulating cookie theft...{Style.RESET_ALL}")
            print(f"  Stolen cookies: {stolen_cookies.get_dict()}")
            
            # Cookie'yi 5 kez kullanmayı dene
            success_count = 0
            for i in range(5):
                response = requests.get(
                    f"{self.api_url}/users/me",
                    cookies=stolen_cookies,
                    timeout=5
                )
                
                if response.status_code == 200:
                    success_count += 1
                    print(f"  [{i+1}] {Fore.YELLOW}✅ Cookie still valid{Style.RESET_ALL}")
                else:
                    print(f"  [{i+1}] {Fore.GREEN}❌ Cookie rejected{Style.RESET_ALL}")
                    break
                
                time.sleep(0.5)
            
            if success_count == 5:
                self.log_result(
                    "Cookie Replay",
                    "Token Reusability",
                    "VULNERABLE",
                    "Cookie can be replayed indefinitely - no token rotation",
                    "MEDIUM"
                )
            elif success_count == 0:
                self.log_result(
                    "Cookie Replay",
                    "Token Reusability",
                    "SAFE",
                    "Cookie rejected immediately - strong protection",
                    "INFO"
                )
            else:
                self.log_result(
                    "Cookie Replay",
                    "Token Reusability",
                    "WARNING",
                    f"Cookie valid for {success_count} attempts - partial protection",
                    "MEDIUM"
                )
                
        except Exception as e:
            self.log_result(
                "Cookie Replay",
                "Replay Attack Test",
                "ERROR",
                str(e),
                "HIGH"
            )
    
    def test_session_fixation(self):
        """Test 1.3: Session Fixation Attack"""
        print(f"\n{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}TEST 3: SESSION FIXATION ATTACK{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")
        
        try:
            # Saldırgan session oluştur
            attacker_session = requests.Session()
            attacker_session.get(f"{self.base_url}/health", timeout=5)
            
            attacker_cookies_before = attacker_session.cookies.get_dict().copy()
            print(f"{Fore.RED}🔴 Attacker's initial cookies:{Style.RESET_ALL}")
            print(f"  {attacker_cookies_before}")
            
            # Kurban bu cookie ile login yapar (simüle)
            username = f"fixation_test_{int(time.time())}"
            
            requests.post(f"{self.api_url}/auth/register", json={
                "username": username,
                "email": f"{username}@test.com",
                "password": "Test123!",
                "full_name": "Fixation Test"
            }, timeout=5)
            
            # Kurban saldırganın cookie'si ile login
            victim_login = attacker_session.post(f"{self.api_url}/auth/login", json={
                "username": username,
                "password": "Test123!"
            }, timeout=5)
            
            attacker_cookies_after = attacker_session.cookies.get_dict()
            
            # Session ID değişti mi?
            if attacker_cookies_before == attacker_cookies_after:
                self.log_result(
                    "Session Fixation",
                    "Session Regeneration",
                    "VULNERABLE",
                    "Session ID not regenerated on login - fixation possible!",
                    "HIGH"
                )
            else:
                self.log_result(
                    "Session Fixation",
                    "Session Regeneration",
                    "SAFE",
                    "Session ID regenerated on login - fixation prevented",
                    "INFO"
                )
            
            # Saldırgan erişmeyi dene
            access_resp = attacker_session.get(f"{self.api_url}/users/me", timeout=5)
            
            if access_resp.status_code == 200:
                user_data = access_resp.json()
                if user_data.get('username') == username:
                    self.log_result(
                        "Session Fixation",
                        "Unauthorized Access",
                        "VULNERABLE",
                        "Attacker accessed victim account via session fixation!",
                        "CRITICAL"
                    )
                else:
                    self.log_result(
                        "Session Fixation",
                        "Unauthorized Access",
                        "SAFE",
                        "Access granted but to different user",
                        "INFO"
                    )
            else:
                self.log_result(
                    "Session Fixation",
                    "Unauthorized Access",
                    "SAFE",
                    "Attacker cannot access victim account",
                    "INFO"
                )
                
        except Exception as e:
            self.log_result(
                "Session Fixation",
                "Fixation Attack Test",
                "ERROR",
                str(e),
                "HIGH"
            )
    
    def test_trace_method(self):
        """Test 2.1: TRACE Method Cookie Extraction"""
        print(f"\n{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}TEST 4: TRACE METHOD EXPLOIT{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")
        
        try:
            # Login session oluştur
            session = requests.Session()
            username = f"trace_test_{int(time.time())}"
            
            requests.post(f"{self.api_url}/auth/register", json={
                "username": username,
                "email": f"{username}@test.com",
                "password": "Test123!",
                "full_name": "TRACE Test"
            }, timeout=5)
            
            session.post(f"{self.api_url}/auth/login", json={
                "username": username,
                "password": "Test123!"
            }, timeout=5)
            
            # TRACE request gönder
            try:
                trace_resp = session.request('TRACE', f"{self.api_url}/users/me", timeout=5)
                
                print(f"{Fore.YELLOW}TRACE Response:{Style.RESET_ALL}")
                print(f"  Status: {trace_resp.status_code}")
                print(f"  Body: {trace_resp.text[:200]}")
                
                # Cookie exposed mi?
                if 'Cookie:' in trace_resp.text or 'cookie' in trace_resp.text.lower():
                    self.log_result(
                        "HTTP Methods",
                        "TRACE Method",
                        "VULNERABLE",
                        "TRACE method exposes cookies - HttpOnly bypass!",
                        "CRITICAL"
                    )
                else:
                    self.log_result(
                        "HTTP Methods",
                        "TRACE Method",
                        "SAFE",
                        "TRACE method disabled or filtered",
                        "INFO"
                    )
            except requests.exceptions.ConnectionError:
                self.log_result(
                    "HTTP Methods",
                    "TRACE Method",
                    "SAFE",
                    "TRACE method not allowed - connection refused",
                    "INFO"
                )
                
        except Exception as e:
            self.log_result(
                "HTTP Methods",
                "TRACE Method Test",
                "ERROR",
                str(e),
                "MEDIUM"
            )
    
    def test_exception_disclosure(self):
        """Test 4.1: Stack Trace Information Disclosure"""
        print(f"\n{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}TEST 5: EXCEPTION HANDLER INFORMATION DISCLOSURE{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")
        
        payloads = [
            ("Null username", {"username": None, "password": "test"}),
            ("Long username", {"username": "a" * 10000, "password": "test"}),
            ("Dict username", {"username": {"$ne": ""}, "password": "test"}),
            ("SQL injection", {"username": "'; DROP TABLE users--", "password": "test"}),
            ("Array password", {"username": "test", "password": []}),
        ]
        
        vulnerabilities_found = []
        
        for test_name, payload in payloads:
            try:
                response = requests.post(
                    f"{self.api_url}/auth/login",
                    json=payload,
                    timeout=5
                )
                
                response_text = response.text.lower()
                
                # Stack trace kontrolü
                dangerous_keywords = [
                    'traceback', 'file "', 'line ', 'exception',
                    'error at', 'stack trace', 'raise ', 'def ',
                    'app/', 'backend/', '.py"'
                ]
                
                found_keywords = [kw for kw in dangerous_keywords if kw in response_text]
                
                if found_keywords:
                    vulnerabilities_found.append({
                        'test': test_name,
                        'keywords': found_keywords,
                        'response': response.text[:300]
                    })
                    print(f"  {Fore.RED}❌ {test_name}: Information leaked!{Style.RESET_ALL}")
                    print(f"     Keywords found: {', '.join(found_keywords)}")
                else:
                    print(f"  {Fore.GREEN}✅ {test_name}: Generic error{Style.RESET_ALL}")
                    
            except Exception as e:
                print(f"  {Fore.YELLOW}⚠️  {test_name}: {str(e)}{Style.RESET_ALL}")
        
        if vulnerabilities_found:
            self.log_result(
                "Exception Handling",
                "Stack Trace Disclosure",
                "VULNERABLE",
                f"Stack traces exposed in {len(vulnerabilities_found)} tests",
                "MEDIUM"
            )
        else:
            self.log_result(
                "Exception Handling",
                "Stack Trace Disclosure",
                "SAFE",
                "Generic error messages - no information leakage",
                "INFO"
            )
    
    def run_all_tests(self):
        """Tüm testleri çalıştır"""
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}🔒 NEW BACKEND SECURITY TEST SUITE{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Target: {self.base_url}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}\n")
        
        # Testleri çalıştır
        self.test_auth_response_structure()
        self.test_cookie_replay_attack()
        self.test_session_fixation()
        self.test_trace_method()
        self.test_exception_disclosure()
        
        # Özet rapor
        print(f"\n{Fore.GREEN}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}TEST SUMMARY{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'='*70}{Style.RESET_ALL}\n")
        
        total_tests = len(self.results)
        vulnerabilities = [r for r in self.results if r['status'] == 'VULNERABLE']
        safe_tests = [r for r in self.results if r['status'] == 'SAFE']
        warnings = [r for r in self.results if r['status'] == 'WARNING']
        
        print(f"📊 Total Tests: {total_tests}")
        print(f"✅ Safe: {len(safe_tests)}")
        print(f"⚠️  Warnings: {len(warnings)}")
        print(f"❌ Vulnerabilities: {len(vulnerabilities)}")
        
        if vulnerabilities:
            print(f"\n{Fore.RED}VULNERABILITIES FOUND:{Style.RESET_ALL}")
            for vuln in vulnerabilities:
                print(f"  🔴 [{vuln['severity']}] {vuln['category']} - {vuln['test_name']}")
                print(f"     {vuln['details']}")
        
        # JSON rapor kaydet
        report = {
            "test_date": datetime.now().isoformat(),
            "target": self.base_url,
            "summary": {
                "total_tests": total_tests,
                "safe": len(safe_tests),
                "warnings": len(warnings),
                "vulnerabilities": len(vulnerabilities)
            },
            "results": self.results
        }
        
        with open('new_backend_security_results.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Detailed report saved: new_backend_security_results.json")

if __name__ == "__main__":
    tester = NewBackendSecurityTester()
    tester.run_all_tests()
    
    print(f"\n{Fore.GREEN}✅ All tests completed!{Style.RESET_ALL}\n")
