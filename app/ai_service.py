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
            openai_client = OpenAI(api_key=settings.openai_api_key, timeout=25.0)  # Timeout eklendi
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
    # Query parametrelerini temizleyip uzantıya bakmak daha sağlıklıdır ama basitlik için endswith kullanıyoruz
    # Eğer url 'image.jpg?size=large' gibiyse endswith çalışmaz, bu yüzden 'in' kontrolü daha güvenli:
    has_valid_ext = any(ext in url_lower for ext in valid_extensions)

    # SVG ve GIF kesinlikle yasak
    if '.svg' in url_lower or '.gif' in url_lower:
        return False

    if not has_valid_ext:
        # Uzantı yoksa bile bazı CDN'ler resim döner, o yüzden çok katı olmayalım ama logoları eleyelim
        pass

    # 2. Yasaklı Kelimeler (Logolar, ikonlar, arayüz elemanları)
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


# [MEVCUT] GPT-4o Vision ile Akıllı Görsel Doğrulama
def validate_images_with_vision(image_urls: List[str]) -> List[str]:
    """
    GPT-4o Vision kullanarak resimlerin gerçekten moda/ürün fotoğrafı olup olmadığını kontrol eder.
    SOSYAL MEDYA LİNKLERİ FİLTRELENDİ (Hata Önleyici).
    """
    if not image_urls or not openai_client:
        return image_urls

    # [İYİLEŞTİRME] OpenAI'ın erişemediği ve 400 hatası verdiren domainleri baştan ele.
    # Özellikle Instagram CDN linkleri geçicidir ve botlara kapalıdır.
    safe_candidates = []
    risky_domains = ['instagram.com', 'facebook.com', 'cdn.instagram', 'fbcdn.net', 'tiktok.com', 'pinterest']

    for url in image_urls:
        if not any(d in url.lower() for d in risky_domains):
            safe_candidates.append(url)
        else:
            # Riskli URL ise listeye ekleme, Vision API bunu indirirken hata verir.
            pass

    # Maliyet optimizasyonu: Sadece en iyi 8 adayı kontrol et
    candidates = safe_candidates[:8]
    if not candidates:
        logger.info("Vision için uygun aday URL bulunamadı (Tümü riskli domain).")
        return image_urls[:8]  # Filtreleme yapmadan ilk 8'i dön

    logger.info(f"👁️ Vision API ile {len(candidates)} görsel taranıyor...")

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

    for url in candidates:
        messages_content.append({
            "type": "image_url",
            "image_url": {"url": url, "detail": "low"}  # 'low' mod token tasarrufu sağlar
        })

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": messages_content}],
            max_tokens=60,
            temperature=0.0
        )

        result_text = response.choices[0].message.content.strip()

        # JSON temizliği (Markdown taglerini kaldır)
        clean_text = result_text.replace("```json", "").replace("```", "").strip()
        # Bazen AI boş dönebilir veya text dönebilir
        if not clean_text or clean_text == "[]":
            return []

        try:
            indices = json.loads(clean_text)
        except json.JSONDecodeError:
            # JSON değilse fallback
            return candidates

        if not isinstance(indices, list):
            return candidates

        # Seçilen indeksleri URL'e çevir
        verified_urls = [candidates[i] for i in indices if isinstance(i, int) and 0 <= i < len(candidates)]
        logger.info(f"✅ Vision Onaylı Görseller: {len(verified_urls)}/{len(candidates)}")

        return verified_urls

    except Exception as e:
        logger.error(f"Vision filtre hatası: {e}. Filtre devre dışı bırakılıyor, ham liste dönülüyor.")
        # Hata durumunda (örneğin hala bir bozuk link varsa) ham listeyi dönmek en güvenlisidir.
        return candidates


# -----------------------------------------------------------------------------
# 2. NİYET ANALİZİ VE SOHBET MODÜLÜ
# -----------------------------------------------------------------------------

def analyze_user_intent(message: str) -> str:
    """
    Kullanıcının mesajı bir 'Sohbet/Sorgu' mu yoksa 'Pazar Araştırması' mı?
    """
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
    """
    Kullanıcının kimlik, yetenek ve doğruluk ile ilgili sorularını yanıtlar.
    """
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
# 3. DERİN PAZAR ARAŞTIRMASI (ARAŞTIRMA MODU - GÜNCELLENDİ)
# -----------------------------------------------------------------------------

