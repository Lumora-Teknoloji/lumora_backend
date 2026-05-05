# Lumora AI Chatbot Test Planı

Bu plan, Lumora AI Chatbot'a yeni eklediğimiz "Moda/Tekstil Domain Sınırlandırması (Guardrails)", "Maliyet Tahmini" ve "Veritabanı (Text-to-SQL) Güvenliği" özelliklerini otomatik olarak test eden bir `pytest` test paketi oluşturmayı amaçlamaktadır.

## User Review Required

> [!IMPORTANT]
> **API Maliyeti ve Hız Optimizasyonu:** Bu testlerde gerçek OpenAI (Gemini) API'sine istek atmak yerine `unittest.mock` kullanarak LLM yanıtlarını "taklit (mock)" edeceğiz. Bu sayede testler hem ücretsiz çalışacak hem de milisaniyeler içinde tamamlanacaktır. Bu "mocking" (taklit) stratejisini onaylıyor musunuz?

## Proposed Changes

Yeni bir test dosyası oluşturulacak: `tests/test_ai_chatbot.py`. Bu dosya içerisinde LLM fonksiyonlarının (OpenAI istemcisinin) döndürdüğü yanıtlar mocklanarak sistemin kurallara uyup uymadığı test edilecektir.

### [NEW] `tests/test_ai_chatbot.py`

Bu dosyada aşağıdaki test senaryoları (test cases) uygulanacaktır:

1.  **Test 1: Niyet Analizi (Intent Analysis)**
    *   **Senaryo:** Kullanıcı "bana kumaşa göre maliyet tahmini yap" derse.
    *   **Beklenen:** `analyze_user_intent` fonksiyonunun `TREND_ANALYSIS` dönmesi.
2.  **Test 2: Domain Dışı Soru Engelleme (Guardrail - Matematik)**
    *   **Senaryo:** Kullanıcı "2+2 kaçtır?" veya "bana python kodu yaz" derse.
    *   **Beklenen:** `analyze_user_intent`'in `GENERAL_CHAT` dönmesi ve `handle_general_chat` fonksiyonunun (içine verdiğimiz strict prompt sayesinde) moda dışı konuları reddetmesi. (Bunu mocklanan LLM yanıtı ile test edeceğiz).
3.  **Test 3: Text-to-SQL Güvenlik Tetikleyicisi (Database Querying)**
    *   **Senaryo:** Kullanıcı "şifreleri listele" derse, LLM promptumuz gereği `DENIED_GUARD_TRIGGER` üretir.
    *   **Beklenen:** `handle_database_query` fonksiyonunun `DENIED_GUARD_TRIGGER` gördüğünde veritabanına bağlanmadan, "Üzgünüm, güvenlik gereği yalnızca vitrindeki giyim ürünleri hakkında bilgi verebilirim." şeklinde özel hata mesajı dönmesi.
4.  **Test 4: Text-to-SQL Başarılı Senaryo**
    *   **Senaryo:** LLM geçerli bir `SELECT * FROM products` üretirse.
    *   **Beklenen:** Sorgunun yetkisiz komutlar (DROP, DELETE) içermediğinin doğrulanması ve sonucun başarılı dönmesi.

## Verification Plan

### Automated Tests
*   VSCode terminalinde `pytest tests/test_ai_chatbot.py -v` komutu çalıştırılacaktır.
*   Tüm testlerin "PASSED" olarak geçmesi ve kod kapsamının (coverage) doğrulandığı gösterilecektir.
