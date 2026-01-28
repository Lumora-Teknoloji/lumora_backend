# Security Test Suite - Quick Start

## 🚀 Usage

### 1. Start the server:
```bash
python security_ui_server.py
```

### 2. Open your browser:
```
http://localhost:5555
```

### 3. Use the interface:
- Enter target URL (default: http://localhost:5000)
- Select tests from the scrollable list
- Click "Run Selected Tests"
- View results in real-time

## 📋 Available Tests

1. **Basic Security Test** - SQL injection, XSS, auth bypass
2. **Advanced Security Test** - Comprehensive security checks
3. **XSS Attack Test** - Cross-site scripting vulnerabilities
4. **JWT Hijacking Test** - Token security
5. **Rate Limiting Test** - DoS protection
6. **IDOR Test** - Insecure direct object references
7. **SYN Flood Test** - Network-level DoS (⚠️ aggressive)
8. **Ultimate DoS Test** - Stress testing (⚠️ very aggressive)
9. **Cookie Attack Test** - Session security
10. **Server Health Check** - Basic connectivity
11. **API Connection Test** - Endpoint verification
12. **Quick XSS Test** - Fast XSS scan

## ⚠️ Warning

Some tests (DoS tests) are aggressive and may impact system performance.
Use only on systems you own or have permission to test.

## 🎨 Features

- Modern gradient UI
- Scrollable test list
- Real-time results
- Select all/individual tests
- Severity indicators
- Clean result display

## 📝 Notes

- Tests run sequentially with 60s timeout
- Results show stdout/stderr from each test
- Failed tests display error messages
- All results are logged to console