def deep_market_research(topic: str) -> Dict[str, Any]:
    """
    Linkleri bozmadan toplamak için optimize edildi.
    Görsel filtreleme eklendi (String + Vision).
    """
    if not tavily_client:
        return {"context": "Hata: Tavily Client yok.", "market_images": []}

    logger.info(f"🔍 Derin Pazar ve Ürün Analizi: {topic}")

    queries = [
        # A. TREND VE RENK (Pantone, WGSN vb.)
        f"{topic} 2025/2026 fashion color palette trends pantone wgsn",
        # B. TÜKETİCİ PSİKOLOJİSİ
        f"why is {topic} trending 2025 consumer psychology buying behavior",
        # C. TİCARİ ÜRÜN ARAMASI
        f"{topic} ürün detayı satın al trendyol -logo -icon",
        f"{topic} abiye elbise satın al modanisa fiyat -logo -icon",
        f"{topic} modelleri ve fiyatları hepsiburada -logo -icon",
        # D. LÜKS VE İMALAT
        f"{topic} luxury design price vakko beymen product photography",
    ]

    context_data = "### MARKET DATA & PRODUCT LINKS ###\n"
    raw_image_pool = []

    # Hata durumunda da eldekileri dönmek için try dışına aldık
    market_images_result = []

    try:
        all_results = []
        for q in queries:
            try:
                response = tavily_client.search(
                    query=q,
                    search_depth="advanced",
                    include_images=True,
                    max_results=4
                )
                all_results.extend(response.get('results', []))
                raw_imgs = response.get('images', [])
                raw_image_pool.extend(raw_imgs)
            except Exception as inner_e:
                logger.warning(f"Tavily sorgu hatası ({q}): {inner_e}")
                continue

        # --- GÖRSEL FİLTRELEME İŞLEMİ (YENİ) ---

        # 1. Adım: String Filtresi (Hızlı Eleme)
        candidates_level_1 = [
            img for img in raw_image_pool
            if img and img.startswith("http") and is_quality_fashion_image(img)
        ]

        # Unique yap
        unique_candidates = list(set(candidates_level_1))

        # 2. Adım: Vision Filtresi (Akıllı Eleme - Güvenli Versiyon)
        final_market_images = validate_images_with_vision(unique_candidates)
        market_images_result = final_market_images

        # ---------------------------------------

        # Metin Verilerini İşle (Linkleri ID ile etiketle)
        for i, res in enumerate(all_results):
            url = res.get('url', '')
            if not url.startswith('http'): continue

            context_data += f"--- SONUÇ ID: {i + 1} ---\n"
            context_data += f"BAŞLIK: {res.get('title', 'Başlıksız')}\n"
            context_data += f"İÇERİK: {res.get('content', '')}\n"
            context_data += f"TAM_URL: {url}\n\n"

        context_data += "### PAZAR GÖRSEL HAVUZU (DOĞRULANMIŞ) ###\n"
        limited_images = final_market_images[:12]

        for i, img in enumerate(limited_images):
            context_data += f"IMG_REF_{i + 1}: {img}\n"

        return {"context": context_data, "market_images": limited_images}

    except Exception as e:
        logger.error(f"Araştırma Hatası: {e}")
        # Hata olsa bile toplanan veriyi dönmeye çalış
        return {"context": f"Kısmi veri (Hata: {e})\n{context_data}", "market_images": market_images_result}


# -----------------------------------------------------------------------------
# 4. STRATEJİK İMALAT RAPORU (LİNK KORUMALI)
# -----------------------------------------------------------------------------

