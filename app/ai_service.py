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

try:
    import fal_client  # type: ignore
except Exception:
    fal_client = None

# Logger
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
            openai_client = OpenAI(api_key=settings.openai_api_key)
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
    pattern = r'!\[[^\]]*\]\((?!https?://)[^)]+\)'
    return re.sub(pattern, '', markdown_text)


# [MEVCUT] Görsel Kalite Filtresi (String Bazlı)
def is_quality_fashion_image(url: str) -> bool:
    """
    Tavily'den gelen URL'in bir logo, ikon veya gereksiz grafik olup olmadığını kontrol eder.
    Sadece potansiyel ürün fotoğraflarına izin verir.
    """
    if not url: return False
    url_lower = url.lower()

    # 1. Uzantı Kontrolü (Sadece statik resimler)
    valid_extensions = ('.jpg', '.jpeg', '.png', '.webp')
    if not any(url_lower.endswith(ext) for ext in valid_extensions):
        if '.svg' in url_lower or '.gif' in url_lower:
            return False

    # 2. Yasaklı Kelimeler (Logolar, ikonlar, arayüz elemanları)
    banned_keywords = [
        'logo', 'icon', 'avatar', 'user', 'profile', 'banner',
        'button', 'sprite', 'svg', 'loader', 'gif', 'promo',
        'footer', 'header', 'favicon', 'thumbnail', 'pixel',
        'sprite', 'blank', 'transparent', 'chart', 'size'
    ]

    if any(keyword in url_lower for keyword in banned_keywords):
        return False

    return True


# [MEVCUT] GPT-4o Vision ile Akıllı Görsel Doğrulama
def validate_images_with_vision(image_urls: List[str]) -> List[str]:
    """
    GPT-4o Vision kullanarak resimlerin gerçekten moda/ürün fotoğrafı olup olmadığını kontrol eder.
    Bütçeyi korumak için sadece en iyi 8 adayı kontrol eder.
    """
    if not image_urls or not openai_client:
        return image_urls

    # Maliyet optimizasyonu: Sadece ilk 8 görseli kontrol et
    candidates = image_urls[:8]
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
        indices = json.loads(clean_text)

        if not isinstance(indices, list):
            return candidates

        # Seçilen indeksleri URL'e çevir
        verified_urls = [candidates[i] for i in indices if isinstance(i, int) and 0 <= i < len(candidates)]
        logger.info(f"✅ Vision Onaylı Görseller: {len(verified_urls)}/{len(candidates)}")

        return verified_urls

    except Exception as e:
        logger.error(f"Vision filtre hatası: {e}. Filtre devre dışı bırakılıyor, ham liste dönülüyor.")
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
            temperature=0.0
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
        return "Üzgünüm, şu an yanıt veremiyorum."


# -----------------------------------------------------------------------------
# 3. DERİN PAZAR ARAŞTIRMASI (ARAŞTIRMA MODU - GÜNCELLENDİ)
# -----------------------------------------------------------------------------

