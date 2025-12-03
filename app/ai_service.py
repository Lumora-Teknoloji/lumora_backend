"""
AI servis modülü - LangChain klasöründeki ajan mantığını içerir.
"""
import os
import json
import base64
import uuid
import logging
import requests
import time
from typing import List, Optional
from openai import OpenAI
from tavily import TavilyClient

from .config import settings

logger = logging.getLogger(__name__)

# AI istemcileri
openai_client: Optional[OpenAI] = None
tavily_client: Optional[TavilyClient] = None

# FLUX API - AIMLAPI.com kullanıyoruz
AIMLAPI_HOST = "https://api.aimlapi.com"  # AIMLAPI.com API host

# İstemcileri başlat
def initialize_ai_clients():
    """AI istemcilerini başlatır."""
    global openai_client, tavily_client
    
    if settings.openai_api_key:
        openai_client = OpenAI(api_key=settings.openai_api_key)
        logger.info("OpenAI client initialized")
    else:
        logger.warning("OpenAI API key not found - AI features will be limited")
    
    if settings.tavily_api_key:
        tavily_client = TavilyClient(api_key=settings.tavily_api_key)
        logger.info("Tavily client initialized")
    else:
        logger.warning("Tavily API key not found - Internet search features will be disabled")


# İstemcileri başlat
initialize_ai_clients()

# Tools schema
tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "internet_aramasi",
            "description": "Moda trendleri, pazar analizleri ve ticari öngörüler için arama yapar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sorgu": {
                        "type": "string",
                        "description": "Detaylı arama sorgusu (Örn: '2025 spring summer plus size evening wear trends Turkey market')"
                    }
                },
                "required": ["sorgu"],
            },
        },
    }
]


