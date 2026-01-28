"""
Security Test Suite Backend Server
Runs security tests via web interface
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import subprocess
import json
import os
from pathlib import Path

app = Flask(__name__)
CORS(app)

# Test directory
TEST_DIR = Path(__file__).parent

# Available tests
AVAILABLE_TESTS = {
    'security_test.py': 'Basic Security Test',
    'advanced_security_test.py': 'Advanced Security Test',
    'xss_test_logger.py': 'XSS Attack Test',
    'jwt_hijacking_test.py': 'JWT Hijacking Test',
    'rate_limiting_test.py': 'Rate Limiting Test',
    'idor_real_test.py': 'IDOR Vulnerability Test',
    'syn_flood_test.py': 'SYN Flood DoS Test',
    'ultimate_dos_test.py': 'Ultimate DoS Test',
    'advanced_cookie_attacks.py': 'Cookie Attack Test',
    'server_health_check.py': 'Server Health Check',
    'api_connection_test.py': 'API Connection Test',
    'quick_xss_test.py': 'Quick XSS Test'
}

@app.route('/')
def index():
    return send_from_directory('.', 'security_ui.html')

@app.route('/run-security-tests', methods=['POST'])
def run_security_tests():
    data = request.json
    target_url = data.get('target_url')
    selected_tests = data.get('tests', [])
    
    if not target_url:
        return jsonify({'error': 'Target URL is required'}), 400
    
    if not selected_tests:
        return jsonify({'error': 'At least one test must be selected'}), 400
    
    results = []
    
    for test_file in selected_tests:
        if test_file not in AVAILABLE_TESTS:
            results.append({
                'test_name': test_file,
                'success': False,
                'message': 'Unknown test'
            })
            continue
        
        test_path = TEST_DIR / test_file
        
        if not test_path.exists():
            results.append({
                'test_name': AVAILABLE_TESTS[test_file],
                'success': False,
                'message': f'Test file not found: {test_file}'
            })
            continue
        
        try:
            # Run the test
            print(f"\n{'='*60}")
            print(f"Running: {AVAILABLE_TESTS[test_file]}")
            print(f"File: {test_file}")
            print(f"Target: {target_url}")
            print(f"{'='*60}\n")
            
            # Set environment variable for target URL
            env = os.environ.copy()
            env['TARGET_URL'] = target_url
            
            # Run test with timeout
            process = subprocess.run(
                ['python', test_file],
                cwd=str(TEST_DIR),
                capture_output=True,
                text=True,
                timeout=60,
                env=env
            )
            
            # Parse output
            output = process.stdout
            error = process.stderr
            
            success = process.returncode == 0
            
            results.append({
                'test_name': AVAILABLE_TESTS[test_file],
                'success': success,
                'message': 'Test completed' if success else 'Test failed',
                'details': {
                    'stdout': output[-500:] if len(output) > 500 else output,  # Last 500 chars
                    'stderr': error[-500:] if len(error) > 500 else error,
                    'return_code': process.returncode
                }
            })
            
        except subprocess.TimeoutExpired:
            results.append({
                'test_name': AVAILABLE_TESTS[test_file],
                'success': False,
                'message': 'Test timed out (60s limit)'
            })
        except Exception as e:
            results.append({
                'test_name': AVAILABLE_TESTS[test_file],
                'success': False,
                'message': f'Error running test: {str(e)}'
            })
    
    return jsonify({
        'target_url': target_url,
        'results': results,
        'total_tests': len(results),
        'passed': sum(1 for r in results if r['success']),
        'failed': sum(1 for r in results if not r['success'])
    })

@app.route('/list-tests', methods=['GET'])
def list_tests():
    return jsonify({
        'available_tests': [
            {
                'file': file,
                'name': name,
                'exists': (TEST_DIR / file).exists()
            }
            for file, name in AVAILABLE_TESTS.items()
        ]
    })

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🛡️  SECURITY TEST SUITE SERVER")
    print("="*60)
    print(f"\n📂 Test Directory: {TEST_DIR}")
    print(f"🌐 Opening web interface at: http://localhost:5555\n")
    print("Press Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5555, debug=True)