def deep_market_research(topic: str) -> Dict[str, Any]:
    """
    Linkleri bozmadan toplamak için optimize edildi.
    Görsel filtreleme eklendi (String + Vision).
    [GÜNCELLENDİ] Renk ve Psikoloji verileri için özel sorgular eklendi.
    """
    if not tavily_client:
        return {"context": "Hata: Tavily Client yok.", "market_images": []}

    logger.info(f"🔍 Derin Pazar ve Ürün Analizi: {topic}")

    # [GÜNCELLENDİ] Sorgular artık Renk, Trend ve Psikolojiyi de kapsıyor
    queries = [
        # A. TREND VE RENK (Pantone, WGSN vb.)
        f"{topic} 2025/2026 fashion color palette trends pantone wgsn",

        # B. TÜKETİCİ PSİKOLOJİSİ
        f"why is {topic} trending 2025 consumer psychology buying behavior",

        # C. TİCARİ ÜRÜN ARAMASI (Direkt Ürün Sayfalarını Hedefle)
        f"{topic} ürün detayı satın al trendyol -logo -icon",
        f"{topic} abiye elbise satın al modanisa fiyat -logo -icon",
        f"{topic} modelleri ve fiyatları hepsiburada -logo -icon",

        # D. LÜKS VE İMALAT
        f"{topic} luxury design price vakko beymen product photography",
    ]

    context_data = "### MARKET DATA & PRODUCT LINKS ###\n"
    raw_image_pool = []

    try:
        all_results = []
        for q in queries:
            response = tavily_client.search(
                query=q,
                search_depth="advanced",
                include_images=True,
                max_results=4
            )
            all_results.extend(response.get('results', []))

            # Ham görselleri havuza ekle
            raw_imgs = response.get('images', [])
            raw_image_pool.extend(raw_imgs)

        # --- GÖRSEL FİLTRELEME İŞLEMİ (YENİ) ---

        # 1. Adım: String Filtresi (Hızlı Eleme)
        candidates_level_1 = [
            img for img in raw_image_pool
            if img and img.startswith("http") and is_quality_fashion_image(img)
        ]

        # Unique yap (Tekrarları temizle)
        unique_candidates = list(set(candidates_level_1))

        # 2. Adım: Vision Filtresi (Akıllı Eleme)
        final_market_images = validate_images_with_vision(unique_candidates)

        # ---------------------------------------

        # Metin Verilerini İşle (Linkleri ID ile etiketle)
        for i, res in enumerate(all_results):
            # Sadece geçerli HTTP linklerini alıyoruz
            url = res.get('url', '')
            if not url.startswith('http'): continue

            context_data += f"--- SONUÇ ID: {i + 1} ---\n"
            context_data += f"BAŞLIK: {res['title']}\n"
            context_data += f"İÇERİK: {res['content']}\n"
            context_data += f"TAM_URL: {url}\n\n"  # "TAM_URL" etiketiyle LLM'e işaret ediyoruz

        context_data += "### PAZAR GÖRSEL HAVUZU (DOĞRULANMIŞ) ###\n"
        # En fazla 12 görseli context'e ekle
        limited_images = final_market_images[:12]

        for i, img in enumerate(limited_images):
            context_data += f"IMG_REF_{i + 1}: {img}\n"

        return {"context": context_data, "market_images": limited_images}

    except Exception as e:
        logger.error(f"Araştırma Hatası: {e}")
        return {"context": f"Hata: {e}", "market_images": []}


# -----------------------------------------------------------------------------
# 4. STRATEJİK İMALAT RAPORU (LİNK KORUMALI)
# -----------------------------------------------------------------------------

def generate_strategic_report(user_message: str, research_data: str) -> str:
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
        return f"Rapor Hatası: {e}"


# -----------------------------------------------------------------------------
# 5. GÖRSEL PROMPT (GÜNCELLENDİ - BOYDAN & E-TİCARET)
# -----------------------------------------------------------------------------
def generate_image_prompts(analysis_text: str) -> List[Dict[str, str]]:
    """
    Rapor içindeki model isimlerini yakalar ve E-TİCARET'e uygun,
    stüdyo ışıklı, boydan (full body) promptlar üretir.
    """
    # [GÜNCELLENDİ] Prompt Mühendisliği: Boydan, E-Ticaret ve Stüdyo Işığı Zorunluluğu
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
        data = json.loads(response.choices[0].message.content)
        return data.get("items", [])
    except Exception as e:
        logger.error(f"Görsel prompt çıkarma hatası: {e}")
        return []


