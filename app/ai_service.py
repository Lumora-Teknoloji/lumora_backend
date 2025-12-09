import os
import logging
import asyncio
import requests
import time
import uuid
import json
import re
from typing import List, Dict, Any, Optional
from openai import OpenAI
from tavily import TavilyClient
from .config import settings

# FAL Client Import (Güvenli)
try:
    import fal_client  # type: ignore
except ImportError:
    fal_client = None
except Exception as e:
    logging.warning(f"FAL Client import hatası: {e}")
    fal_client = None

# Logger Ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# 1. BAŞLATMA
# -----------------------------------------------------------------------------
openai_client: Optional[OpenAI] = None
tavily_client: Optional[TavilyClient] = None


def initialize_ai_clients():
    global openai_client, tavily_client
    try:
        if settings.openai_api_key:
            # Timeout süresini artırdık
            openai_client = OpenAI(api_key=settings.openai_api_key, timeout=40.0)
            logger.info("✅ OpenAI Hazır")
        if settings.tavily_api_key:
            tavily_client = TavilyClient(api_key=settings.tavily_api_key)
            logger.info("✅ Tavily Hazır")
    except Exception as e:
        logger.error(f"❌ Başlatma Hatası: {e}")


initialize_ai_clients()


# Yardımcı: HTTP olmayan markdown image'larını temizle
def _remove_non_http_images(markdown_text: str) -> str:
    """
    IMG_REF_* gibi placeholder linklerden kaynaklanan kırık görselleri temizler.
    """
    if not markdown_text: return ""
    pattern = r'!\[[^\]]*\]\((?!https?://)[^)]+\)'
    return re.sub(pattern, '', markdown_text)


# [MEVCUT] Görsel Kalite Filtresi (String Bazlı)
def is_quality_fashion_image(url: str) -> bool:
    """
    URL'in bir logo, ikon veya gereksiz grafik olup olmadığını kontrol eder.
    Sadece potansiyel ürün fotoğraflarına izin verir.
    """
    if not url: return False
    url_lower = url.lower()

    # 1. Uzantı Kontrolü (Sadece statik resimler)
    valid_extensions = ('.jpg', '.jpeg', '.png', '.webp')
    has_valid_ext = any(ext in url_lower for ext in valid_extensions)

    # SVG ve GIF kesinlikle yasak
    if '.svg' in url_lower or '.gif' in url_lower:
        return False

    if not has_valid_ext:
        # Uzantı yoksa bile bazı CDN'ler resim döner, o yüzden çok katı olmayalım
        pass

    # 2. Yasaklı Kelimeler
    banned_keywords = [
        'logo', 'icon', 'avatar', 'user', 'profile', 'banner',
        'button', 'sprite', 'svg', 'loader', 'gif', 'promo',
        'footer', 'header', 'favicon', 'thumbnail', 'pixel',
        'sprite', 'blank', 'transparent', 'chart', 'size',
        'overlay', 'track', 'adserver'
    ]

    if any(keyword in url_lower for keyword in banned_keywords):
        return False

    return True


# [YENİ] SerpApi ile Görsel Doğrulama (Varlık Kontrolü)
def verify_image_with_serp(image_url: str) -> bool:
    """
    SerpApi (Google Reverse Image) kullanarak görselin erişilebilir ve 
    Google dizininde bulunabilir olduğunu doğrular.
    """
    if not settings.serp_api_key:
        return True # Anahtar tanımlı değilse bu adımı atla (Güvenli geçiş)

    try:
        # logger.info(f"🔎 SerpApi ile görsel kontrol ediliyor: {image_url}")
        params = {
            "engine": "google_reverse_image",
            "image_url": image_url,
            "api_key": settings.serp_api_key
        }
        # 3 saniye timeout yeterli, sistemi yavaşlatmayalım
        response = requests.get("https://serpapi.com/search.json", params=params, timeout=3)
        
        if response.status_code == 200:
            return True
        elif response.status_code == 401:
            logger.warning("SerpApi yetkilendirme hatası (API Key geçersiz).")
            return True # Sistemi kırmamak için onayla
        else:
            logger.warning(f"SerpApi görseli doğrulayamadı ({response.status_code}): {image_url}")
            return False
            
    except Exception as e:
        logger.warning(f"SerpApi bağlantı hatası: {e}")
        return True # Hata durumunda akışı bozma