def ajan_calistir(kullanici_sorusu: str) -> str:
    """
    Moda asistanı ajanını çalıştırır ve ticari analiz yapar.
    
    Args:
        kullanici_sorusu: Kullanıcının sorusu
        
    Returns:
        AI'ın ürettiği analiz raporu
    """
    if not openai_client:
        logger.error("OpenAI client not initialized - API key is missing")
        return """Üzgünüm, AI servisi şu anda kullanılamıyor. 

**Sorun:** OpenAI API anahtarı yapılandırılmamış.

**Çözüm:** 
1. `.env` dosyasını açın
2. `OPENAI_API_KEY=your-api-key-here` şeklinde API anahtarınızı ekleyin
3. Backend'i yeniden başlatın: `docker-compose restart backend`

API anahtarı almak için: https://platform.openai.com/api-keys"""
    
    # TİCARİ VE LOKAL ODAKLI SYSTEM PROMPT - GÖRSELDEKİ FORMATTA ÇIKTI İÇİN
    system_prompt = """
    Sen Türkiye pazarına ve global trendlere hakim kıdemli bir Moda Satın Alma Direktörüsün (Fashion Buyer) ve Moda Trend Analisti.
    Görevin: Kullanıcının sorusunu YAPILANDIRILMIŞ, GÖRSEL DESTEKLİ ve TİCARİ ODAKLI bir şekilde analiz etmek.

    ÖNEMLİ: Çıktı formatı görsel destekli, yapılandırılmış ve ticari odaklı olmalı. Her bölüm net başlıklar, emojiler ve madde işaretleri ile sunulmalı.

    Rapor Formatın (GÖRSELDEKİ GİBİ YAPILANDIRILMIŞ):

    ## 🎨 RENK TRENDLERİ (COLOR TRENDS)
    Her rengi şu formatta sun:
    **1. [Renk Adı] - [Satış Potansiyeli]**
    - Kısa açıklama (2-3 cümle)
    - Türkiye pazarına uygunluğu
    - Hangi özel günlerde tercih edilir
    - Satış potansiyeli: Yüksek/Orta/Düşük
    
    Örnek format:
    **1. Zümrüt Yeşili - Yüksek Satış Potansiyeli**
    - 2025-2026'nın en güçlü rengi. Lüks görünüm, zarif duruş ve Türk pazarının özel gün tercihlerine uygunluğu ile öne çıkıyor.
    - Özellikle düğün, nişan ve özel davetlerde tercih ediliyor.
    - Satış Potansiyeli: ⭐⭐⭐⭐⭐ (5/5)

    ## ✂️ KESİM TRENDLERİ (CUT TRENDS)
    Her kesimi şu formatta sun:
    **1. [Kesim Adı] - [Özellik]**
    **Öne Çıkan Özellikler:**
    - Madde 1
    - Madde 2
    - Madde 3
    - Madde 4
    
    Örnek format:
    **2. Drape (Drapeli) Detaylar 🔥 2025'in Yıldızı**
    **Öne Çıkan Özellikler:**
    - Sanatsal kıvrımlar ve pililer
    - Problemli bölgeleri estetik şekilde gizler
    - Lüks ve modern görünüm
    - Bel ve kalça bölgesinde şekil verir

    **3. A Kesim (A-Line) - Klasik Tercih**
    **Öne Çıkan Özellikler:**
    - Omuz ve göğüs bölgesinden genişleyen form
    - Kalça ve bacak bölgesini dengeler
    - Maksimum konfor ve hareket özgürlüğü

    **4. Balık / Mermaid Kesim - Cesur Seçim**
    **Öne Çıkan Özellikler:**
    - 2025'te büyük beden segmentinde popülerlik kazanıyor
    - Esnek kumaşlarla üretim önerilir (stretch saten, likra kumaşlar)
    - Vücut hatlarını takip eder, diz seviyesinden genişler

    ## 🧵 KUMAŞ SEÇİMİ (FABRIC SELECTION)
    
    **En Çok Satan Kumaşlar:**
    1. **Şifon:** Hafif, dökümlü, transparan değil
    2. **Saten:** Parlak, dökümlü, lüks görünüm
    3. **İpek Karışımı:** Premium segment için önerilir
    4. **Krep:** Mat, şık, dökümlü
    5. **Tül-Dantel Kombinasyonları:** Romantik detaylar için

    **Büyük Beden İçin Önemli:**
    - Kumaş vücuda yapışmamalı ama aşırı geniş de olmamalı
    - Dökümlü ve akıcı yapı şart
    - Esnek kumaşlar konfor sağlar

    ## 🔥 DETAY TRENDLERİ (DETAIL TRENDS)
    
    **2025-2026'da Öne Çıkan Detaylar:**
    1. **Pul Payet İşlemeler:** Özellikle omuz ve göğüs bölgesinde
    2. **V Yaka:** İnce ve uzun görünüm sağlar
    3. **Kayık Yaka:** Omuz hatlarını zarifçe sergiler
    4. **Uzun Kol / Kısa Kol Seçenekleri:** Mevsimsel esneklik
    5. **Kol ve Etek Uçlarında Transparan Detaylar:** Modern ve hafif görünüm
    6. **Işıltılı Taş İşlemeler:** Akşam davetleri için

    ## 💰 SATIŞ STRATEJİSİ ÖNERİLERİ (SALES STRATEGY SUGGESTIONS)

    **1. Yüksek Satış Potansiyeli Olan Kombinasyonlar:**
    - **1. [Renk] + [Kesim] + [Detay]:** ⭐⭐⭐⭐⭐ (5/5)
    - **2. [Renk] + [Kesim] + [Detay]:** ⭐⭐⭐⭐⭐ (5/5)
    - **3. [Renk] + [Kesim] + [Kumaş]:** ⭐⭐⭐⭐ (4/5)
    - (En az 5 kombinasyon listele)

    **2. Beden Aralığı Önerisi:**
    - **42-54 beden arası geniş stok**
    - **56-60 beden az miktarda**
    - **Standart bedenler:** [Beden numaraları]

    **3. Fiyat Segmentasyonu:**
    - **Ekonomik:** [Kumaş], [Kesim] (500-900 TL arası)
    - **Orta Segment:** [Kumaş], [Detaylar] (900-1500 TL arası)
    - **Premium:** [Özellikler] (1500-2500 TL arası)
    - **Lüks:** [Özel Özellikler] (2500+ TL)
    
    NOT: Fiyatlar Türkiye pazarına uygun, gerçekçi fiyat aralıkları olmalı. Büyük beden abiye elbiseler için minimum 500 TL'den başlamalı.

    **4. TÜRKİYE PAZARI ÖZEL NOTLAR:**
    1. **Tesettür Opsiyonu:** Uzun kol ve kapalı yaka alternatifli modeller sunun
    2. **Mevsimsel Adaptasyon:** Yaz için kolsuz/kısa kol, kış için uzun kol versiyonlar
    3. **Özel Gün Odaklı:** Düğün, nişan, kına gibi etkinlikler için farklı stil seçenekleri
    4. **Hızlı Teslimat:** Online satışta 2-3 gün içinde kargo kritik
    5. **Beden Tablosu Netliği:** Büyük beden kategorisinde doğru ölçü tablosu müşteri memnuniyetini artırır

    **5. SONUÇ ve ÖNERİLER:**
    **En Yüksek Satış Potansiyeli:**
    - **Renkler:** [Renk listesi]
    - **Modeller:** [Kesim listesi]
    - **Detaylar:** [Detay listesi]
    - **Kumaşlar:** [Kumaş listesi]
    
    Sonuç paragrafı: "Türkiye pazarında [kategori] büyüyor ve müşteriler artık sadece beden değil, trend ve şıklık da arıyor. Kaliteli kumaş, doğru kesim ve güncel tasarımlarla bu segmentte başarılı olabilirsiniz."

    ## 📚 KAYNAKLAR (SOURCES)
    - **[1] [Kaynak Başlığı]** - [URL]
    - **[2] [Kaynak Başlığı]** - [URL]
    - **[3] [Kaynak Başlığı]** - [URL]
    (En az 3-5 kaynak)

    ÖNEMLİ KURALLAR:
    - Her bölümü görseldeki gibi yapılandırılmış formatta sun
    - Emojiler kullan (🎨, ✂️, 🧵, 🔥, 💰, 📚)
    - Yıldız puanlaması kullan (⭐⭐⭐⭐⭐)
    - Madde işaretleri ile listele
    - Türkiye pazarına özel notlar ekle
    - Somut veriler ve örnekler kullan
    - Markdown formatını kullan (başlıklar, kalın yazı, listeler)
    - Profesyonel ama görsel destekli bir dil kullan
    
    ÖNEMLİ: Görsel üretimi için marker veya özel ifade kullanma. 
    Sistem otomatik olarak kullanıcı mesajını analiz edip görsel gerekip gerekmediğine karar verecek.
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": kullanici_sorusu}
    ]

    try:
        # İlk LLM Çağrısı - Hız için optimize edilmiş
        # Tavily aramasını sadece trend/pazar sorularında yap (daha hızlı)
        should_search = tavily_client and any(keyword in kullanici_sorusu.lower() for keyword in [
            'trend', 'pazar', 'satış', 'fiyat', 'maliyet', 'analiz', 'rakip', 'türkiye pazarı'
        ])
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools_schema if should_search else None,
            tool_choice="auto" if should_search else None,
            max_tokens=2500,  # Hız için optimize edilmiş token limiti
            temperature=0.7,  # Yaratıcılık ve detay dengesi
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if tool_calls and tavily_client:
            messages.append(response_message)
            for tool_call in tool_calls:
                if tool_call.function.name == "internet_aramasi":
                    args = json.loads(tool_call.function.arguments)
                    logger.info(f"🔎 Ticari İstihbarat Taranıyor: {args.get('sorgu')}")

                    try:
                        # Hız için daha az sonuç ve basic search depth
                        search_result = tavily_client.search(
                            query=args.get("sorgu"),
                            search_depth="basic",  # advanced yerine basic (daha hızlı)
                            max_results=5,  # Hız için daha az sonuç
                        )
                        # Kaynakları daha okunabilir formatta hazırla
                        content_str = json.dumps(search_result, ensure_ascii=False, indent=2)
                    except Exception as e:
                        logger.error(f"Tavily arama hatası: {e}")
                        content_str = f"Arama Hatası: {str(e)}"

                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": "internet_aramasi",
                        "content": content_str,
                    })

            # Final Cevap - Hız için optimize edilmiş
            final_response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=2500,  # Hız için optimize edilmiş token limiti
                temperature=0.7,  # Yaratıcılık ve detay dengesi
            )
            return final_response.choices[0].message.content
        else:
            return response_message.content
            
    except Exception as e:
        logger.error(f"AI ajan hatası: {e}", exc_info=True)
        return f"Üzgünüm, bir hata oluştu: {str(e)}"


def resim_olustur_sdxl_coklu(base_prompt: str, adet: int = 2, stil: str = "", ozel_durumlar: str = "") -> List[str]:
    """
    Stability AI SDXL ile görsel üretimi.
    
    Args:
        base_prompt: Temel görsel prompt'u
        adet: Üretilecek görsel sayısı
        stil: Stil açıklaması
        ozel_durumlar: Özel durumlar (örn: "plus size")
        
    Returns:
        Üretilen görsellerin URL listesi
    """
    if not settings.stability_api_key:
        logger.warning("Stability AI API key not found - Image generation disabled")
        return []

    # 1. BEDEN VE TÜRKIYE PAZARI OPTİMİZASYONU
    body_type_prompt = "standard model size, elegant pose"
    if "büyük beden" in ozel_durumlar.lower() or "plus size" in ozel_durumlar.lower() or "xl" in ozel_durumlar.lower():
        body_type_prompt = (
            "plus size fashion model, curvy body type, voluptuous, "
            "confident elegant pose, graceful standing pose, "
            "realistic body standards, natural body proportions, "
            "flattering silhouette, professional plus-size model"
        )

    # Türkiye pazarı için genel estetik (Daha şık, abartısız, kaliteli)
    market_prompt = "high-end boutique quality, elegant aesthetic suitable for Turkey fashion market"

    # E-ticaret formatı için optimize edilmiş prompt - Temiz, profesyonel, abartısız
    ecommerce_prompt = (
        "full-body shot, product photography style, "
        "clean white background or neutral gray background, "
        "minimalist setting, simple backdrop, "
        "professional e-commerce photography, "
        "even lighting, soft diffused light, no harsh shadows, "
        "natural pose, standing straight, arms at sides or slightly away, "
        "front view, centered composition, "
        "sharp focus on the dress, clear product visibility, "
        "realistic fabric texture, natural fabric drape, "
        "professional but simple, commercial fashion photography, "
        "shot with professional camera, high resolution, "
        "clean, clear, product-focused, "
        "no dramatic poses, no excessive styling, "
        "suitable for online store, catalog style"
    )

    # Final Zenginleştirilmiş Prompt - E-ticaret formatına uygun
    zenginlestirilmis_prompt = (
        f"{base_prompt}, {stil}, {body_type_prompt}, {market_prompt}, "
        f"{ecommerce_prompt}"
    )
    
    # Negative Prompt - E-ticaret formatına uygun olmayan özellikleri filtreler
    negative_prompt = (
        "cartoon, illustration, drawing, painting, sketch, "
        "anime, manga, 3d render, cgi, computer graphics, "
        "low quality, blurry, distorted, deformed, ugly, "
        "bad anatomy, bad proportions, extra limbs, "
        "watermark, signature, text, logo, "
        "unrealistic, fake, artificial, synthetic, "
        "casual wear, streetwear, sportswear, "
        "overly revealing, inappropriate, "
        "dramatic poses, exaggerated poses, theatrical poses, "
        "complex backgrounds, busy backgrounds, cluttered background, "
        "dramatic lighting, harsh shadows, artistic lighting, "
        "editorial style, fashion show, runway, "
        "vogue style, magazine style, artistic photography, "
        "excessive styling, over-styled, "
        "dark moody atmosphere, dramatic atmosphere, "
        "luxury setting, fancy interior, elaborate setting"
    )

    # Stability AI SDXL API endpoint
    url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
    
    headers = {
        "Authorization": f"Bearer {settings.stability_api_key}",
        "Content-Type": "application/json",
    }
    
    logger.info(f"🔑 Stability AI SDXL API Key kullanılıyor: {settings.stability_api_key[:10]}...{settings.stability_api_key[-5:] if len(settings.stability_api_key) > 15 else 'kısa'}")

    try:
        logger.info(f"🎨 {adet} adet görsel çiziliyor (SDXL)... (Beden: {body_type_prompt})")
        logger.info(f"📝 Görsel prompt: {zenginlestirilmis_prompt[:200]}...")
        
        resim_linkleri = []
        
        for i in range(min(adet, 4)):  # Maksimum 4 görsel
            # SDXL API request body - Maksimum gerçekçilik için optimize edilmiş parametreler
            # Yaratıcılık az, gerçekçilik çok
            body = {
                "text_prompts": [
                    {"text": zenginlestirilmis_prompt, "weight": 1.0},
                    {"text": negative_prompt, "weight": -1.0}  # Negative prompt
                ],
                "cfg_scale": 7,  # 7 (daha düşük = daha gerçekçi, yaratıcılık az, aşırı yaratıcılık yok)
                "height": 1024,
                "width": 1024,
                "samples": 1,
                "steps": 50,  # 50 adım (daha fazla işlem = maksimum kalite ve gerçekçilik)
                "style_preset": "photographic",  # Photographic preset (gerçekçilik için)
            }
            
            response = requests.post(url, headers=headers, json=body, timeout=120)

            if response.status_code != 200:
                error_text = response.text
                logger.error(f"❌ Stability AI SDXL Hatası (Status {response.status_code}): {error_text}")
                
                # API key hatası için özel mesaj
                if response.status_code == 401:
                    logger.error("⚠️ Stability AI API key geçersiz!")
                    logger.error("💡 Çözüm: API key'inizi kontrol edin: https://platform.stability.ai/account/keys")
                elif response.status_code == 403:
                    logger.error("⚠️ Stability AI API erişim izni yok!")
                    logger.error("💡 Çözüm: API key'inizin SDXL erişimi olduğundan emin olun.")
                
                break  # Hata varsa döngüden çık
            
            data = response.json()
            
            # Stability AI SDXL response formatı kontrolü
            # Format: {"artifacts": [{"base64": "...", "finishReason": "SUCCESS"}]}
            if "artifacts" not in data or len(data["artifacts"]) == 0:
                logger.error(f"❌ Stability AI yanıtında görsel bulunamadı. Response: {data}")
                break
            
            artifact = data["artifacts"][0]
            if artifact.get("finishReason") != "SUCCESS":
                logger.error(f"❌ Görsel üretimi başarısız. Finish reason: {artifact.get('finishReason')}")
                break
            
            image_base64 = artifact.get("base64")
            if not image_base64:
                logger.error(f"❌ Görsel base64 verisi bulunamadı.")
                break
            
            # Base64 görseli decode et ve kaydet
            try:
                image_bytes = base64.b64decode(image_base64)
                static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
                os.makedirs(static_dir, exist_ok=True)
                
                dosya_adi = f"design_{uuid.uuid4().hex[:8]}_{i}.png"
                dosya_yolu = os.path.join(static_dir, dosya_adi)
                
                with open(dosya_yolu, "wb") as f:
                    f.write(image_bytes)
                
                backend_url = f"http://localhost:{settings.port}"
                link = f"{backend_url}/static/{dosya_adi}"
                resim_linkleri.append(link)
                logger.info(f"✅ Görsel {i+1} üretildi ve kaydedildi: {dosya_adi}")
                
                # Her görsel arasında kısa bir bekleme (rate limit için)
                if i < min(adet, 4) - 1:
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"❌ Görsel kaydetme hatası: {e}")
                continue
        
        logger.info(f"✅ {len(resim_linkleri)} görsel üretildi (SDXL)")
        return resim_linkleri

    except Exception as e:
        logger.error(f"Stability AI SDXL İstek Hatası: {e}", exc_info=True)
        return []


def should_generate_images_for_message(user_message: str) -> bool:
    """
    Kullanıcı mesajına göre görsel üretilip üretilmeyeceğini belirler.
    
    Args:
        user_message: Kullanıcının mesajı
        
    Returns:
        True eğer görsel üretilmeli, False değilse
    """
    if not user_message:
        return False
    
    message_lower = user_message.lower()
    
    # Görsel isteyen kelimeler
    image_request_keywords = [
        'görsel', 'resim', 'fotoğraf', 'foto', 'görüntü', 'image', 'picture', 'photo',
        'göster', 'gösterebilir misin', 'çiz', 'çizebilir misin', 'tasarım',
        'nasıl görünür', 'nasıl görünüyor', 'görünüm', 'görünüş'
    ]
    
    # Kıyafet fikri isteyen kelimeler (genişletilmiş - görsel üretimi için)
    fashion_idea_keywords = [
        'fikir', 'öner', 'öneri', 'tasarım', 'tasarım fikri', 'kıyafet fikri',
        'ne giyeyim', 'ne giysem', 'nasıl giyinsem', 'kombin', 'kombinasyon',
        'outfit', 'look', 'style', 'stil', 'moda', 'fashion',
        'nasıl olmalı', 'nasıl olur', 'nasıl yapmalı', 'nasıl yapılır',
        'tasarım öner', 'kıyafet öner', 'giyim öner',
        'abiye', 'elbise', 'kıyafet', 'giyim', 'gömlek', 'pantolon', 'etek',
        'ceket', 'mont', 'kaban', 'şal', 'atkı', 'çanta', 'ayakkabı',
        'büyük beden', 'plus size', 'beden', 'model', 'kesim', 'renk',
        'kumaş', 'desen', 'stil', 'trend', '2025', '2026',
        # Moda kategorileri - görsel üretimi için
        'gece', 'gündüz', 'günlük', 'spor', 'iş', 'okul', 'düğün', 'nişan',
        'parti', 'davet', 'özel gün', 'yaz', 'kış', 'sonbahar', 'ilkbahar'
    ]
    
    # Görsel isteği kontrolü - ÖNCELİKLİ (PROMPT'TA GÖRSEL İSTEDİYSE KESİNLİKLE ÜRET)
    for keyword in image_request_keywords:
        if keyword in message_lower:
            logger.info(f"🎨 GÖRSEL ÜRETİMİ TETİKLENDİ (görsel isteği - KESİNLİKLE ÜRETİLECEK): '{keyword}'")
            return True
    
    # Kıyafet fikri isteği kontrolü - PROMPT'TA FİKİR İSTEDİYSE GÖRSEL ÜRET
    for keyword in fashion_idea_keywords:
        if keyword in message_lower:
            logger.info(f"🎨 GÖRSEL ÜRETİMİ TETİKLENDİ (kıyafet fikri - KESİNLİKLE ÜRETİLECEK): '{keyword}'")
            return True
    
    # Soru cümleleri kontrolü (kıyafet hakkında) - PROMPT'TA SORU VARSA GÖRSEL ÜRET
    question_patterns = [
        'nasıl görünür', 'nasıl görünüyor', 'nasıl olmalı', 'nasıl olur',
        'ne giyeyim', 'ne giysem', 'hangi kıyafet', 'hangi giyim'
    ]
    for pattern in question_patterns:
        if pattern in message_lower:
            logger.info(f"🎨 GÖRSEL ÜRETİMİ TETİKLENDİ (soru kalıbı - KESİNLİKLE ÜRETİLECEK): '{pattern}'")
            return True
    
    logger.info("📝 Görsel üretilmeyecek - normal cevap verilecek")
    return False


def should_generate_images_from_response(ai_response: str) -> bool:
    """
    AI cevabını analiz ederek görsel üretilip üretilmeyeceğini belirler.
    Prompt'ta görsel isteği varsa kesinlikle görsel üretilmeli.
    
    Args:
        ai_response: AI'ın ürettiği cevap
        
    Returns:
        True eğer görsel üretilmeli, False değilse
    """
    if not ai_response:
        return False
    
    response_lower = ai_response.lower()
    
    # Görsel üretimi gerektiren ifadeler (AI cevabında) - DAHA GENİŞ KAPSAMLI
    # Öncelikle marker kontrolü yap (farklı varyasyonları kontrol et)
    marker_variations = [
        '[görsel_üretimi_gerekli]',
        '[görsel üretimi gerekli]',
        'görsel_üretimi_gerekli',
        'görsel üretimi gerekli',
        'görsel üretimi yapılmalı',
        'görsel üretimi gereklidir',
        'görsel üretimi yapılacak'
    ]
    for marker in marker_variations:
        if marker in response_lower:
            logger.info(f"🎨 AI cevabında görsel üretimi marker'ı bulundu: '{marker}'")
            return True
    
    # Marker yoksa, diğer ifadeleri kontrol et (DAHA GENİŞ KAPSAMLI)
    image_indicators = [
        # Açık görsel istekleri
        'görsel', 'resim', 'fotoğraf', 'foto', 'görüntü', 'image', 'picture', 'photo',
        'görsel referans', 'görsel açıklama', 'görsel öneri',
        'üretilecek görseller', 'görsel üretimi', 'görsel tasarım',
        'görselde', 'görseldeki', 'görsel olarak', 'görsel şekilde',
        'çizim', 'tasarım görseli', 'moda görseli', 'kıyafet görseli',
        'görsel üretimi yapılmalı', 'görsel referansı gerekli', 'görsel tasarım önerilir',
        # Moda/kıyafet açıklamaları (görsel gerektirir)
        'renk trendleri', 'kesim trendleri', 'kumaş seçimi', 'detay trendleri',
        'kombinasyon', 'outfit', 'look', 'stil', 'tasarım',
        # Açıklayıcı ifadeler (görsel gerektirir)
        'nasıl görünür', 'nasıl görünüyor', 'görünüm', 'görünüş',
        'şu şekilde', 'bu şekilde', 'böyle', 'şöyle'
    ]
    
    for indicator in image_indicators:
        if indicator in response_lower:
            logger.info(f"🎨 AI cevabında görsel üretimi gerektiren ifade bulundu: '{indicator}'")
            return True
    
    return False


async def generate_ai_response(user_message: str, generate_images: bool = False) -> dict:
    """
    Kullanıcı mesajına AI yanıtı üretir.
    PROMPT'TA GÖRSEL İSTEDİĞİNDE KESİNLİKLE GÖRSEL ÜRETİLİR.
    
    Args:
        user_message: Kullanıcının mesajı
        generate_images: Görsel üretilsin mi? (manuel override)
        
    Returns:
        {
            "content": AI yanıtı,
            "image_urls": Görsel URL'leri (varsa)
        }
    """
    import asyncio
    
    # AI analiz raporu ve görsel üretimini paralel yap (hız için)
    loop = asyncio.get_event_loop()
    ajan_sorusu = f"{user_message}. (Bağlam: Türkiye Pazarı, Satış Odaklı, Kaynaklı)"
    
    # AI raporu üret
    rapor = await loop.run_in_executor(None, ajan_calistir, ajan_sorusu)
    
    # SADECE kullanıcı mesajından görsel isteği kontrolü
    # AI cevabından görsel üretimi kontrolü KALDIRILDI
    should_generate_from_message = should_generate_images_for_message(user_message)
    
    # SADECE kullanıcı mesajında görsel/fikir isteği varsa görsel üret
    final_should_generate = generate_images or should_generate_from_message
    
    logger.info(f"🔍 Görsel üretim kontrolü: user_message='{user_message[:50]}...', generate_images={generate_images}, should_generate_from_message={should_generate_from_message}, final_should_generate={final_should_generate}, stability_key={'SET' if settings.stability_api_key else 'NOT SET'}")
    
    if should_generate_from_message:
        logger.info("🎨 KULLANICI MESAJINDA GÖRSEL/FİKİR İSTEĞİ VAR - GÖRSEL ÜRETİLECEK!")
    
    resim_linkleri = []
    if final_should_generate and settings.stability_api_key:
        konu = user_message.lower()
        
        # AI cevabından görsel üretimi için özel bilgiler çıkar (varsa)
        # Örneğin: renk, kesim, kumaş, detay bilgileri
        ai_renk_bilgisi = ""
        ai_kesim_bilgisi = ""
        ai_kumas_bilgisi = ""
        
        # AI cevabından önemli bilgileri çıkar
        if "zümrüt" in rapor.lower() or "yeşil" in rapor.lower():
            ai_renk_bilgisi = "emerald green, zümrüt yeşili"
        if "drape" in rapor.lower() or "drapeli" in rapor.lower():
            ai_kesim_bilgisi = "draped, flowing, elegant drape details"
        if "saten" in rapor.lower() or "satin" in rapor.lower():
            ai_kumas_bilgisi = "satin fabric, luxurious satin texture"
        
        # FLUX prompt'unu oluştur - kullanıcı mesajı + AI cevabından çıkarılan bilgiler
        base_prompt_parts = [f"Professional fashion design sketch and high-end fashion photography of {user_message}"]
        
        if ai_renk_bilgisi:
            base_prompt_parts.append(f"in {ai_renk_bilgisi} color")
        if ai_kesim_bilgisi:
            base_prompt_parts.append(f"with {ai_kesim_bilgisi}")
        if ai_kumas_bilgisi:
            base_prompt_parts.append(f"made of {ai_kumas_bilgisi}")
        
        base_prompt_parts.append("detailed fabric texture, elegant styling, Turkey fashion market aesthetic")
        base_prompt = ", ".join(base_prompt_parts)
        
        ozel_durumlar = ""
        if "büyük beden" in konu or "plus size" in konu or "xl" in konu or "büyük" in konu:
            ozel_durumlar = "plus size"
        
        logger.info(f"🎨 Görsel üretiliyor (SDXL'a gönderiliyor): {base_prompt}")
        # Görsel üretimini thread pool'da çalıştır
        resim_linkleri = await loop.run_in_executor(
            None,
            resim_olustur_sdxl_coklu,
            base_prompt,
            2,  # 2 görsel üretilecek
            "Modern, Elegant, Commercial Fashion",
            ozel_durumlar
        )
        logger.info(f"✅ {len(resim_linkleri)} görsel üretildi")
    elif final_should_generate and not settings.stability_api_key:
        logger.warning("⚠️ Stability AI API key bulunamadı - görsel üretilemiyor (PROMPT'TA GÖRSEL İSTENMİŞTİ!)")
    elif not final_should_generate:
        logger.info("📝 Görsel üretilmeyecek - mesaj ve cevap analizi sonucu")
    
    return {
        "content": rapor,
        "image_urls": resim_linkleri
    }