# [MEVCUT] Stil Bağlamı Çıkarıcı
def extract_visual_style(user_text: str) -> str:
    """
    Kullanıcının mesajındaki genel stil ve görünüm kurallarını İngilizce prompt'a çevirir.
    Örn: "Tesettürlü siyah abiye" -> "model wearing hijab, modest fashion, long sleeves, full coverage, elegant"
    Örn: "Plaj için bikini" -> "beachwear, summer vibe, swimwear"
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
    [GÜNCELLENDİ] 1080p Dikey + Yüksek Adım Sayısı (Inference Steps)
    """
    api_key = settings.fal_api_key
    if not api_key:
        logger.info("❕ FAL_API_KEY yok, görsel üretimi atlanıyor.")
        return []

    base_url = getattr(settings, "fal_base_url", "https://fal.run").rstrip("/")
    model_path = getattr(settings, "fal_model_path", "fal-ai/flux/dev").strip("/")
    run_url = f"{base_url}/{model_path}"
    poll_url = f"{base_url}/{model_path}"  # request_id eklenecek

    # fal_client varsa resmi SDK ile kullan, yoksa HTTP fallback
    use_sdk = fal_client is not None
    if use_sdk:
        os.environ["FAL_KEY"] = api_key

    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }

    def _run_prompt(prompt: str) -> Optional[str]:
        # [YENİ AYARLAR] Kaliteyi artırmak için parametre optimizasyonu
        fal_args = {
            "prompt": prompt,
            "image_size": "portrait_4_3",  # Yüksek çözünürlüklü dikey (Boydan foto için ideal)
            "num_inference_steps": 40,  # [ÖNEMLİ] Adım sayısı arttı (Daha fazla detay)
            "guidance_scale": 3.5,  # [ÖNEMLİ] Prompt sadakati arttı
            "num_images": 1,
            "enable_safety_checker": False
        }

        # Önce SDK dene, hata olursa HTTP fallback
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
                    if isinstance(first, dict):
                        return first.get("url")
                    return first
            except Exception as e:
                logger.error(f"FAL SDK hata: {e}. HTTP fallback deneniyor. prompt='{prompt[:80]}'")

        try:
            run_resp = requests.post(
                run_url,
                headers=headers,
                json=fal_args,  # Aynı argümanları HTTP için de kullanıyoruz
                timeout=30,
            )
            run_resp.raise_for_status()
            data = run_resp.json()

            # Bazı modeller direkt images döndürüyor (request_id olmadan)
            direct_images = data.get("images") or data.get("output", {}).get("images")
            if direct_images:
                first = direct_images[0]
                if isinstance(first, dict):
                    url = first.get("url")
                    if url:
                        return url
                elif isinstance(first, str):
                    return first

            req_id = data.get("request_id")
            if not req_id:
                logger.error(f"FAL run yanıtında request_id yok. Yanıt: {run_resp.text[:200]}")
                return None

            # Poll result
            for _ in range(15):  # ~30s max (2s * 15)
                time.sleep(2)
                res = requests.get(f"{poll_url}/{req_id}", headers=headers, timeout=20)
                if res.status_code == 404:
                    logger.error("FAL poll 404 - endpoint veya model yolu hatalı.")
                    break
                res.raise_for_status()
                data = res.json()
                status = data.get("status")
                if status == "COMPLETED":
                    images = data.get("images") or data.get("output", {}).get("images")
                    if images:
                        # image can be dict with url or direct url list
                        if isinstance(images, list):
                            first = images[0]
                            if isinstance(first, dict):
                                return first.get("url")
                            return first
                    break
                if status in ("FAILED", "CANCELLED"):
                    break
            return None
        except Exception as e:
            logger.error(f"FAL görsel üretim hatası: {e}")
            return None

    results: List[Dict[str, str]] = []
    for item in prompt_items[:5]:  # en fazla 5 görsel
        prompt = item.get("prompt")
        if not prompt:
            continue
        logger.info(f"FAL görsel isteği: {prompt[:80]}...")
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

    # ADIM 3: Raporlama (Placeholder'lı formatta)
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

        # [MEVCUT] DİNAMİK STİL ENJEKSİYONU (Context Injection)
        dynamic_style_context = await loop.run_in_executor(None, extract_visual_style, user_message)
        logger.info(f"🎨 Çıkarılan Stil Bağlamı: {dynamic_style_context}")

        # [GÜNCELLENDİ] Master Prefix (Ön Ek - Zorunlu Boydan Çekim ve Uzak Mesafe)
        # Kamerayı uzaklaştırarak tüm vücudun kadraja girmesini garantiliyoruz.
        master_prefix = "Wide-angle full body shot, camera zoomed out, showing entire outfit from head to toe including shoes, "

        # [GÜNCELLENDİ] Master Style Şablonu (E-Ticaret Stüdyo Kalitesi)
        # "Cinematic" yerine "High-key studio lighting" ve "white background" eklendi.
        master_style_suffix = ", high-key soft studio lighting, shadowless white background, professional e-commerce catalog photography, 8k, sharp focus, hyper-realistic texture"

        # 3. Hepsini Birleştir: Prefix + Prompt + Dinamik Stil + Suffix
        normalized_prompts: List[Dict[str, str]] = []
        for idx, item in enumerate(prompt_items):
            ref_id = (item.get("ref_id") or (
                ref_ids_ordered[idx % len(ref_ids_ordered)] if ref_ids_ordered else "")).strip()

            raw_prompt = item.get("prompt", "").strip()

            # Dinamik stili ve boydan zorunluluğunu her prompta ekle
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