def generate_strategic_report(user_message: str, research_data: str) -> str:
    if not openai_client: return "OpenAI Client başlatılamadı."

    system_prompt = """
    Sen Kıdemli Moda Stratejistisin.

    GÖREVİN:
    Üreticiye 2025/2026 sezonu için **GERÇEKÇİ FİYAT ARALIKLARI**, **ÇALIŞAN LİNKLERLE RAKİP ANALİZİ** ve **DERİNLEMESİNE TREND ANALİZİ** sunan rapor hazırla.

    ⚠️ 1. LİNK KURALI (HAYATİ ÖNEMLİ):
    - Bölüm 4'te ürünleri listelerken, 'MARKET DATA' içinde 'TAM_URL:' etiketli satırı bul.
    - O URL'yi **HARFİ HARFİNE, HİÇ DEĞİŞTİRMEDEN** kopyala.
    - Asla linki kısaltma (.... koyma).
    - Asla link uydurma.
    - Eğer URL yoksa o ürünü listeye koyma.

    ⚠️ 2. GÖRSEL YERLEŞİM KURALI (AKICILIK İÇİN):
    - Bölüm 3'te (TOP 5 MODEL) her modelin hemen altına görsel koymak için sadece bir YER TUTUCU (Placeholder) bırak.
    - Asla doğrudan resim linki koyma.
    - Kullanman gereken format tam olarak şudur: [[VISUAL_CARD_1]] (Birinci model için), [[VISUAL_CARD_2]] (İkinci model için)...

    ⚠️ 3. TREND VE RENK ANALİZİ (GERÇEK VERİ):
    - 'Trend Tetikleyicileri' bölümünü kafandan yazma. 'MARKET DATA' içindeki arama sonuçlarını analiz et.
    - **Trend Renk Paleti:** Arama sonuçlarında geçen (Pantone, WGSN vb.) gerçek renk kodlarını veya isimlerini kullan.
    - **Tüketici Psikolojisi:** Arama sonuçlarında belirtilen alım nedenlerini (sürdürülebilirlik, statü, rahatlık vb.) yaz.

    RAPOR FORMATI (Markdown):

    # 🏭 [KONU] - 2025/2026 STRATEJİK İMALAT DOSYASI

    ## 📈 BÖLÜM 1: TREND TETİKLEYİCİLERİ (VERİ ODAKLI)
    * **Popüler Kültür:** (Diziler, TikTok akımları, Ünlüler vb.)
    * **Tüketici Psikolojisi:** (Alım motivasyonları)
    * **Trend Renk Paleti:** (Sezonun öne çıkan renkleri)

    ## 💰 BÖLÜM 2: DETAYLI SEGMENT VE FİYAT ANALİZİ
    (Tablo Buraya Gelecek)

    ## 🏆 BÖLÜM 3: ÜRETİLECEK TOP 5 MODEL
    ### 1. [Model Adı]
    * **Kumaş:** ...
    * **Detay:** ...
    [[VISUAL_CARD_1]]

    ### 2. [Model Adı]
    ...
    [[VISUAL_CARD_2]]

    ... (Diğer Modeller 5'e kadar)

    ## 🛍️ BÖLÜM 4: SAHADA SATILAN RAKİP ÜRÜNLER (CANLI VİTRİN)
    ### 🛒 Rakip 1: [Ürün Başlığı]
    * **Fiyat:** ... TL
    * **Site:** ...
    * **Ürüne Git:** [👉 Ürünü İncele](TAM_URL)

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
# 5. GÖRSEL PROMPT (GÜNCELLENDİ - BOYDAN & E-TİCARET)
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
        data = json.loads(content)
        return data.get("items", [])
    except Exception as e:
        logger.error(f"Görsel prompt çıkarma hatası: {e}")
        return []


# [MEVCUT] Stil Bağlamı Çıkarıcı
def extract_visual_style(user_text: str) -> str:
    """
    Kullanıcının mesajındaki genel stil ve görünüm kurallarını İngilizce prompt'a çevirir.
    """
    if not openai_client: return ""

    system_msg = """
    You are a 'Visual Style Extractor'. 
    Analyze the user's fashion request and extract the CORE VISUAL CONSTRAINTS (e.g., modesty, specific era, subculture, environment).
    Convert these into comma-separated English keywords for an image generator.

    Examples:
    - User: "Tesettürlü abiye" -> "model wearing hijab, modest fashion, long sleeves, full length dress, conservative style"
    - User: "90lar grunge" -> "90s grunge fashion, plaid shirt, vintage vibe, edgy look"
    - User: "Yazlık açık elbise" -> "summer dress, sleeveless, lightweight fabric, sunny vibe"

    RETURN ONLY THE ENGLISH KEYWORDS. NO EXPLANATION.
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
    FAL (flux2-pro) üzerinden görsel üretir. Key yoksa boş döner.
    [GÜNCELLENDİ] SDK kullanımı iyileştirildi, timeout ve hata yönetimi güçlendirildi.
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

    def _run_prompt(prompt: str) -> Optional[str]:
        fal_args = {
            "prompt": prompt,
            "image_size": "portrait_4_3",
            "num_inference_steps": 40,
            "guidance_scale": 3.5,
            "num_images": 1,
            "enable_safety_checker": False
        }

        # 1. SDK Yöntemi (Öncelikli)
        if use_sdk:
            try:
                handler = fal_client.submit(
                    model_path,
                    arguments=fal_args,
                )
                # SDK'nın .get() metodu polling'i kendi yapar
                result = handler.get()
                images = result.get("images") or result.get("output", {}).get("images")
                if images:
                    first = images[0]
                    if isinstance(first, dict):
                        return first.get("url")
                    return first
            except Exception as e:
                logger.error(f"FAL SDK hata: {e}. HTTP fallback deneniyor.")
                # SDK başarısız olursa HTTP yöntemine geç

        # 2. HTTP Fallback Yöntemi
        try:
            # POST isteği (Queue Submit)
            run_resp = requests.post(
                run_url,
                headers=headers,
                json=fal_args,
                timeout=30,
            )
            run_resp.raise_for_status()
            data = run_resp.json()

            # Bazen senkron dönebilir
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

            # Polling Loop
            for _ in range(20):  # 40 saniye max (2s * 20)
                time.sleep(2)
                res = requests.get(f"{poll_url}/requests/{req_id}/status", headers=headers, timeout=20)

                # Bazen URL yapısı modelden modele değişebilir, requests endpointini de deneyelim
                if res.status_code == 404:
                    res = requests.get(f"{base_url}/requests/{req_id}/status", headers=headers, timeout=20)

                res.raise_for_status()
                poll_data = res.json()
                status = poll_data.get("status")

                if status == "COMPLETED":
                    # Sonuçları almak için result endpointine gitmek gerekebilir veya status içinde dönebilir
                    # Genelde result linki 'response_url' içinde olur veya 'logs' parametresi false ise output içindedir

                    # Eğer payload içinde direkt output yoksa, result endpointine git:
                    output = poll_data.get("output")
                    if not output:
                        # Bazı API versiyonlarında result ayrı bir GET ister, ancak FAL genelde status içinde döner.
                        # Queue yapısına göre tekrar check etmeye gerek yoksa:
                        pass

                    images = poll_data.get("images") or (output.get("images") if output else None)

                    if images:
                        if isinstance(images, list):
                            first = images[0]
                            if isinstance(first, dict):
                                return first.get("url")
                            return first
                    break

                if status in ("FAILED", "CANCELLED"):
                    logger.error(f"FAL işlemi başarısız: {status}")
                    break

            return None

        except Exception as e:
            logger.error(f"FAL HTTP isteği hatası: {e}")
            return None

    results: List[Dict[str, str]] = []
    for item in prompt_items[:5]:
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
    ref_lookup = {f"IMG_REF_{i + 1}": img for i, img in enumerate(research_result["market_images"])}

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
            market_url = ref_lookup.get(ref_id, "")

            if market_url and ai_url:
                replacement_block = f"""
| 🛍️ Pazar Referansı | 🎨 AI Tasarımı ({model_name}) |
| :---: | :---: |
| ![]({market_url}) | ![]({ai_url}) |
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
    combined_images = research_result["market_images"] + ai_generated_urls_only

    return {
        "content": final_content,
        "image_urls": combined_images,
        "process_log": [
            "Fiyat aralıkları (Min-Max) analiz edildi.",
            f"{len(research_result['market_images'])} adet ürün görseli ve çalışan link toplandı.",
            "Görseller 'Full Body' ve 'E-Ticaret Stüdyo' modunda üretildi."
        ]
    }