"""
Server Health Check - Saldırı Olmadan Baseline Test
"""

import socket
import time
from colorama import init, Fore, Style

init()

def test_server_health(host="localhost", port=8000, attempts=10):
    """Server'a normal bağlantı testi"""
    
    print(f"{Fore.CYAN}{'═' * 70}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}SERVER HEALTH CHECK - BASELINE (NO ATTACK){Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'═' * 70}{Style.RESET_ALL}\n")
    
    print(f"Target: {host}:{port}")
    print(f"Attempts: {attempts}\n")
    
    results = []
    
    for i in range(1, attempts + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            start = time.time()
            sock.connect((host, port))
            elapsed = (time.time() - start) * 1000
            sock.close()
            
            results.append({"attempt": i, "status": "SUCCESS", "time_ms": elapsed})
            
            if elapsed < 10:
                print(f"[{i:2d}] {Fore.GREEN}✅ Connected ({elapsed:.2f}ms) - Excellent{Style.RESET_ALL}")
            elif elapsed < 100:
                print(f"[{i:2d}] {Fore.GREEN}✅ Connected ({elapsed:.2f}ms) - Good{Style.RESET_ALL}")
            elif elapsed < 1000:
                print(f"[{i:2d}] {Fore.YELLOW}⚠️  Connected ({elapsed:.2f}ms) - Slow{Style.RESET_ALL}")
            else:
                print(f"[{i:2d}] {Fore.RED}⚠️  Connected ({elapsed:.2f}ms) - Very Slow!{Style.RESET_ALL}")
            
            time.sleep(0.1)
            
        except socket.timeout:
            results.append({"attempt": i, "status": "TIMEOUT", "time_ms": 5000})
            print(f"[{i:2d}] {Fore.RED}❌ TIMEOUT{Style.RESET_ALL}")
        except Exception as e:
            results.append({"attempt": i, "status": "ERROR", "time_ms": 0})
            print(f"[{i:2d}] {Fore.RED}❌ ERROR: {e}{Style.RESET_ALL}")
    
    # Statistics
    print(f"\n{Fore.YELLOW}{'─' * 70}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}STATISTICS{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'─' * 70}{Style.RESET_ALL}\n")
    
    successful = [r for r in results if r["status"] == "SUCCESS"]
    failed = len(results) - len(successful)
    
    if successful:
        times = [r["time_ms"] for r in successful]
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        
        print(f"Successful: {Fore.GREEN}{len(successful)}/{len(results)}{Style.RESET_ALL}")
        print(f"Failed: {Fore.RED}{failed}/{len(results)}{Style.RESET_ALL}")
        print(f"Success Rate: {Fore.GREEN}{(len(successful)/len(results))*100:.1f}%{Style.RESET_ALL}\n")
        
        print(f"Response Time:")
        print(f"  Min: {Fore.GREEN}{min_time:.2f}ms{Style.RESET_ALL}")
        print(f"  Max: {Fore.YELLOW}{max_time:.2f}ms{Style.RESET_ALL}")
        print(f"  Avg: {Fore.CYAN}{avg_time:.2f}ms{Style.RESET_ALL}\n")
        
        # Verdict
        print(f"{Fore.GREEN}{'═' * 70}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}VERDICT{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'═' * 70}{Style.RESET_ALL}\n")
        
        if len(successful) == len(results) and avg_time < 100:
            print(f"{Fore.GREEN}✅ SERVER HEALTHY{Style.RESET_ALL}")
            print(f"   All connections successful")
            print(f"   Average response time: {avg_time:.2f}ms")
            print(f"   Server is operating normally\n")
        elif len(successful) >= len(results) * 0.9:
            print(f"{Fore.YELLOW}⚠️  SERVER SLOW{Style.RESET_ALL}")
            print(f"   Some connections delayed")
            print(f"   Average response time: {avg_time:.2f}ms\n")
        else:
            print(f"{Fore.RED}🔴 SERVER ISSUES{Style.RESET_ALL}")
            print(f"   Multiple connection failures")
            print(f"   Server may be under load\n")
    else:
        print(f"{Fore.RED}🔴 SERVER DOWN!{Style.RESET_ALL}")
        print(f"   All connection attempts failed\n")
    
    return results

if __name__ == "__main__":
    print(f"""
{Fore.CYAN}
╔═══════════════════════════════════════════════════════╗
║     SERVER BASELINE HEALTH CHECK                     ║
║     Test server WITHOUT attack                       ║
╚═══════════════════════════════════════════════════════╝
{Style.RESET_ALL}
""")
    
    test_server_health("localhost", 8000, attempts=10)
    
    print(f"{Fore.CYAN}✅ Baseline test complete!{Style.RESET_ALL}\n")
