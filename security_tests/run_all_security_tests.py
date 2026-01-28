"""
HIZLI GÜVENLİK TESTİ ÇALIŞTIRICI
Tüm testleri çalıştırır ve sonuçları JSON'a kaydeder
"""
import subprocess
import json
import time
from datetime import datetime
from pathlib import Path

# Test dosyaları
TESTS = [
    'security_test.py',
    'advanced_security_test.py',
    'xss_test_logger.py',
    'jwt_hijacking_test.py',
    'rate_limiting_test.py',
    'idor_real_test.py',
    'advanced_cookie_attacks.py',
    'server_health_check.py',
    'api_connection_test.py',
    'quick_xss_test.py'
]

def run_test(test_file):
    """Tek bir testi çalıştırır"""
    print(f"\n{'='*60}")
    print(f"▶️  {test_file}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            ['python', test_file],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        duration = time.time() - start_time
        
        return {
            'name': test_file.replace('.py', ''),
            'file': test_file,
            'status': 'passed' if result.returncode == 0 else 'failed',
            'passed': result.returncode == 0,
            'duration': round(duration * 1000),
            'output': result.stdout[-500:] if result.stdout else '',
            'error': result.stderr[-500:] if result.stderr else '',
            'return_code': result.returncode
        }
        
    except subprocess.TimeoutExpired:
        return {
            'name': test_file.replace('.py', ''),
            'file': test_file,
            'status': 'failed',
            'passed': False,
            'duration': 30000,
            'error': 'Test timeout (30s)',
            'return_code': -1
        }
    except Exception as e:
        return {
            'name': test_file.replace('.py', ''),
            'file': test_file,
            'status': 'failed',
            'passed': False,
            'duration': 0,
            'error': str(e),
            'return_code': -1
        }

def main():
    print("\n" + "="*60)
    print("🛡️  GÜVENLİK TESTLERİ BAŞLADI")
    print("="*60)
    print(f"Test Sayısı: {len(TESTS)}")
    print(f"Başlangıç: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    results = []
    passed = 0
    failed = 0
    
    for test_file in TESTS:
        if not Path(test_file).exists():
            print(f"⚠️  {test_file} bulunamadı, atlanıyor...")
            continue
            
        result = run_test(test_file)
        results.append(result)
        
        if result['passed']:
            passed += 1
            print(f"✅ BAŞARILI - {result['duration']}ms")
        else:
            failed += 1
            print(f"❌ BAŞARISIZ - {result.get('error', 'Unknown error')[:100]}")
    
    # Sonuçları kaydet
    output_data = {
        'timestamp': datetime.now().isoformat(),
        'total': len(results),
        'passed': passed,
        'failed': failed,
        'success_rate': round((passed / len(results) * 100) if results else 0, 1),
        'results': results
    }
    
    output_file = 'latest_test_results.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*60)
    print("📊 ÖZET")
    print("="*60)
    print(f"✅ Başarılı: {passed}")
    print(f"❌ Başarısız: {failed}")
    print(f"📈 Başarı Oranı: {output_data['success_rate']}%")
    print(f"💾 Sonuçlar: {output_file}")
    print("="*60)
    print("\n🌐 Sonuçları görmek için:")
    print("   security_results_auto.html dosyasını tarayıcıda açın")
    print("="*60 + "\n")

if __name__ == '__main__':
    main()
