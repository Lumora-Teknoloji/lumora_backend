# 🛡️ Güvenlik Testleri - Hızlı Kullanım

## ⚡ TEK KOMUTLA ÇALIŞTIR

```bash
python run_all_security_tests.py
```

Bu komut:
- ✅ Tüm güvenlik testlerini çalıştırır
- ✅ Sonuçları `latest_test_results.json` dosyasına yazar
- ✅ Konsola özet rapor gösterir

## 🌐 SONUÇLARI GÖRMEK İÇİN

Tarayıcıda aç:
```
security_results_auto.html
```

Ya da:
- Dosyaya çift tıkla
- Tarayıcıda `file://C:/Users/Esisya/.gemini/antigravity/scratch/LangChain_backend/security_tests/security_results_auto.html` aç

## 📊 ÖZELLİKLER

- **Otomatik Güncelleme**: Her 5 saniyede bir yenilenir
- **Özet Kartlar**: Toplam, Başarılı, Başarısız, Başarı Oranı
- **Detaylı Sonuçlar**: Her testin çıktısı ve hatalar
- **Canlı Zaman Damgası**: Son güncelleme zamanı

## 🚀 İŞ AKIŞI

1. Testleri çalıştır: `python run_all_security_tests.py`
2. HTML'yi aç: `security_results_auto.html`
3. Sonuçları izle (otomatik yenilenir)

## ⚠️ NOT

HTML dosyası otomatik olarak `latest_test_results.json` dosyasını okur.
Test çalıştırmadan önce HTML'yi açarsanız "Sonuçlar yüklenemedi" hatası alırsınız.
