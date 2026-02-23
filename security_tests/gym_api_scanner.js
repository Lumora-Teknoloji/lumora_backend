// ============================================================================
// GYM API COMPREHENSIVE ENDPOINT SCANNER
// Tarayıcı Console'dan çalıştır (F12 → Console)
// ============================================================================

const API_URL = "https://gym-api.algorynth.net";
const TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjo2LCJlbWFpbCI6InRlc3Rfc2VjdXJpdHlAZXhhbXBsZS5jb20iLCJpc3MiOiJneW0tdHJhY2tlci1hcGkiLCJleHAiOjE3Njc0Mzk0ODYsImlhdCI6MTc2NzM1MzA4Nn0.SJFr0yGvNspzbQktTDLB81Lb6DHsREXjcnUEbngUE1c";

// Kapsamlı endpoint listesi
const endpoints = [
    // Health & Info
    "/api/health", "/health", "/api/status", "/status",
    "/api/info", "/info", "/api/version",

    // Auth
    "/api/auth/login", "/api/auth/register", "/api/auth/logout",
    "/api/auth/refresh", "/api/auth/verify", "/api/auth/reset",
    "/auth/login", "/login", "/register", "/signup",

    // User
    "/api/users", "/api/users/me", "/api/user", "/api/me",
    "/api/profile", "/api/account", "/api/user/profile",
    "/users", "/me", "/profile",

    // Gym Specific
    "/api/workouts", "/api/exercises", "/api/trainings",
    "/api/programs", "/api/sessions", "/api/routines",
    "/api/goals", "/api/achievements", "/api/progress",
    "/api/nutrition", "/api/diet", "/api/meals",
    "/api/body-measurements", "/api/stats", "/api/analytics",

    // Admin
    "/api/admin", "/api/admin/users", "/api/admin/stats",
    "/admin", "/dashboard",

    // Debug
    "/api/debug", "/api/test", "/debug", "/console",

    // Docs
    "/docs", "/api/docs", "/swagger", "/openapi.json",
    "/api-docs", "/documentation",
];

console.log("="repeat(80));
console.log("GYM API COMPREHENSIVE ENDPOINT SCANNER");
console.log("="repeat(80));

const results = {
    accessible: [],
    protected: [],
    other: []
};

// Async scanner
async function scanEndpoints() {
    console.log("\n[PHASE 1] Testing WITHOUT authentication...\n");

    for (const endpoint of endpoints) {
        try {
            const response = await fetch(API_URL + endpoint, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.status !== 404) {
                const emoji = response.status === 200 ? "✅" :
                    response.status === 401 || response.status === 403 ? "🔒" : "⚠️";

                console.log(`${emoji} ${endpoint.padEnd(40)} -> ${response.status}`);

                if (response.status === 200) {
                    results.accessible.push({ endpoint, method: 'GET', auth: false, status: response.status });
                } else if (response.status === 401 || response.status === 403) {
                    results.protected.push({ endpoint, method: 'GET', auth: false, status: response.status });
                } else {
                    results.other.push({ endpoint, method: 'GET', auth: false, status: response.status });
                }
            }
        } catch (e) { }

        // Rate limit - wait 50ms
        await new Promise(r => setTimeout(r, 50));
    }

    console.log("\n[PHASE 2] Testing WITH authentication...\n");

    for (const endpoint of endpoints) {
        try {
            const response = await fetch(API_URL + endpoint, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${TOKEN}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.status !== 404 && response.status === 200) {
                console.log(`✅ ${endpoint.padEnd(40)} -> ${response.status} (with token)`);

                // Check if different from no-auth
                const noAuthResult = results.protected.find(r => r.endpoint === endpoint);
                if (noAuthResult) {
                    console.log(`   ⚡ TOKEN UNLOCKED: ${endpoint}`);
                }

                results.accessible.push({ endpoint, method: 'GET', auth: true, status: response.status });
            }
        } catch (e) { }

        await new Promise(r => setTimeout(r, 50));
    }

    // Summary
    console.log("\n" + "=".repeat(80));
    console.log("SCAN COMPLETE");
    console.log("=".repeat(80));
    console.log(`\nTotal found: ${results.accessible.length + results.protected.length + results.other.length}`);
    console.log(`✅ Accessible (200): ${results.accessible.length}`);
    console.log(`🔒 Protected (401/403): ${results.protected.length}`);
    console.log(`⚠️  Other: ${results.other.length}`);

    console.log("\n✅ ACCESSIBLE ENDPOINTS:");
    results.accessible.forEach(r => {
        console.log(`  ${r.method.padEnd(6)} ${r.endpoint}${r.auth ? ' (auth required)' : ''}`);
    });

    console.log("\n🔒 PROTECTED ENDPOINTS:");
    results.protected.forEach(r => {
        console.log(`  ${r.method.padEnd(6)} ${r.endpoint}`);
    });

    console.log("\n📊 RESULTS OBJECT (copy this):");
    console.log(JSON.stringify(results, null, 2));

    return results;
}

// Run the scanner
console.log("\n🚀 Starting scan... This will take ~10 seconds\n");
scanEndpoints().then(results => {
    console.log("\n✅ Scan complete! Check results above.");
    window.gymApiResults = results; // Save to window for later access
    console.log("\n💾 Results saved to: window.gymApiResults");
});
