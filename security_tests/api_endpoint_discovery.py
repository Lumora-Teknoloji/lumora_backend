# -*- coding: utf-8 -*-
"""
API Endpoint Discovery Tool
Otomatik olarak API endpoint'lerini bulur
"""
import requests
import json
import sys
from urllib.parse import urljoin

# Windows encoding fix
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def discover_api(base_url):
    """API endpoint'lerini otomatik keşfeder"""
    
    print("="*80)
    print(f"API ENDPOINT DISCOVERY: {base_url}")
    print("="*80)
    
    results = {
        "base_url": base_url,
        "documentation": [],
        "endpoints": [],
        "auth_endpoints": []
    }
    
    # 1. API Dokümantasyonunu Bul
    print("\n[STEP 1] Searching for API Documentation...")
    print("-"*80)
    
    doc_paths = [
        "/docs",
        "/api/docs",
        "/swagger",
        "/api/swagger",
        "/openapi.json",
        "/api/openapi.json",
        "/api-docs",
        "/redoc",
        "/api/redoc",
        "/documentation",
        "/api/v1/docs",
        "/api/v2/docs"
    ]
    
    for path in doc_paths:
        try:
            url = urljoin(base_url, path)
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                print(f"[FOUND] {path} -> {r.status_code}")
                results["documentation"].append({
                    "path": path,
                    "url": url,
                    "content_type": r.headers.get('Content-Type', 'unknown')
                })
                
                # OpenAPI/Swagger JSON ise parse et
                if 'json' in r.headers.get('Content-Type', ''):
                    try:
                        api_spec = r.json()
                        if 'paths' in api_spec:
                            print(f"  [*] OpenAPI/Swagger spec found!")
                            print(f"  [*] Endpoints in spec: {len(api_spec.get('paths', {}))}")
                            return analyze_openapi_spec(api_spec, base_url)
                    except:
                        pass
        except:
            pass
    
    if not results["documentation"]:
        print("[INFO] No API documentation found, using brute force discovery...")
    
    # 2. Common Endpoint'leri Test Et
    print("\n[STEP 2] Testing Common Endpoints...")
    print("-"*80)
    
    common_endpoints = [
        # Health/Status
        "/health", "/api/health", "/status", "/api/status",
        "/ping", "/api/ping",
        
        # Authentication
        "/login", "/api/login", "/auth/login", "/api/auth/login",
        "/signin", "/api/signin", "/auth/signin",
        "/register", "/api/register", "/auth/register",
        "/signup", "/api/signup", "/auth/signup",
        "/logout", "/api/logout", "/auth/logout",
        "/token", "/api/token", "/auth/token",
        
        # User endpoints
        "/users", "/api/users", "/user", "/api/user",
        "/users/me", "/api/users/me", "/me", "/api/me",
        "/profile", "/api/profile",
        
        # Common resources
        "/items", "/api/items", "/products", "/api/products",
        "/data", "/api/data", "/list", "/api/list",
        
        # API versions
        "/v1", "/api/v1", "/v2", "/api/v2",
        "/api", "/api/v1/health"
    ]
    
    found_endpoints = []
    
    for endpoint in common_endpoints:
        try:
            url = urljoin(base_url, endpoint)
            
            # GET request
            r = requests.get(url, timeout=3)
            if r.status_code != 404:
                status_symbol = "[OK]" if r.status_code == 200 else "[AUTH]" if r.status_code == 401 else "[FORBIDDEN]" if r.status_code == 403 else "[INFO]"
                print(f"{status_symbol} GET  {endpoint:30} -> {r.status_code}")
                
                found_endpoints.append({
                    "method": "GET",
                    "path": endpoint,
                    "status": r.status_code,
                    "url": url
                })
                
                # Auth endpoint'ini kaydet
                if 'login' in endpoint or 'signin' in endpoint or 'auth' in endpoint:
                    results["auth_endpoints"].append({
                        "method": "GET",
                        "path": endpoint,
                        "status": r.status_code
                    })
                
                # POST da dene (özellikle auth için)
                if any(x in endpoint for x in ['login', 'register', 'signup', 'token', 'auth']):
                    try:
                        r_post = requests.post(url, json={}, timeout=3)
                        if r_post.status_code != 404:
                            print(f"{status_symbol} POST {endpoint:30} -> {r_post.status_code}")
                            found_endpoints.append({
                                "method": "POST",
                                "path": endpoint,
                                "status": r_post.status_code,
                                "url": url
                            })
                            
                            results["auth_endpoints"].append({
                                "method": "POST",
                                "path": endpoint,
                                "status": r_post.status_code,
                                "response_sample": r_post.text[:200] if r_post.text else None
                            })
                    except:
                        pass
        except:
            pass
    
    results["endpoints"] = found_endpoints
    
    # 3. Sonuçları Göster
    print("\n" + "="*80)
    print("DISCOVERY RESULTS")
    print("="*80)
    
    print(f"\n[*] Documentation URLs: {len(results['documentation'])}")
    for doc in results["documentation"]:
        print(f"    {doc['url']}")
    
    print(f"\n[*] Found Endpoints: {len(found_endpoints)}")
    
    # Auth endpoint'lerini öne çıkar
    if results["auth_endpoints"]:
        print(f"\n[*] Authentication Endpoints ({len(results['auth_endpoints'])}):")
        for auth in results["auth_endpoints"]:
            print(f"    {auth['method']:6} {auth['path']:30} -> {auth['status']}")
            if auth.get('response_sample'):
                print(f"           Response: {auth['response_sample']}")
    
    # JSON'a kaydet
    with open("api_discovery_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n[*] Full results saved to: api_discovery_results.json")
    
    # 4. Login Test Önerileri
    if results["auth_endpoints"]:
        print("\n" + "="*80)
        print("LOGIN TEST SUGGESTIONS")
        print("="*80)
        
        for auth in results["auth_endpoints"]:
            if auth['method'] == 'POST' and 'login' in auth['path']:
                print(f"\nTry this endpoint: {auth['path']}")
                print("Different payload formats to test:")
                print('  1. {"username": "user", "password": "pass"}')
                print('  2. {"email": "user@example.com", "password": "pass"}')
                print('  3. {"user": "user", "pass": "pass"}')
                print('  4. {"identifier": "user", "password": "pass"}')
    
    return results