# [YENİ] SerpApi ile Görsel Kaynak Sayfasını Bulma
def get_image_source_page_with_serp(image_url: str) -> Optional[str]:
    """
    SerpApi (Google Reverse Image) kullanarak görselin gerçek kaynak sayfasını bulur.
    Returns: Kaynak sayfa URL'si veya None
    """
    if not settings.serp_api_key:
        return None  # Anahtar yoksa None dön

    try:
        logger.info(f"🔍 SerpApi ile görsel kaynak sayfası aranıyor: {image_url[:80]}...")
        params = {
            "engine": "google_reverse_image",
            "image_url": image_url,
            "api_key": settings.serp_api_key
        }
        response = requests.get("https://serpapi.com/search.json", params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            # SerpApi response yapısına göre kaynak sayfayı bul
            # Önce "inline_images" içinde ara
            inline_images = data.get('inline_images', [])
            if inline_images and len(inline_images) > 0:
                first_result = inline_images[0]
                source_url = first_result.get('link') or first_result.get('source') or first_result.get('url')
                if source_url and source_url.startswith('http'):
                    logger.info(f"✅ SerpApi kaynak bulundu (inline_images): {source_url}")
                    return source_url
            
            # Alternatif: "results" içinde ara
            results = data.get('results', [])
            if results and len(results) > 0:
                first_result = results[0]
                source_url = first_result.get('link') or first_result.get('url')
                if source_url and source_url.startswith('http'):
                    logger.info(f"✅ SerpApi kaynak bulundu (results): {source_url}")
                    return source_url
            
            # Alternatif: "visual_matches" içinde ara
            visual_matches = data.get('visual_matches', [])
            if visual_matches and len(visual_matches) > 0:
                first_match = visual_matches[0]
                source_url = first_match.get('link') or first_match.get('url')
                if source_url and source_url.startswith('http'):
                    logger.info(f"✅ SerpApi kaynak bulundu (visual_matches): {source_url}")
                    return source_url
            
            logger.warning(f"SerpApi'de kaynak bulunamadı: {image_url[:80]}...")
            return None
        elif response.status_code == 401:
            logger.warning("SerpApi yetkilendirme hatası (API Key geçersiz).")
            return None
        else:
            logger.warning(f"SerpApi hatası ({response.status_code}): {image_url[:80]}...")
            return None
            
    except Exception as e:
        logger.warning(f"SerpApi bağlantı hatası: {e}")
        return None


# [GÜNCELLENDİ] GPT-4o Vision ile Akıllı Görsel Doğrulama
def validate_images_with_vision(image_urls: List[str]) -> List[str]:
    """
    GPT-4o Vision kullanarak resimlerin gerçekten moda/ürün fotoğrafı olup olmadığını kontrol eder.
    [YENİ ÖZELLİK]: MIME Type Check (HEAD Request) ile bozuk formatları OpenAI'ya göndermeden eler.
    """
    if not image_urls or not openai_client:
        return image_urls

    # 1. Adım: Riskli Domainleri Ele
    risky_domains = ['instagram.com', 'facebook.com', 'cdn.instagram', 'fbcdn.net', 'tiktok.com', 'pinterest']
    initial_candidates = [url for url in image_urls if not any(d in url.lower() for d in risky_domains)][:10]

    # 2. Adım: [YENİ] Gerçek Dosya Türü Kontrolü (HEAD Request)
    valid_candidates = []
    logger.info("📡 Görsellerin gerçek formatları (MIME Type) kontrol ediliyor...")

    for url in initial_candidates:
        try:
            # Sadece başlık bilgisini çekiyoruz (Dosyayı indirmez, çok hızlıdır)
            head_response = requests.head(url, timeout=1.5, allow_redirects=True)
            if head_response.status_code == 200:
                content_type = head_response.headers.get('Content-Type', '').lower()
                # OpenAI sadece bunları destekler: png, jpeg, gif, webp
                allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif']
                if any(t in content_type for t in allowed_types):
                    # [EKLEME] SerpApi Kontrolü
                    if verify_image_with_serp(url):
                        valid_candidates.append(url)
                else:
                    pass
        except Exception:
            pass

    # Eğer hiç geçerli resim kalmadıysa orijinal listeyi (riskli olsa da) dönelim
    if not valid_candidates:
        logger.info("MIME kontrolünden geçen görsel olmadı, ham liste kullanılıyor.")
        return image_urls[:8]

    # En fazla 8 tanesini Vision'a gönder
    final_check_list = valid_candidates[:8]
    logger.info(f"👁️ Vision API'ye {len(final_check_list)} adet temizlenmiş görsel gönderiliyor...")

    # Vision Payload Hazırlığı
    messages_content = [
        {
            "type": "text",
            "text": (
                "You are a strict image filter for a fashion sourcing app. "
                "Analyze these images based on their index (0, 1, 2...)."
                "Return the indices of images that are ONLY:\n"
                "1. Clear fashion product photography (garments, models, mannequins).\n"
                "2. High quality packshots.\n"
                "EXCLUDE: Logos, text banners, size charts, blurry icons, irrelevant objects, or website UI elements.\n"
                "Return ONLY a JSON list of integers. Example: [0, 2, 5]. If none are good, return []."
            )
        }
    ]

    for url in final_check_list:
        messages_content.append({
            "type": "image_url",
            "image_url": {"url": url, "detail": "low"}
        })

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": messages_content}],
            max_tokens=60,
            temperature=0.0
        )

        result_text = response.choices[0].message.content.strip()
        clean_text = result_text.replace("```json", "").replace("```", "").strip()
        
        if not clean_text or clean_text == "[]":
            return []

        try:
            indices = json.loads(clean_text)
        except json.JSONDecodeError:
            logger.error(f"Vision JSON parse hatası: {clean_text}")
            return final_check_list

        if not isinstance(indices, list):
            return final_check_list

        verified_urls = [final_check_list[i] for i in indices if isinstance(i, int) and 0 <= i < len(final_check_list)]
        logger.info(f"✅ Vision Onaylı Görseller: {len(verified_urls)}/{len(final_check_list)}")

        return verified_urls

    except Exception as e:
        logger.error(f"Vision filtre hatası: {e}. Filtre devre dışı bırakılıyor.")
        return final_check_list


