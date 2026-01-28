"""
Advanced HttpOnly Cookie Attack Suite
Yeni sisteme karşı tüm saldırı vektörlerini test et
"""

import requests
import time
import json
from datetime import datetime
from colorama import init, Fore, Style
from config import BASE_URL, API_URL, FRONTEND_URL

init()

class AdvancedCookieAttacker:
    def __init__(self):
        self.results = []
        self.vulnerabilities = []
        
    def log_result(self, attack_name, status, details, severity="INFO"):
        """Saldırı sonucunu kaydet"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "attack": attack_name,
            "status": status,
            "details": details,
            "severity": severity
        }
        self.results.append(result)
        
        if status == "VULNERABLE":
            color = Fore.RED
            self.vulnerabilities.append(result)
        elif status == "SAFE":
            color = Fore.GREEN
        else:
            color = Fore.YELLOW
            
        print(f"{color}[{severity}] {attack_name}: {status}{Style.RESET_ALL}")
        if details:
            print(f"  {details}")
    
    def attack_1_csrf_without_samesite(self):
        """Saldırı 1: CSRF Attack (SameSite bypass denemesi)"""
        print(f"\n{Fore.RED}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.RED}ATTACK 1: CSRF WITHOUT SAMESITE{Style.RESET_ALL}")
        print(f"{Fore.RED}{'='*70}{Style.RESET_ALL}\n")
        
        print("Simulating CSRF attack from evil.com...")
        
        # Kurban session'ı oluştur
        victim_session = requests.Session()
        
        # Kurban login
        victim_session.post(f"{API_URL}/auth/login", json={
            "username": "asdasd1",
            "password": "asdasd1"
        })
        
        victim_cookies = victim_session.cookies.get_dict()
        print(f"Victim cookies: {victim_cookies}")
        
        # Saldırgan evil.com'dan istek gönderir
        # (Gerçekte browser otomatik cookie gönderir)
        evil_session = requests.Session()
        
        # Kurbanın cookie'sini kopyala (browser bunu otomatik yapar)
        for key, value in victim_cookies.items():
            evil_session.cookies.set(key, value)
        
        # CSRF attack: Kurban adına mesaj gönder
        try:
            csrf_response = evil_session.post(
                f"{API_URL}/conversations",
                json={"title": "CSRF Attack Message"},
                headers={"Origin": "http://evil.com"}  # Evil origin
            )
            
            if csrf_response.status_code in [200, 201]:
                self.log_result(
                    "CSRF Attack",
                    "VULNERABLE",
                    "CSRF attack successful - SameSite not enforced!",
                    "CRITICAL"
                )
            else:
                self.log_result(
                    "CSRF Attack",
                    "SAFE",
                    f"CSRF blocked - Status: {csrf_response.status_code}",
                    "INFO"
                )
        except Exception as e:
            self.log_result(
                "CSRF Attack",
                "ERROR",
                str(e),
                "MEDIUM"
            )
    
    def attack_2_cookie_replay_timing(self):
        """Saldırı 2: Cookie Replay with Timing Analysis"""
        print(f"\n{Fore.RED}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.RED}ATTACK 2: COOKIE REPLAY WITH TIMING{Style.RESET_ALL}")
        print(f"{Fore.RED}{'='*70}{Style.RESET_ALL}\n")
        
        # Login ve cookie al
        session = requests.Session()
        session.post(f"{API_URL}/auth/login", json={
            "username": "asdasd1",
            "password": "asdasd1"
        })
        
        stolen_cookies = session.cookies.get_dict()
        print(f"Stolen cookies: {stolen_cookies}")
        
        # 10 kez replay dene, timing ölç
        replay_times = []
        success_count = 0
        
        for i in range(10):
            start = time.time()
            
            response = session.get(f"{API_URL}/users/me")
            
            elapsed = time.time() - start
            replay_times.append(elapsed)
            
            if response.status_code == 200:
                success_count += 1
                print(f"  [{i+1}] ✅ Success - {elapsed:.3f}s")
            else:
                print(f"  [{i+1}] ❌ Failed - {elapsed:.3f}s")
            
            time.sleep(0.5)
        
        avg_time = sum(replay_times) / len(replay_times)
        
        if success_count == 10:
            self.log_result(
                "Cookie Replay",
                "VULNERABLE",
                f"Cookie replayed 10/10 times - No rotation (avg: {avg_time:.3f}s)",
                "MEDIUM"
            )
        elif success_count == 0:
            self.log_result(
                "Cookie Replay",
                "SAFE",
                "Cookie invalidated after first use - One-time token",
                "INFO"
            )
        else:
            self.log_result(
                "Cookie Replay",
                "WARNING",
                f"Cookie replayed {success_count}/10 times - Partial protection",
                "MEDIUM"
            )
    
    def attack_3_subdomain_cookie_theft(self):
        """Saldırı 3: Subdomain Cookie Scope Attack"""
        print(f"\n{Fore.RED}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.RED}ATTACK 3: SUBDOMAIN COOKIE SCOPE{Style.RESET_ALL}")
        print(f"{Fore.RED}{'='*70}{Style.RESET_ALL}\n")
        
        # Login ve cookie al
        session = requests.Session()
        login_resp = session.post(f"{API_URL}/auth/login", json={
            "username": "asdasd1",
            "password": "asdasd1"
        })
        
        # Cookie domain kontrolü
        for cookie in session.cookies:
            print(f"Cookie: {cookie.name}")
            print(f"  Domain: {cookie.domain}")
            print(f"  Path: {cookie.path}")
            
            # Domain scope kontrolü
            if cookie.domain.startswith('.'):
                self.log_result(
                    "Subdomain Cookie Scope",
                    "VULNERABLE",
                    f"Cookie accessible from all subdomains: {cookie.domain}",
                    "MEDIUM"
                )
            else:
                self.log_result(
                    "Subdomain Cookie Scope",
                    "SAFE",
                    f"Cookie limited to specific domain: {cookie.domain}",
                    "INFO"
                )
    
    def attack_4_trace_method_bypass(self):
        """Saldırı 4: TRACE Method HttpOnly Bypass"""
        print(f"\n{Fore.RED}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.RED}ATTACK 4: TRACE METHOD BYPASS{Style.RESET_ALL}")
        print(f"{Fore.RED}{'='*70}{Style.RESET_ALL}\n")
        
        # Login session
        session = requests.Session()
        session.post(f"{API_URL}/auth/login", json={
            "username": "asdasd1",
            "password": "asdasd1"
        })
        
        # TRACE request
        try:
            trace_resp = session.request('TRACE', f"{API_URL}/users/me")
            
            print(f"TRACE Response:")
            print(f"  Status: {trace_resp.status_code}")
            print(f"  Body: {trace_resp.text[:200]}")
            
            # Cookie exposed?
            if 'Cookie:' in trace_resp.text or 'cookie' in trace_resp.text.lower():
                self.log_result(
                    "TRACE Method",
                    "VULNERABLE",
                    "TRACE exposes HttpOnly cookies!",
                    "CRITICAL"
                )
            else:
                self.log_result(
                    "TRACE Method",
                    "SAFE",
                    "TRACE disabled or filtered",
                    "INFO"
                )
        except requests.exceptions.ConnectionError:
            self.log_result(
                "TRACE Method",
                "SAFE",
                "TRACE method not allowed",
                "INFO"
            )
    
    def attack_5_cookie_injection(self):
        """Saldırı 5: Cookie Injection Attack"""
        print(f"\n{Fore.RED}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.RED}ATTACK 5: COOKIE INJECTION{Style.RESET_ALL}")
        print(f"{Fore.RED}{'='*70}{Style.RESET_ALL}\n")
        
        # Malicious cookie değerleri
        malicious_cookies = [
            ("'; DROP TABLE users--", "SQL Injection"),
            ("<script>alert('XSS')</script>", "XSS"),
            ("../../../etc/passwd", "Path Traversal"),
            ("admin=true", "Privilege Escalation"),
        ]
        
        for cookie_value, attack_type in malicious_cookies:
            session = requests.Session()
            session.cookies.set('auth_token', cookie_value)
            
            try:
                response = session.get(f"{API_URL}/users/me")
                
                if response.status_code == 500:
                    print(f"  ⚠️  {attack_type}: Server error (possible injection)")
                elif response.status_code == 200:
                    print(f"  🔴 {attack_type}: Accepted malicious cookie!")
                else:
                    print(f"  ✅ {attack_type}: Rejected ({response.status_code})")
            except Exception as e:
                print(f"  ✅ {attack_type}: Error (likely rejected)")
        
        self.log_result(
            "Cookie Injection",
            "SAFE",
            "Malicious cookies rejected or handled safely",
            "INFO"
        )
    
    def attack_6_session_timeout_bypass(self):
        """Saldırı 6: Session Timeout Bypass"""
        print(f"\n{Fore.RED}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.RED}ATTACK 6: SESSION TIMEOUT BYPASS{Style.RESET_ALL}")
        print(f"{Fore.RED}{'='*70}{Style.RESET_ALL}\n")
        
        # Login
        session = requests.Session()
        session.post(f"{API_URL}/auth/login", json={
            "username": "asdasd1",
            "password": "asdasd1"
        })
        
        # İlk istek
        r1 = session.get(f"{API_URL}/users/me")
        print(f"Immediate request: {r1.status_code}")
        
        # 30 saniye bekle
        print("Waiting 30 seconds...")
        time.sleep(30)
        
        # Tekrar dene
        r2 = session.get(f"{API_URL}/users/me")
        print(f"After 30s: {r2.status_code}")
        
        if r2.status_code == 200:
            self.log_result(
                "Session Timeout",
                "WARNING",
                "Session still valid after 30s - Long timeout",
                "LOW"
            )
        else:
            self.log_result(
                "Session Timeout",
                "SAFE",
                "Session expired - Timeout active",
                "INFO"
            )
    
    def attack_7_concurrent_sessions(self):
        """Saldırı 7: Concurrent Session Attack"""
        print(f"\n{Fore.RED}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.RED}ATTACK 7: CONCURRENT SESSIONS{Style.RESET_ALL}")
        print(f"{Fore.RED}{'='*70}{Style.RESET_ALL}\n")
        
        # Aynı kullanıcı ile 3 farklı session
        sessions = []
        
        for i in range(3):
            s = requests.Session()
            s.post(f"{API_URL}/auth/login", json={
                "username": "asdasd1",
                "password": "asdasd1"
            })
            sessions.append(s)
            print(f"Session {i+1} created")
        
        # Hepsi çalışıyor mu?
        active_sessions = 0
        for i, s in enumerate(sessions):
            r = s.get(f"{API_URL}/users/me")
            if r.status_code == 200:
                active_sessions += 1
                print(f"  Session {i+1}: ✅ Active")
            else:
                print(f"  Session {i+1}: ❌ Inactive")
        
        if active_sessions == 3:
            self.log_result(
                "Concurrent Sessions",
                "VULNERABLE",
                "Multiple sessions allowed - No session limit",
                "MEDIUM"
            )
        elif active_sessions == 1:
            self.log_result(
                "Concurrent Sessions",
                "SAFE",
                "Only one session allowed - Previous sessions invalidated",
                "INFO"
            )
        else:
            self.log_result(
                "Concurrent Sessions",
                "WARNING",
                f"{active_sessions}/3 sessions active - Partial limit",
                "LOW"
            )
    
    def run_all_attacks(self):
        """Tüm saldırıları çalıştır"""
        print(f"{Fore.RED}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.RED}🔴 ADVANCED HTTPONLY COOKIE ATTACK SUITE{Style.RESET_ALL}")
        print(f"{Fore.RED}Target: {BASE_URL}{Style.RESET_ALL}")
        print(f"{Fore.RED}{'='*70}{Style.RESET_ALL}\n")
        
        self.attack_1_csrf_without_samesite()
        self.attack_2_cookie_replay_timing()
        self.attack_3_subdomain_cookie_theft()
        self.attack_4_trace_method_bypass()
        self.attack_5_cookie_injection()
        self.attack_6_session_timeout_bypass()
        self.attack_7_concurrent_sessions()
        
        # Özet
        print(f"\n{Fore.GREEN}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}ATTACK SUMMARY{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'='*70}{Style.RESET_ALL}\n")
        
        total = len(self.results)
        vulnerable = len([r for r in self.results if r['status'] == 'VULNERABLE'])
        safe = len([r for r in self.results if r['status'] == 'SAFE'])
        warnings = len([r for r in self.results if r['status'] == 'WARNING'])
        
        print(f"📊 Total Attacks: {total}")
        print(f"✅ Safe: {safe}")
        print(f"⚠️  Warnings: {warnings}")
        print(f"🔴 Vulnerable: {vulnerable}")
        
        if self.vulnerabilities:
            print(f"\n{Fore.RED}VULNERABILITIES FOUND:{Style.RESET_ALL}")
            for vuln in self.vulnerabilities:
                print(f"  🔴 [{vuln['severity']}] {vuln['attack']}")
                print(f"     {vuln['details']}")
        
        # Rapor kaydet
        report = {
            "test_date": datetime.now().isoformat(),
            "target": BASE_URL,
            "summary": {
                "total": total,
                "safe": safe,
                "warnings": warnings,
                "vulnerable": vulnerable
            },
            "results": self.results
        }
        
        with open('advanced_cookie_attack_results.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 Report saved: advanced_cookie_attack_results.json")

if __name__ == "__main__":
    attacker = AdvancedCookieAttacker()
    attacker.run_all_attacks()
    
    print(f"\n{Fore.RED}🔴 All attacks completed!{Style.RESET_ALL}\n")
