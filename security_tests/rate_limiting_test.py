"""
Rate Limiting Attack Test - Brute Force Simülasyonu
Backend'de rate limiting var mı test eder
"""

import requests
import time
from datetime import datetime
from colorama import init, Fore, Style
import sys
from config import API_URL

init()  # Colorama init

BASE_URL = API_URL  # Backward compatibility


def print_banner():
    banner = f"""
{Fore.RED}
╔═══════════════════════════════════════════════════════╗
║     🔴 RATE LIMITING ATTACK SIMULATION               ║
║     Brute Force - Password Cracking Test             ║
╠═══════════════════════════════════════════════════════╣
║  Target: {BASE_URL}/auth/login                ║
║  Test Type: Password Brute Force                     ║
║  Expected: Rate limiting should block us!            ║
╚═══════════════════════════════════════════════════════╝
{Style.RESET_ALL}
"""
    print(banner)

def test_rate_limiting():
    """Login endpoint'ini brute force ile test et"""
    
    print(f"{Fore.YELLOW}[INFO] Test başlatılıyor...{Style.RESET_ALL}\n")
    
    # Test parametreleri
    username = "test_user_for_brute_force"
    
    # 10,000 farklı şifre oluştur (gerçek brute force simülasyonu)
    print(f"{Fore.CYAN}[INFO] 10,000 password denemesi oluşturuluyor...{Style.RESET_ALL}")
    
    base_passwords = [
        "password", "123456", "qwerty", "admin", "letmein", "welcome",
        "monkey", "dragon", "master", "sunshine", "princess", "football",
        "shadow", "michael", "jennifer", "alex", "hello", "secret",
        "test", "user", "guest", "demo", "temp", "sample", "Login",
        "Access", "Auth", "Secure", "Safe", "Protected", "Private"
    ]
    
    passwords = []
    
    # Varyasyonlar oluştur
    for base in base_passwords:
        for i in range(320):  # 30 * 320 = 9,600
            passwords.append(f"{base}{i}")
            passwords.append(f"{base.upper()}{i}")
            passwords.append(f"{base.capitalize()}{i}!")
            passwords.append(f"{i}{base}")
            passwords.append(f"{base}_{i}")
            passwords.append(f"{base}-{i}")
            passwords.append(f"{base}.{i}")
            passwords.append(f"{base}@{i}")
            passwords.append(f"{base}#{i}")
            passwords.append(f"{base}${i}")
            
            if len(passwords) >= 10000:
                break
        if len(passwords) >= 10000:
            break
    
    # Eksik varsa tamamla
    while len(passwords) < 10000:
        passwords.append(f"bruteforce{len(passwords)}")
    
    passwords = passwords[:10000]  # Tam 10,000
    
    print(f"{Fore.GREEN}✅ {len(passwords)} farklı şifre hazırlandı{Style.RESET_ALL}\n")
    
    total_attempts = len(passwords)
    successful_attempts = 0
    blocked_attempts = 0
    rate_limit_detected = False
    
    print(f"{Fore.CYAN}[TEST] Toplam deneme sayısı: {total_attempts}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[TEST] Target kullanıcı: {username}{Style.RESET_ALL}\n")
    
    # Progress bar
    print(f"{Fore.YELLOW}Progress:{Style.RESET_ALL}")
    print("─" * 60)
    
    results = []
    
    for i, password in enumerate(passwords, 1):
        # Progress göster
        progress = int((i / total_attempts) * 150)
        bar = "█" * progress + "░" * (150 - progress)
        percent = (i / total_attempts) * 100
        
        sys.stdout.write(f"\r[{bar}] {percent:.1f}% ({i}/{total_attempts})")
        sys.stdout.flush()
        
        # Login denemesi
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{BASE_URL}/auth/login",
                json={
                    "username": username,
                    "password": password
                },
                timeout=5
            )
            
            elapsed_time = (time.time() - start_time) * 1000  # ms
            
            result = {
                "attempt": i,
                "password": password,
                "status_code": response.status_code,
                "time_ms": round(elapsed_time, 2),
                "blocked": False
            }
            
            # Rate limiting kontrolü
            if response.status_code == 429:  # Too Many Requests
                rate_limit_detected = True
                blocked_attempts += 1
                result["blocked"] = True
            elif response.status_code in [200, 201]:
                successful_attempts += 1
            else:
                successful_attempts += 1  # Backend cevap verdi
                
            results.append(result)
            
        except requests.Timeout:
            result = {
                "attempt": i,
                "password": password,
                "status_code": "TIMEOUT",
                "time_ms": 5000,
                "blocked": True
            }
            blocked_attempts += 1
            results.append(result)
            
        except Exception as e:
            result = {
                "attempt": i,
                "password": password,
                "status_code": "ERROR",
                "time_ms": 0,
                "blocked": False,
                "error": str(e)
            }
            results.append(result)
        
        # Hız sınırı test etmek için hızlı gönder (delay yok)
        # time.sleep(0.1)  # Gerçek saldırıda delay olmaz!
    
    print("\n\n")  # Progress bar'dan sonra
    
    # Sonuçları göster
    print(f"\n{Fore.GREEN}{'=' * 60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}TEST SONUÇLARI{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'=' * 60}{Style.RESET_ALL}\n")
    
    print(f"📊 Toplam Deneme: {total_attempts}")
    print(f"✅ Başarılı (Backend cevap verdi): {successful_attempts}")
    print(f"❌ Engellendi (Rate limit): {blocked_attempts}")
    print(f"📈 Başarı Oranı: {(successful_attempts/total_attempts)*100:.1f}%\n")
    
    # Rate limiting değerlendirmesi
    print(f"{Fore.YELLOW}{'─' * 60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}RATE LIMITING DEĞERLENDİRMESİ{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'─' * 60}{Style.RESET_ALL}\n")
    
    if rate_limit_detected:
        print(f"{Fore.GREEN}✅ SAFE: Rate limiting algılandı!{Style.RESET_ALL}")
        print(f"   {blocked_attempts}/{total_attempts} istek engellendi")
    else:
        print(f"{Fore.RED}❌ VULNERABLE: Rate limiting YOK!{Style.RESET_ALL}")
        print(f"   {successful_attempts}/{total_attempts} istek başarılı")
        print(f"   {Fore.RED}🚨 Saldırgan sınırsız deneme yapabilir!{Style.RESET_ALL}")
    
    # Detaylı sonuçlar
    print(f"\n{Fore.CYAN}DETAYLI SONUÇLAR (İlk 10 ve Son 10):{Style.RESET_ALL}\n")
    
    # İlk 10
    print(f"{Fore.YELLOW}İlk 10 Deneme:{Style.RESET_ALL}")
    for result in results[:10]:
        status_color = Fore.GREEN if result['status_code'] in [200, 201, 401] else Fore.RED
        blocked_text = " 🛡️ BLOCKED" if result.get('blocked') else ""
        print(f"  #{result['attempt']:2d} | Password: {result['password']:15s} | "
              f"Status: {status_color}{str(result['status_code']):>3s}{Style.RESET_ALL} | "
              f"Time: {result['time_ms']:6.2f}ms{blocked_text}")
    
    print(f"\n{Fore.YELLOW}Son 10 Deneme:{Style.RESET_ALL}")
    for result in results[-10:]:
        status_color = Fore.GREEN if result['status_code'] in [200, 201, 401] else Fore.RED
        blocked_text = " 🛡️ BLOCKED" if result.get('blocked') else ""
        print(f"  #{result['attempt']:2d} | Password: {result['password']:15s} | "
              f"Status: {status_color}{str(result['status_code']):>3s}{Style.RESET_ALL} | " 
              f"Time: {result['time_ms']:6.2f}ms{blocked_text}")
    
    # Ortalama response time
    avg_time = sum(r['time_ms'] for r in results if isinstance(r['time_ms'], (int, float))) / len(results)
    print(f"\n⏱️  Ortalama Response Time: {avg_time:.2f}ms")
    
    # Risk değerlendirmesi
    print(f"\n{Fore.RED}{'═' * 60}{Style.RESET_ALL}")
    print(f"{Fore.RED}RİSK DEĞERLENDİRMESİ{Style.RESET_ALL}")
    print(f"{Fore.RED}{'═' * 60}{Style.RESET_ALL}\n")
    
    if successful_attempts > total_attempts * 0.9:  # %90'dan fazla başarılı
        print(f"{Fore.RED}🔴 CRITICAL RISK - Rate Limiting YOK!{Style.RESET_ALL}")
        print(f"{Fore.RED}   Saldırgan sınırsız brute force yapabilir{Style.RESET_ALL}")
        print(f"{Fore.RED}   Tüm şifreleri deneyebilir{Style.RESET_ALL}")
        print(f"{Fore.RED}   Hesaplar ele geçirilebilir{Style.RESET_ALL}\n")
        
        print(f"{Fore.YELLOW}ÖNERİLEN DÜZELTME:{Style.RESET_ALL}")
        print(f"  1. slowapi kütüphanesi ekle")
        print(f"  2. Login endpoint'e rate limit ekle (5 deneme/dakika)")
        print(f"  3. IP bazlı blocking ekle")
        print(f"  4. CAPTCHA ekle (çok deneme sonrası)")
    else:
        print(f"{Fore.GREEN}✅ SAFE - Rate limiting çalışıyor!{Style.RESET_ALL}")
    
    # JSON rapor kaydet
    import json
    report = {
        "test_date": datetime.now().isoformat(),
        "total_attempts": total_attempts,
        "successful_attempts": successful_attempts,
        "blocked_attempts": blocked_attempts,
        "rate_limit_detected": rate_limit_detected,
        "vulnerability": "VULNERABLE" if not rate_limit_detected else "SAFE",
        "results": results
    }
    
    with open('rate_limiting_test_results.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detaylı rapor kaydedildi: rate_limiting_test_results.json")

if __name__ == "__main__":
    print_banner()
    
    print(f"{Fore.YELLOW}⚠️  UYARI: Bu bir güvenlik testidir!{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}   Sadece kendi sistemlerinizde kullanın!{Style.RESET_ALL}\n")
    
    input(f"{Fore.CYAN}Devam etmek için Enter'a basın...{Style.RESET_ALL}\n")
    
    test_rate_limiting()
    
    print(f"\n{Fore.GREEN}✅ Test tamamlandı!{Style.RESET_ALL}\n")