# -----------------------------------------------------------------------------
# 2. NİYET ANALİZİ VE SOHBET MODÜLÜ
# -----------------------------------------------------------------------------

def analyze_user_intent(message: str) -> str:
    if not openai_client: return "MARKET_RESEARCH"

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system",
                 "content": "You are a classifier. Classify the user input into 'GENERAL_CHAT' or 'MARKET_RESEARCH'. Return ONLY the category name."},
                {"role": "user", "content": message}
            ],
            temperature=0.0,
            max_tokens=20
        )
        return response.choices[0].message.content.strip()
    except:
        return "MARKET_RESEARCH"


def handle_general_chat(message: str) -> str:
    system_prompt = """
    Sen Kıdemli Moda Stratejisi Asistanısın (AI Fashion Strategist).
    GÖREVİN: Kullanıcının sorusuna profesyonel, güven veren bir dille cevap ver.
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Chat hatası: {e}")
        return "Üzgünüm, şu an yanıt veremiyorum."


# -----------------------------------------------------------------------------
# 3. DERİN PAZAR ARAŞTIRMASI (100+ YORUM ODAKLI)
# -----------------------------------------------------------------------------

def deep_market_research(topic: str) -> Dict[str, Any]:
    if not tavily_client:
        return {"context": "Hata: Tavily Client yok.", "market_images": []}

    logger.info(f"🔍 Derin Pazar Analizi (100+ Yorum & Trend): {topic}")

    # [STRATEJİ] "100+ Yorum" ve "En Çok Değerlendirilen" Vurgusu
    queries = [
        # A. YÜKSEK DEĞERLENDİRME SAYISI ODAKLI
        f"{topic} 100+ yorum alan ürünler trendyol",
        f"{topic} en çok değerlendirilen modeller 2025",
        f"{topic} 1000+ reviews bestsellers",
        # B. TİCARİ TRENDLER - FAST FASHION
        f"site:zara.com {topic} bestsellers",
        f"site:mango.com {topic} en çok satanlar",
        f"site:hm.com {topic} top rated",
        # C. KULLANICI DENEYİMİ
        f"{topic} kullanıcı yorumları ve şikayetleri",
        f"en beğenilen {topic} tavsiyeleri 2025",
    ]

    context_data = "### MARKET DATA (HIGH REVIEW COUNT > 100) & PRODUCT LINKS ###\n"
    raw_image_pool = []
    market_images_result = []

    try:
        all_results = []
        # Görsel-sayfa eşleştirmesi için: her sorgu sonucundaki sayfa URL'lerini sakla
        image_to_page_map = {}  # {img_url: page_url}
        
        for q in queries:
            try:
                # days=90: Yorumların birikmesi için biraz daha geniş zaman (3 ay) idealdir.
                response = tavily_client.search(
                    query=q,
                    search_depth="advanced",
                    include_images=True,
                    max_results=3,
                    days=90
                )
                query_results = response.get('results', [])
                all_results.extend(query_results)
                
                # Bu sorgudan gelen sayfa URL'lerini topla
                page_urls = [res.get('url', '') for res in query_results if res.get('url', '').startswith('http')]
                
                # Bu sorgudan gelen görselleri al ve sayfalarla eşleştir
                raw_imgs = response.get('images', [])
                for img_url in raw_imgs:
                    if img_url and img_url.startswith("http"):
                        raw_image_pool.append(img_url)
                        # Eğer bu görsel için henüz bir sayfa URL'si yoksa, ilk geçerli sayfa URL'sini kullan
                        if img_url not in image_to_page_map and page_urls:
                            image_to_page_map[img_url] = page_urls[0]
            except Exception as inner_e:
                logger.warning(f"Tavily sorgu hatası ({q}): {inner_e}")
                continue

        # --- GÖRSEL FİLTRELEME ---
        candidates_level_1 = [
            img for img in raw_image_pool
            if img and img.startswith("http") and is_quality_fashion_image(img)
        ]

        unique_candidates = list(set(candidates_level_1))
        
        # ADIM 1: Vision API ile görsellerin gerçekten resim olduğu ve moda/ürün fotoğrafı olduğu doğrulanmalı
        logger.info(f"👁️ Vision API ile {len(unique_candidates)} görsel doğrulanıyor...")
        final_market_images = validate_images_with_vision(unique_candidates)
        logger.info(f"✅ Vision API doğrulaması tamamlandı: {len(final_market_images)} görsel onaylandı")
        
        # ADIM 2: Vision'dan geçen görseller için SerpApi reverse search ile gerçek kaynak sayfasını bul
        logger.info(f"🔍 SerpApi reverse search ile {len(final_market_images)} görsel için kaynak sayfası aranıyor...")
        market_images_result = []
        serp_api_enabled = bool(settings.serp_api_key)
        
        for idx, img_url in enumerate(final_market_images):
            source_page = None
            
            # Vision'dan geçen TÜM görseller için SerpApi reverse search yap
            if serp_api_enabled:
                try:
                    logger.info(f"🔎 SerpApi reverse search ({idx+1}/{len(final_market_images)}): {img_url[:60]}...")
                    source_page = get_image_source_page_with_serp(img_url)
                    if source_page:
                        logger.info(f"✅ Kaynak sayfa bulundu: {source_page}")
                    else:
                        logger.info(f"⚠️ Kaynak sayfa bulunamadı, Tavily eşleştirmesi kullanılacak")
                except Exception as e:
                    logger.warning(f"SerpApi hatası (görsel {idx+1}): {e}")
                    source_page = None
            
            # Eğer SerpApi'den kaynak bulunamazsa, Tavily'den gelen eşleştirmeyi kullan
            if not source_page:
                source_page = image_to_page_map.get(img_url, img_url)
                logger.info(f"📌 Tavily eşleştirmesi kullanıldı: {source_page}")
            
            market_images_result.append({
                'img': img_url,
                'page': source_page
            })
        
        logger.info(f"✅ Tüm görseller için kaynak sayfalar bulundu: {len(market_images_result)} görsel hazır")

        # Metin Verilerini İşle
        for i, res in enumerate(all_results):
            url = res.get('url', '')
            if not url.startswith('http'): continue

            context_data += f"--- SONUÇ ID: {i + 1} ---\n"
            context_data += f"BAŞLIK: {res.get('title', 'Başlıksız')}\n"
            context_data += f"İÇERİK: {res.get('content', '')}\n"
            context_data += f"TAM_URL: {url}\n\n"

        context_data += "### PAZAR GÖRSEL HAVUZU ###\n"
        limited_images = market_images_result[:12]

        for i, img_data in enumerate(limited_images):
            img_url = img_data['img'] if isinstance(img_data, dict) else img_data
            context_data += f"IMG_REF_{i + 1}: {img_url}\n"

        return {"context": context_data, "market_images": limited_images}

    except Exception as e:
        logger.error(f"Araştırma Hatası: {e}")
        return {"context": f"Kısmi veri (Hata: {e})\n{context_data}", "market_images": market_images_result}


# -----------------------------------------------------------------------------
# 4. STRATEJİK İMALAT RAPORU (100+ YORUM FİLTRESİ)
# -----------------------------------------------------------------------------

def generate_strategic_report(user_message: str, research_data: str) -> str:
    if not openai_client: return "OpenAI Client başlatılamadı."

    system_prompt = """
    Sen Kıdemli Moda Stratejistisin.

    GÖREVİN:
    Üreticiye 2025/2026 sezonu için **ÇOK YÜKSEK ETKİLEŞİM ALAN (100+ YORUM)** ürünleri baz alan bir rapor hazırla.

    ⚠️ 1. KRİTİK SEÇİM KURALI (100+ YORUM FİLTRESİ):
    - Bölüm 4'te (Rakip Ürünler) rastgele ürün listeleme.
    - 'MARKET DATA' içindeki metinleri tara.
    - **ZORUNLU KRİTER:** Sadece metninde "100+ değerlendirme", "binlerce yorum", "çok satan" veya benzeri ifadeler geçen ürünleri seç.
    - Eğer yorum sayısı net değilse ama "En çok satanlar" listesindeyse kabul et.
    - Raporda her ürünün altına tahmini yorum/etkileşim durumunu yaz (Örn: "1500+ Değerlendirme").

    ⚠️ 2. LİNK KURALI:
    - SADECE 'TAM_URL'si olan, çalışan linkleri kullan.
    - Link formatı: [👉 Ürünü İncele](TAM_URL)

    ⚠️ 3. GÖRSEL YERLEŞİM KURALI:
    - Bölüm 3'te modeller için [[VISUAL_CARD_1]], [[VISUAL_CARD_2]]... placeholderlarını kullan.

    RAPOR FORMATI (Markdown):

    # 🏭 [KONU] - YÜKSEK ETKİLEŞİMLİ (100+ YORUM) İMALAT DOSYASI

    ## 📈 BÖLÜM 1: KİTLE ANALİZİ (YÜKSEK YORUM ALANLAR)
    * **Neden Çok Yorum Aldı?:** (Fiyat/Performans, Trend, vb.)
    * **Kullanıcıların Ortak Övgüleri:**
    * **Kullanıcıların Ortak Şikayetleri:**

    ## 💰 BÖLÜM 2: FİYAT VE PERFORMANS ANALİZİ
    (Tablo Buraya)

    ## 🏆 BÖLÜM 3: ÜRETİLECEK YILDIZ MODELLER (TOP 5)
    ### 1. [Model Adı]
    * **Neden Tutar:** ...
    [[VISUAL_CARD_1]]

    ... (Devamı)

    ## 🛍️ BÖLÜM 4: SAHADA KANITLANMIŞ RAKİPLER (100+ YORUMLU)
    Bu bölümde 100 ve üzeri yorum almış, pazar lideri ürünler listelenir.

    ### 🌟 Rakip 1: [Ürün Başlığı]
    * **Etkileşim:** (Örn: 200+ Yorum / 4.8 Puan)
    * **Fiyat:** ... TL
    * **Link:** [👉 Ürünü İncele](TAM_URL)

    ### 🌟 Rakip 2: [Ürün Başlığı]
    ...

    ## 🔗 KAYNAKÇA
    * [Site Adı](URL)
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"KONU: {user_message}\n\nVERİLER:\n{research_data}"}
            ],
            temperature=0.4
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Rapor oluşturma hatası: {e}")
        return f"Rapor oluşturulurken bir hata oluştu: {e}"