def analyze_openapi_spec(spec, base_url):
    """OpenAPI/Swagger spec'i analiz eder"""
    print("\n[ANALYZING OPENAPI SPEC]")
    print("-"*80)
    
    paths = spec.get('paths', {})
    
    print(f"\nFound {len(paths)} endpoints in OpenAPI spec:\n")
    
    auth_endpoints = []
    
    for path, methods in paths.items():
        for method, details in methods.items():
            if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                summary = details.get('summary', details.get('description', 'No description'))
                print(f"{method.upper():6} {path:40} - {summary[:50]}")
                
                # Auth endpoint'lerini bul
                if any(keyword in path.lower() for keyword in ['login', 'auth', 'token', 'signin']):
                    auth_endpoints.append({
                        "method": method.upper(),
                        "path": path,
                        "summary": summary,
                        "parameters": details.get('parameters', []),
                        "requestBody": details.get('requestBody', {})
                    })
    
    if auth_endpoints:
        print("\n[AUTH ENDPOINTS DETAILS]")
        print("-"*80)
        for auth in auth_endpoints:
            print(f"\n{auth['method']} {auth['path']}")
            print(f"  Summary: {auth['summary']}")
            
            # Request body schema
            if 'requestBody' in auth and auth['requestBody']:
                content = auth['requestBody'].get('content', {})
                for content_type, schema_data in content.items():
                    schema = schema_data.get('schema', {})
                    if 'properties' in schema:
                        print(f"  Required fields:")
                        for prop, prop_details in schema['properties'].items():
                            prop_type = prop_details.get('type', 'unknown')
                            print(f"    - {prop} ({prop_type})")
    
    return {
        "base_url": base_url,
        "spec_version": spec.get('openapi', spec.get('swagger', 'unknown')),
        "total_endpoints": len(paths),
        "auth_endpoints": auth_endpoints,
        "paths": paths
    }


if __name__ == "__main__":
    # Target API
    API_URL = "https://gym-api.algorynth.net"
    
    print("\n")
    print("#"*80)
    print("#" + " "*78 + "#")
    print("#" + " "*20 + "API ENDPOINT DISCOVERY TOOL" + " "*31 + "#")
    print("#" + " "*78 + "#")
    print("#"*80)
    print("\n")
    
    results = discover_api(API_URL)
    
    print("\n" + "="*80)
    print("DISCOVERY COMPLETE!")
    print("="*80)
    print("\nNext steps:")
    print("1. Check api_discovery_results.json for full results")
    print("2. Try the suggested login endpoints with different payloads")
    print("3. Use found documentation URLs for more details")
    print("="*80 + "\n")