# -----------------------------------------------------------------------------
# 5. GÖRSEL PROMPT
# -----------------------------------------------------------------------------

def generate_image_prompts(analysis_text: str) -> List[Dict[str, str]]:
    """
    Rapor içindeki model isimlerini yakalar ve E-TİCARET'e uygun,
    stüdyo ışıklı, boydan (full body) promptlar üretir.
    """
    system_prompt = """
    You are an AI Fashion Photographer & Prompt Engineer.

    TASK: Extract up to 5 model concepts from the report.
    For each concept, create a highly detailed image prompt optimized for FLUX GENERATION.

    PROMPT RULES (STRICT E-COMMERCE STANDARDS):
    1.  **START WITH:** "Wide-angle full body e-commerce studio shot of..." (Must enforce full body).
    2.  **FRAMING:** "Zoomed out", "Head to toe visibility", "Model standing", "Shoes visible", "No cropping".
    3.  **LIGHTING:** "High-key soft studio lighting", "Bright and evenly lit", "No harsh shadows", "Commercial look".
    4.  **BACKGROUND:** "Clean neutral studio background" or "Solid white background".
    5.  **DETAILS:** "Hyper-realistic fabric texture", "8k resolution", "Sharp focus".
    6.  **POSE:** "Standard e-commerce pose", "Frontal or 3/4 view", "Professional model".

    Output JSON format: 
    {"items": [{"model_name": "...", "ref_id": "IMG_REF_X", "prompt": "..."}]}
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": analysis_text}],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        if not content: return []
        clean_content = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_content)
        return data.get("items", [])
    except Exception as e:
        logger.error(f"Görsel prompt çıkarma hatası: {e}")
        return []


# [MEVCUT] Stil Bağlamı Çıkarıcı
def extract_visual_style(user_text: str) -> str:
    if not openai_client: return ""

    system_msg = """
    You are a 'Visual Style Extractor'. 
    Analyze the user's fashion request and extract the CORE VISUAL CONSTRAINTS (e.g., modesty, specific era, subculture, environment).
    Convert these into comma-separated English keywords for an image generator.
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_text}
            ],
            temperature=0.0,
            max_tokens=60
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return ""


def generate_ai_images(prompt_items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    FAL (flux2-pro) üzerinden görsel üretir.
    Bakiye bitmesi (403) durumunda döngüyü kırar (Circuit Breaker).
    """
    api_key = settings.fal_api_key
    if not api_key:
        logger.info("❕ FAL_API_KEY yok, görsel üretimi atlanıyor.")
        return []

    base_url = getattr(settings, "fal_base_url", "https://fal.run").rstrip("/")
    model_path = getattr(settings, "fal_model_path", "fal-ai/flux/dev").strip("/")
    run_url = f"{base_url}/{model_path}"
    poll_url = f"{base_url}/{model_path}"

    use_sdk = fal_client is not None
    if use_sdk:
        os.environ["FAL_KEY"] = api_key

    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }

    stop_generation = False

    def _run_prompt(prompt: str) -> Optional[str]:
        nonlocal stop_generation
        if stop_generation:
            return None

        fal_args = {
            "prompt": prompt,
            "image_size": "portrait_4_3",
            "num_inference_steps": 40,
            "guidance_scale": 3.5,
            "num_images": 1,
            "enable_safety_checker": False
        }

        # 1. SDK Yöntemi
        if use_sdk:
            try:
                handler = fal_client.submit(
                    model_path,
                    arguments=fal_args,
                )
                result = handler.get()
                images = result.get("images") or result.get("output", {}).get("images")
                if images:
                    first = images[0]
                    if isinstance(first, dict): return first.get("url")
                    return first
            except Exception as e:
                error_str = str(e)
                if "403" in error_str or "Exhausted balance" in error_str or "locked" in error_str:
                    logger.error("🛑 FAL Bakiye Bitti (SDK)! Diğer görseller denenmeyecek.")
                    stop_generation = True
                    return None
                logger.error(f"FAL SDK hata: {e}. HTTP fallback deneniyor.")

        # 2. HTTP Fallback Yöntemi
        try:
            run_resp = requests.post(run_url, headers=headers, json=fal_args, timeout=30)
            if run_resp.status_code == 403:
                logger.error("🛑 FAL Bakiye Bitti (HTTP 403)! Diğer görseller denenmeyecek.")
                stop_generation = True
                return None

            run_resp.raise_for_status()
            data = run_resp.json()

            direct_images = data.get("images") or data.get("output", {}).get("images")
            if direct_images:
                first = direct_images[0]
                if isinstance(first, dict):
                    return first.get("url")
                elif isinstance(first, str):
                    return first

            req_id = data.get("request_id")
            if not req_id:
                logger.error(f"FAL request_id alınamadı: {run_resp.text[:100]}")
                return None

            for _ in range(20):
                time.sleep(2)
                res = requests.get(f"{poll_url}/requests/{req_id}/status", headers=headers, timeout=20)
                
                if res.status_code == 404:
                    res = requests.get(f"{base_url}/requests/{req_id}/status", headers=headers, timeout=20)

                res.raise_for_status()
                poll_data = res.json()
                status = poll_data.get("status")

                if status == "COMPLETED":
                    output = poll_data.get("output")
                    images = poll_data.get("images") or (output.get("images") if output else None)
                    if images:
                        first = images[0]
                        if isinstance(first, dict): return first.get("url")
                        return first
                    break

                if status in ("FAILED", "CANCELLED"):
                    logger.error(f"FAL işlemi başarısız: {status}")
                    break

            return None

        except Exception as e:
            error_str = str(e)
            if "403" in error_str or "Exhausted balance" in error_str:
                logger.error("🛑 FAL Bakiye Bitti (HTTP Exception)! Diğer görseller denenmeyecek.")
                stop_generation = True
            else:
                logger.error(f"FAL HTTP isteği hatası: {e}")
            return None

    results: List[Dict[str, str]] = []
    for item in prompt_items[:5]:
        if stop_generation:
            logger.warning("⚠️ Bakiye yetersizliği nedeniyle görsel üretimi durduruldu.")
            break

        prompt = item.get("prompt")
        if not prompt: continue

        logger.info(f"FAL görsel isteği yapılıyor: {item.get('model_name')}")
        url = _run_prompt(prompt)

        if url:
            results.append({
                "model_name": item.get("model_name", "").strip(),
                "ref_id": item.get("ref_id", "").strip(),
                "url": url
            })
        else:
            if not stop_generation:
                logger.error("FAL görsel isteği başarısız (URL alınamadı).")

    return results


# -----------------------------------------------------------------------------
# 6. ANA ORKESTRASYON
# -----------------------------------------------------------------------------

async def generate_ai_response(user_message: str, generate_images: bool = False) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()

    # ADIM 1: Niyet Analizi
    intent = await loop.run_in_executor(None, analyze_user_intent, user_message)

    if intent == "GENERAL_CHAT":
        chat_response = await loop.run_in_executor(None, handle_general_chat, user_message)
        return {
            "content": chat_response,
            "image_urls": [],
            "process_log": ["Sohbet modu aktif."]
        }

    # ADIM 2: Araştırma
    research_result = await loop.run_in_executor(None, deep_market_research, user_message)

    # ADIM 3: Raporlama
    final_report = await loop.run_in_executor(None, generate_strategic_report, user_message, research_result["context"])

    # ADIM 4: Görsel (Opsiyonel)
    # market_images artık dict listesi: [{'img': '...', 'page': '...'}]
    market_images_list = research_result["market_images"]
    ref_lookup = {}
    for i, img_data in enumerate(market_images_list):
        ref_key = f"IMG_REF_{i + 1}"
        if isinstance(img_data, dict):
            ref_lookup[ref_key] = img_data['img']  # Görsel URL'si
        else:
            # Geriye dönük uyumluluk: eski string formatı
            ref_lookup[ref_key] = img_data

    ai_generated_items: List[Dict[str, str]] = []
    image_triggers = ["çiz", "görsel", "tasarım", "resim", "resimler", "foto", "fotoğraf", "image", "picture", "draw"]
    should_generate_images = True if settings.fal_api_key else (
            generate_images or any(x in user_message.lower() for x in image_triggers))
    ref_ids_ordered = list(ref_lookup.keys())

    if should_generate_images:
        prompt_items = await loop.run_in_executor(None, generate_image_prompts, final_report)
        logger.info(f"Görsel prompt sayısı: {len(prompt_items)}")

        if not prompt_items:
            prompt_items = [{
                "model_name": (user_message[:50] or "AI Model").strip(),
                "ref_id": ref_ids_ordered[0] if ref_lookup else "",
                "prompt": f"Fashion photography of {user_message}"
            }]

        # Stil Enjeksiyonu
        dynamic_style_context = await loop.run_in_executor(None, extract_visual_style, user_message)
        logger.info(f"🎨 Çıkarılan Stil Bağlamı: {dynamic_style_context}")

        master_prefix = "Wide-angle full body shot, camera zoomed out, showing entire outfit from head to toe including shoes, "
        master_style_suffix = ", high-key soft studio lighting, shadowless white background, professional e-commerce catalog photography, 8k, sharp focus, hyper-realistic texture"

        normalized_prompts: List[Dict[str, str]] = []
        for idx, item in enumerate(prompt_items):
            ref_id = (item.get("ref_id") or (
                ref_ids_ordered[idx % len(ref_ids_ordered)] if ref_ids_ordered else "")).strip()

            raw_prompt = item.get("prompt", "").strip()
            enhanced_prompt = f"{master_prefix}{raw_prompt}, {dynamic_style_context}{master_style_suffix}"

            normalized_prompts.append({
                "model_name": item.get("model_name", "").strip(),
                "ref_id": ref_id,
                "prompt": enhanced_prompt
            })

        ai_generated_items = await loop.run_in_executor(None, generate_ai_images, normalized_prompts)
        logger.info(f"Üretilen AI görsel adedi: {len(ai_generated_items)}")
    else:
        logger.info("Görsel üretimi atlandı.")

    # -------------------------------------------------------------------------
    # ADIM 5: SATIR İÇİ GÖRSEL ENTEGRASYONU
    # -------------------------------------------------------------------------
    final_content = final_report

    for i in range(1, 6):
        placeholder = f"[[VISUAL_CARD_{i}]]"

        ai_item = None
        if i <= len(ai_generated_items):
            ai_item = ai_generated_items[i - 1]

        replacement_block = ""

        if ai_item:
            ai_url = ai_item.get("url")
            ref_id = ai_item.get("ref_id")
            model_name = ai_item.get("model_name", "Model")
            market_img_url = ref_lookup.get(ref_id, "")
            
            # Pazar görseli için sayfa URL'sini bul
            market_page_url = ""
            if market_img_url:
                # market_images_list içinden bu görseli bul ve sayfa URL'sini al
                for img_data in market_images_list:
                    img_url = img_data['img'] if isinstance(img_data, dict) else img_data
                    if img_url == market_img_url:
                        if isinstance(img_data, dict):
                            market_page_url = img_data.get('page', market_img_url)
                        else:
                            market_page_url = market_img_url
                        break
                # Eğer bulunamazsa, görsel URL'sini sayfa URL'si olarak kullan
                if not market_page_url:
                    market_page_url = market_img_url

            if market_img_url and ai_url:
                # Pazar görseli: tıklanınca sayfaya gider (HTML link içinde)
                # AI görseli: tıklanınca büyür (sadece resim, markdown formatında)
                replacement_block = f"""
| 🛍️ Pazar Referansı | 🎨 AI Tasarımı ({model_name}) |
| :---: | :---: |
| <a href="{market_page_url}" target="_blank" rel="noopener noreferrer"><img src="{market_img_url}" alt="Pazar Referansı" /></a> | ![]({ai_url}) |
"""
            elif ai_url:
                replacement_block = f"""
| 🎨 AI Tasarımı ({model_name}) |
| :---: |
| ![]({ai_url}) |
"""

        if placeholder in final_content:
            if replacement_block:
                final_content = final_content.replace(placeholder, replacement_block)
            else:
                final_content = final_content.replace(placeholder, "")

    final_content = re.sub(r'\[\[VISUAL_CARD_\d+\]\]', '', final_content)
    final_content = _remove_non_http_images(final_content)

    ai_generated_urls_only = [m["url"] for m in ai_generated_items if m.get("url")]
    # market_images artık dict listesi, sadece görsel URL'lerini çıkar
    market_img_urls_only = [
        img_data['img'] if isinstance(img_data, dict) else img_data 
        for img_data in research_result["market_images"]
    ]
    combined_images = market_img_urls_only + ai_generated_urls_only
    
    # Görsel URL'lerini link URL'leriyle eşleştir (frontend için)
    # Sadece pazar görselleri için link var, AI görselleri için yok (None)
    image_links = {}
    for img_data in research_result["market_images"]:
        if isinstance(img_data, dict):
            img_url = img_data.get('img')
            page_url = img_data.get('page')
            if img_url and page_url and img_url != page_url:
                image_links[img_url] = page_url
    
    # AI görselleri için link yok (None veya boş string)
    for ai_item in ai_generated_items:
        ai_url = ai_item.get("url")
        if ai_url:
            image_links[ai_url] = None  # AI görselleri için link yok

    return {
        "content": final_content,
        "image_urls": combined_images,
        "image_links": image_links,  # {image_url: link_url or None}
        "process_log": [
            "Fiyat aralıkları (Min-Max) analiz edildi.",
            f"{len(research_result['market_images'])} adet ürün görseli ve çalışan link toplandı.",
            f"{len(ai_generated_items)} adet AI görsel üretildi."
        ]
    }
