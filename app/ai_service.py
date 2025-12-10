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
            openai_client = OpenAI(api_key=settings.openai_api_key, timeout=25.0)
            logger.info("✅ OpenAI Hazır")
        if settings.tavily_api_key:
            tavily_client = TavilyClient(api_key=settings.tavily_api_key)
            logger.info("✅ Tavily Hazır")
    except Exception as e:
        logger.error(f"❌ Başlatma Hatası: {e}")


initialize_ai_clients()


# Yardımcı: HTTP olmayan markdown image'larını temizle
def _remove_non_http_images(markdown_text: str) -> str:
    if not markdown_text: return ""
    pattern = r'!\[[^\]]*\]\((?!https?://)[^)]+\)'
    return re.sub(pattern, '', markdown_text)


# [MEVCUT] Görsel Kalite Filtresi (String Bazlı)
def is_quality_fashion_image(url: str) -> bool:
    if not url: return False
    url_lower = url.lower()

    valid_extensions = ('.jpg', '.jpeg', '.png', '.webp')
    has_valid_ext = any(ext in url_lower for ext in valid_extensions)

    if '.svg' in url_lower or '.gif' in url_lower:
        return False

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
    if not image_urls or not openai_client:
        return image_urls

    safe_candidates = []
    risky_domains = ['instagram.com', 'facebook.com', 'cdn.instagram', 'fbcdn.net', 'tiktok.com', 'pinterest']
    for url in image_urls:
        if not any(d in url.lower() for d in risky_domains):
            safe_candidates.append(url)

    candidates = safe_candidates[:8]
    if not candidates:
        return image_urls[:8]

    logger.info(f"👁️ Vision API ile {len(candidates)} görsel taranıyor...")

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
            return candidates

        if not isinstance(indices, list):
            return candidates

        verified_urls = [candidates[i] for i in indices if isinstance(i, int) and 0 <= i < len(candidates)]
        logger.info(f"✅ Vision Onaylı Görseller: {len(verified_urls)}/{len(candidates)}")
        return verified_urls

    except Exception as e:
        logger.error(f"Vision filtre hatası: {e}. Ham liste dönülüyor.")
        return candidates


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
# [GÜNCELLENDİ] GLOBAL DEFİLE VE PODYUM ANALİZİ (RUNWAY AGENT + GÖRSEL)
# -----------------------------------------------------------------------------

def analyze_runway_trends(topic: str) -> Dict[str, Any]:
    """
    Kullanıcının konusuyla ilgili son moda haftalarını tarar.
    [YENİ] Artık defile görsellerini de arar.
    """
    if not tavily_client:
        return {"context": "Defile verisi çekilemedi (Tavily yok).", "runway_images": []}

    logger.info(f"👠 Podyum ve Defile Analizi Başlıyor (Görseller dahil): {topic}")

    # Defilelere odaklanmış özel sorgular (2025/2026)
    runway_queries = [
        f"latest runway looks {topic} Spring/Summer 2026 Paris Milan",
        f"Haute Couture 2025 {topic} designs runway photos",
        f"best {topic} runway moments Fall/Winter 2025 2026 Vogue",
        f"designer {topic} trends 2026 fashion show images"
    ]

    runway_context = "### GLOBAL RUNWAY & FASHION WEEK DATA ###\n"
    runway_image_pool = []

    try:
        for q in runway_queries:
            try:
                response = tavily_client.search(
                    query=q,
                    search_depth="advanced",
                    include_images=True,  # [YENİ] Görsel aramayı açtık
                    max_results=3
                )

                # Metin içerikleri
                results = response.get('results', [])
                for res in results:
                    title = res.get('title', '')
                    content = res.get('content', '')
                    url = res.get('url', '')

                    if len(content) > 50:
                        runway_context += f"KAYNAK: {title}\nURL: {url}\nİÇERİK ÖZETİ: {content[:600]}\n\n"

                # Görsel içerikleri
                images = response.get('images', [])
                for img_url in images:
                    if img_url and img_url.startswith('http'):
                        runway_image_pool.append(img_url)

            except Exception as inner_e:
                logger.warning(f"Tavily Defile Sorgu Hatası ({q}): {inner_e}")
                continue

        # Defile görselleri için hızlı bir string filtresi uygulayalım (Logoları vs. elemek için)
        filtered_runway_images = [
            img for img in runway_image_pool
            if is_quality_fashion_image(img)
        ]
        # İlk 5 tanesini alalım
        final_runway_images = list(set(filtered_runway_images))[:5]
        logger.info(f"✅ Bulunan Defile Görseli Sayısı: {len(final_runway_images)}")

        return {"context": runway_context, "runway_images": final_runway_images}

    except Exception as e:
        logger.error(f"Defile Analiz Hatası: {e}")
        return {"context": f"Defile verisi alınırken hata oluştu: {e}", "runway_images": []}


# -----------------------------------------------------------------------------
# 3. DERİN PAZAR ARAŞTIRMASI (ARAŞTIRMA MODU)
# -----------------------------------------------------------------------------

def deep_market_research(topic: str) -> Dict[str, Any]:
    if not tavily_client:
        return {"context": "Hata: Tavily Client yok.", "market_images": []}

    logger.info(f"🔍 Derin Pazar ve Ürün Analizi: {topic}")

    queries = [
        # A. TREND VE RENK
        f"{topic} 2025/2026 fashion color palette trends pantone wgsn",
        # B. TÜKETİCİ PSİKOLOJİSİ
        f"why is {topic} trending 2025 consumer psychology buying behavior",
        # C. TİCARİ ÜRÜN ARAMASI
        f"{topic} ürün detayı satın al trendyol -logo -icon",
        f"{topic} abiye elbise satın al modanisa fiyat -logo -icon",
        f"{topic} modelleri ve fiyatları hepsiburada -logo -icon",
        # D. LÜKS VE İMALAT
        f"{topic} luxury design price vakko beymen product photography",
        f"{topic} best selling products 2025 fashion e-commerce",
        f"top rated {topic} designs zara mango h&m best sellers",
        f"{topic} en çok satan modeller trendyol çok değerlendirilenler",
        f"{topic} best sellers product photography -logo -icon"
    ]

    context_data = "### MARKET DATA & PRODUCT LINKS ###\n"
    raw_image_pool = []
    market_images_result = []

    try:
        all_results = []
        image_to_page_map = {}

        for q in queries:
            # Retry mekanizması ile tutarlılık
            max_retries = getattr(settings, 'tavily_max_retries', 2)
            query_success = False
            
            for attempt in range(max_retries + 1):
                try:
                    # Tavily'in yerleşik özelliklerini kullan
                    search_params = {
                        "query": q,
                        "search_depth": "advanced",
                        "include_images": True,
                        "max_results": 4,
                        "include_answer": getattr(settings, 'tavily_include_answer', True),  # Tavily'in özet cevabı
                    }
                    
                    # Domain filtresi (eğer ayarlanmışsa)
                    allowed_domains = getattr(settings, 'tavily_domains_list', [])
                    if allowed_domains:
                        search_params["include_domains"] = allowed_domains
                        logger.info(f"🔒 Domain filtresi aktif: {len(allowed_domains)} site ({', '.join(allowed_domains[:3])}...)")
                    
                    # Ham içerik (opsiyonel, daha fazla veri için)
                    if getattr(settings, 'tavily_include_raw_content', False):
                        search_params["include_raw_content"] = True
                    
                    response = tavily_client.search(**search_params)
                    
                    # Tavily'in özet cevabını kullan (tutarlılık için)
                    answer = response.get('answer', '')
                    if answer:
                        context_data += f"### TAVILY ÖZET: {q} ###\n{answer}\n\n"
                    
                    query_results = response.get('results', [])
                    
                    # Score filtresi - Tavily'in yerleşik score'una göre filtrele
                    min_score = getattr(settings, 'tavily_min_score', 0.75)
                    guvenilir_sonuclar = [
                        res for res in query_results 
                        if res.get('score', 0.0) > min_score
                    ]
                    
                    # Eğer yeterli sonuç yoksa, eşiği düşür
                    if len(guvenilir_sonuclar) < 2:
                        guvenilir_sonuclar = [
                            res for res in query_results 
                            if res.get('score', 0.0) > 0.5
                        ]
                        logger.info(f"📊 Tavily score filtresi (düşük eşik): {len(guvenilir_sonuclar)}/{len(query_results)} sonuç güvenilir (score > 0.5)")
                    else:
                        logger.info(f"📊 Tavily score filtresi: {len(guvenilir_sonuclar)}/{len(query_results)} sonuç güvenilir (score > {min_score})")
                    
                    # Score'a göre sırala (yüksekten düşüğe)
                    guvenilir_sonuclar.sort(key=lambda x: x.get('score', 0.0), reverse=True)
                    all_results.extend(guvenilir_sonuclar)
                    
                    # Sayfa URL'lerini topla
                    page_urls = [res.get('url', '') for res in guvenilir_sonuclar if res.get('url', '').startswith('http')]
                    
                    # Görselleri topla
                    raw_imgs = response.get('images', [])
                    for img_url in raw_imgs:
                        if img_url and img_url.startswith("http"):
                            raw_image_pool.append(img_url)
                            if img_url not in image_to_page_map and page_urls:
                                image_to_page_map[img_url] = page_urls[0]
                    
                    query_success = True
                    break  # Başarılı, retry döngüsünden çık
                    
                except Exception as inner_e:
                    if attempt < max_retries:
                        logger.warning(f"Tavily sorgu hatası (deneme {attempt + 1}/{max_retries + 1}): {inner_e}")
                        time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    else:
                        logger.error(f"Tavily sorgu hatası ({q}): {inner_e} - Tüm denemeler başarısız")
                        continue
            
            if not query_success:
                logger.warning(f"⚠️ Sorgu başarısız, atlanıyor: {q}")

        # --- GÖRSEL FİLTRELEME İŞLEMİ ---
        candidates_level_1 = [
            img for img in raw_image_pool
            if img and img.startswith("http") and is_quality_fashion_image(img)
        ]
        unique_candidates = list(set(candidates_level_1))

        # Vision Filtresi
        logger.info(f"👁️ Vision API ile {len(unique_candidates)} görsel doğrulanıyor...")
        final_market_images = validate_images_with_vision(unique_candidates)
        logger.info(f"✅ Vision API doğrulaması tamamlandı: {len(final_market_images)} görsel onaylandı")

        # Tavily'den gelen eşleştirmeyi kullan
        market_images_result = []
        for img_url in final_market_images:
            source_page = image_to_page_map.get(img_url, img_url)
            market_images_result.append({
                'img': img_url,
                'page': source_page
            })

        # Score'a göre tüm sonuçları tekrar sırala (tutarlılık için)
        all_results.sort(key=lambda x: x.get('score', 0.0), reverse=True)
        
        # Duplicate removal - URL bazlı (tutarlılık için)
        seen_urls = set()
        unique_results = []
        for res in all_results:
            url = res.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(res)
        
        logger.info(f"🔄 Duplicate removal: {len(all_results)} -> {len(unique_results)} sonuç")
        all_results = unique_results

        # Metin Verilerini İşle (Score bilgisi ile)
        for i, res in enumerate(all_results):
            url = res.get('url', '')
            if not url.startswith('http'): continue

            score = res.get('score', 0.0)
            score_emoji = "🟢" if score >= 0.75 else "🟡" if score >= 0.5 else "🔴"

            context_data += f"--- SONUÇ ID: {i + 1} ---\n"
            context_data += f"BAŞLIK: {res.get('title', 'Başlıksız')}\n"
            context_data += f"İÇERİK: {res.get('content', '')}\n"
            context_data += f"TAM_URL: {url}\n"
            context_data += f"TAVILY_SCORE: {score:.2f} {score_emoji}\n\n"

        context_data += "### PAZAR GÖRSEL HAVUZU (DOĞRULANMIŞ) ###\n"
        limited_images = market_images_result[:12]

        for i, img_data in enumerate(limited_images):
            img_url = img_data['img'] if isinstance(img_data, dict) else img_data
            context_data += f"IMG_REF_{i + 1}: {img_url}\n"

        return {"context": context_data, "market_images": limited_images}

    except Exception as e:
        logger.error(f"Araştırma Hatası: {e}")
        return {"context": f"Kısmi veri (Hata: {e})\n{context_data}", "market_images": market_images_result}


# -----------------------------------------------------------------------------
# 4. STRATEJİK İMALAT RAPORU (LİNK KORUMALI & DEFİLE GÖRSELLİ)
# -----------------------------------------------------------------------------

def generate_strategic_report(user_message: str, research_data: str) -> str:
    if not openai_client: return "OpenAI Client başlatılamadı."

    # [GÜNCELLENDİ] System Prompt: Defile Görsel Yer Tutucuları Eklendi
    system_prompt = """
    Sen Kıdemli Moda Stratejistisin.

    GÖREVİN:
    Üreticiye hem **SOKAK MODASI (PAZAR)** hem de **YÜKSEK MODA (DEFİLE)** verilerini birleştirerek vizyoner bir rapor sunmak.

    VERİ KAYNAKLARI:
    1. MARKET DATA: E-ticaret siteleri ve halkın satın aldığı ürünler.
    2. RUNWAY DATA: Paris, Milano gibi moda haftalarından tasarımcı notları.

    ⚠️ 1. LİNK KURALI (HAYATİ ÖNEMLİ):
    - Bölüm 5'te (Rakip Ürünler) 'MARKET DATA' içindeki 'TAM_URL:' etiketli linki BOZMADAN kullan.

    ⚠️ 2. GÖRSEL YERLEŞİM KURALI:
    - Bölüm 1'de (GLOBAL DEFİLE İZLERİ) eğer podyumdan bahsettiysen altına [[RUNWAY_VISUAL_1]] [[RUNWAY_VISUAL_2]] gibi yer tutucular koy.
    - Bölüm 4'te (TOP 5 TİCARİ MODEL) her modelin altına [[VISUAL_CARD_X]] yer tutucusunu koy.

    RAPOR FORMATI (Markdown):

    # 💎 [KONU] - 2026 VİZYON VE ÜRETİM RAPORU

    ## 🌍 BÖLÜM 1: GLOBAL DEFİLE İZLERİ (HIGH FASHION)
    *Bu bölümde 'RUNWAY DATA' verilerini kullan. Hangi markanın hangi defilesinde benzer ürünler görüldü?*
    * **Öne Çıkan Defileler:** (Örn: Elie Saab 2025 SS, Gucci Resort vb. isim vererek yaz)
    * **Podyumdan Notlar:** (Defilelerdeki kumaş, kesim ve artistik detaylar)
    * **Vizyon:** (Bu podyum trendi sokağa nasıl inecek?)

    [[RUNWAY_VISUAL_1]] [[RUNWAY_VISUAL_2]] [[RUNWAY_VISUAL_3]]

    ## 📈 BÖLÜM 2: TİCARİ TREND VE TÜKETİCİ ANALİZİ
    * **Popüler Kültür & Sokak:** (Diziler, TikTok akımları)
    * **Trend Renk Paleti:** (Pantone/WGSN kodları)
    * **Kumaş Tercihleri:** (Saten, şifon, krep vb.)

    ## 💰 BÖLÜM 3: SEGMENT VE FİYAT ANALİZİ
    (Tablo Buraya Gelecek - Min/Max/Ortalama Fiyatlar)

    ## 🏆 BÖLÜM 4: ÜRETİLECEK TOP 5 TİCARİ MODEL
    *Ticari başarı potansiyeli yüksek, podyumdan esinlenilmiş ama satılabilir modeller.*
    ### 1. [Model Adı]
    * **Kumaş:** ...
    * **Detay:** ...
    [[VISUAL_CARD_1]]

    ### 2. [Model Adı]
    ...
    [[VISUAL_CARD_2]]

    ... (5'e kadar devam et)

    ## 🛍️ BÖLÜM 5: SAHADA SATILAN RAKİP ÜRÜNLER (CANLI VİTRİN)
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
# 5. GÖRSEL PROMPT (E-TİCARET ODAKLI)
# -----------------------------------------------------------------------------

def generate_image_prompts(analysis_text: str) -> List[Dict[str, str]]:
    system_prompt = """
    You are an AI Fashion Photographer & Prompt Engineer.

    TASK: Extract up to 5 model concepts from the report.
    For each concept, create a highly detailed image prompt optimized for FLUX GENERATION.

    PROMPT RULES (STRICT E-COMMERCE STANDARDS):
    1.  **START WITH:** "Wide-angle full body e-commerce studio shot of..." (Must enforce full body).
    2.  **FRAMING:** "Zoomed out", "Head to toe visibility", "Model standing", "Shoes visible", "No cropping".
    3.  **LIGHTING:** "High-key soft studio lighting", "Bright and evenly lit", "No harsh shadows", "Commercial look".
    4.  **BACKGROUND:** "Clean neutral studio background" or "Solid white background".

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


def extract_visual_style(user_text: str) -> str:
    if not openai_client: return ""

    system_msg = """
    You are a 'Visual Style Extractor'.
    Analyze the user's fashion request and extract the CORE VISUAL CONSTRAINTS.
    Convert these into comma-separated English keywords.
    RETURN ONLY THE ENGLISH KEYWORDS.
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_text}],
            temperature=0.0,
            max_tokens=60
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return ""


def generate_ai_images(prompt_items: List[Dict[str, str]]) -> List[Dict[str, str]]:
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

    headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}

    def _run_prompt(prompt: str) -> Optional[str]:
        fal_args = {
            "prompt": prompt,
            "image_size": "portrait_4_3",
            "num_inference_steps": 40,
            "guidance_scale": 3.5,
            "num_images": 1,
            "enable_safety_checker": False
        }

        if use_sdk:
            try:
                handler = fal_client.submit(model_path, arguments=fal_args)
                result = handler.get()
                images = result.get("images") or result.get("output", {}).get("images")
                if images:
                    first = images[0]
                    if isinstance(first, dict): return first.get("url")
                    return first
            except Exception as e:
                logger.error(f"FAL SDK hata: {e}. HTTP fallback deneniyor.")

        try:
            run_resp = requests.post(run_url, headers=headers, json=fal_args, timeout=30)
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
            if not req_id: return None

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
                        if isinstance(images, list):
                            first = images[0]
                            if isinstance(first, dict): return first.get("url")
                            return first
                    break
                if status in ("FAILED", "CANCELLED"): break

            return None
        except Exception as e:
            logger.error(f"FAL HTTP isteği hatası: {e}")
            return None

    results: List[Dict[str, str]] = []
    for item in prompt_items[:5]:
        prompt = item.get("prompt")
        if not prompt: continue
        url = _run_prompt(prompt)
        if url:
            results.append({
                "model_name": item.get("model_name", "").strip(),
                "ref_id": item.get("ref_id", "").strip(),
                "url": url
            })

    return results


# -----------------------------------------------------------------------------
# 6. ANA ORKESTRASYON (GÜNCELLENDİ: PARALEL ARAŞTIRMA + DEFİLE GÖRSELLERİ)
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

    # ADIM 2: Paralel Araştırma (Hem Pazar Hem Defile)
    future_market = loop.run_in_executor(None, deep_market_research, user_message)
    future_runway = loop.run_in_executor(None, analyze_runway_trends, user_message)

    # İkisinin de bitmesini bekle. runway_result artık bir sözlük (dict).
    market_result, runway_result = await asyncio.gather(future_market, future_runway)

    # Verileri Birleştir (Sözlükten context ve görselleri al)
    runway_context_text = runway_result.get("context", "")
    runway_images_list = runway_result.get("runway_images", [])

    full_research_context = (
        f"{runway_context_text}\n"
        f"{'=' * 30}\n"
        f"{market_result['context']}"
    )

    # ADIM 3: Raporlama (Birleşmiş veri ile)
    final_report = await loop.run_in_executor(None, generate_strategic_report, user_message, full_research_context)

    # ADIM 4: Görsel Üretimi (Opsiyonel AI Görselleri)
    market_images_data = market_result["market_images"]
    ref_lookup = {}
    for i, img_data in enumerate(market_images_data):
        ref_key = f"IMG_REF_{i + 1}"
        if isinstance(img_data, dict):
            ref_lookup[ref_key] = img_data['img']
        else:
            ref_lookup[ref_key] = img_data

    ai_generated_items: List[Dict[str, str]] = []
    image_triggers = ["çiz", "görsel", "tasarım", "resim", "resimler", "foto", "fotoğraf", "image", "picture", "draw"]
    should_generate_images = True if settings.fal_api_key else (
            generate_images or any(x in user_message.lower() for x in image_triggers))
    ref_ids_ordered = list(ref_lookup.keys())

    if should_generate_images:
        # ... (AI görsel üretim kodları aynı) ...
        prompt_items = await loop.run_in_executor(None, generate_image_prompts, final_report)
        logger.info(f"Görsel prompt sayısı: {len(prompt_items)}")

        if not prompt_items:
            prompt_items = [{
                "model_name": (user_message[:50] or "AI Model").strip(),
                "ref_id": ref_ids_ordered[0] if ref_lookup else "",
                "prompt": f"Fashion photography of {user_message}"
            }]

        dynamic_style_context = await loop.run_in_executor(None, extract_visual_style, user_message)

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
    else:
        logger.info("Görsel üretimi atlandı.")

    # -------------------------------------------------------------------------
    # ADIM 5: GÖRSEL ENTEGRASYONU (Pazar + AI + [YENİ] Defile)
    # -------------------------------------------------------------------------
    final_content = final_report

    # [YENİ] A. Defile Görsellerini Yerleştir (Bölüm 1'e)
    # Rapordaki [[RUNWAY_VISUAL_1]] gibi yer tutucuları gerçek görsellerle değiştir.
    for i in range(1, 4):  # En fazla 3 görsel yerleştir
        placeholder = f"[[RUNWAY_VISUAL_{i}]]"
        if i <= len(runway_images_list):
            # Defile görselini basit bir markdown resim olarak ekle
            img_md = f"![Podyum Görseli {i}]({runway_images_list[i - 1]})"
            final_content = final_content.replace(placeholder, img_md)
        else:
            # Görsel yoksa yer tutucuyu temizle
            final_content = final_content.replace(placeholder, "")

    # B. Ticari Modelleri Yerleştir (Bölüm 4'e) - Mevcut mantık
    for i in range(1, 6):
        placeholder = f"[[VISUAL_CARD_{i}]]"
        ai_item = None
        if i <= len(ai_generated_items):
            ai_item = ai_generated_items[i - 1]

        replacement_block = ""
        if ai_item:
            # ... (AI görsel kartı oluşturma mantığı aynı) ...
            ai_url = ai_item.get("url")
            ref_id = ai_item.get("ref_id")
            model_name = ai_item.get("model_name", "Model")
            market_img_url = ref_lookup.get(ref_id, "")

            market_page_url = ""
            if market_img_url:
                for img_data in market_images_data:
                    img_url = img_data['img'] if isinstance(img_data, dict) else img_data
                    if img_url == market_img_url:
                        if isinstance(img_data, dict):
                            market_page_url = img_data.get('page', market_img_url)
                        else:
                            market_page_url = market_img_url
                        break
                if not market_page_url:
                    market_page_url = market_img_url

            if market_img_url and ai_url:
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

    # Temizlik
    final_content = re.sub(r'\[\[VISUAL_CARD_\d+\]\]', '', final_content)
    final_content = re.sub(r'\[\[RUNWAY_VISUAL_\d+\]\]', '', final_content)  # Kalan defile tutucularını da temizle
    final_content = _remove_non_http_images(final_content)

    # Tüm Görsel URL'lerini Topla (Frontend için)
    ai_generated_urls_only = [m["url"] for m in ai_generated_items if m.get("url")]
    market_img_urls_only = [
        img_data['img'] if isinstance(img_data, dict) else img_data
        for img_data in market_result["market_images"]
    ]
    # [YENİ] Defile görsellerini de ana havuza ekle
    combined_images = market_img_urls_only + ai_generated_urls_only + runway_images_list

    # Link Haritası Oluştur
    image_links = {}
    # Pazar linkleri
    for img_data in market_result["market_images"]:
        if isinstance(img_data, dict):
            img_url = img_data.get('img')
            page_url = img_data.get('page')
            if img_url and page_url and img_url != page_url:
                image_links[img_url] = page_url
    # AI linkleri (yok)
    for ai_item in ai_generated_items:
        ai_url = ai_item.get("url")
        if ai_url:
            image_links[ai_url] = None
    # [YENİ] Defile linkleri (şimdilik yok, sadece görsel)
    for r_img in runway_images_list:
        image_links[r_img] = None

    return {
        "content": final_content,
        "image_urls": combined_images,
        "image_links": image_links,
        "process_log": [
            "Pazar ve Defile verileri (Görseller dahil) paralel analiz edildi.",
            f"{len(market_result['market_images'])} adet pazar referansı bulundu.",
            f"{len(runway_images_list)} adet podyum görseli rapora eklendi.",
            "Ticari başarı odaklı AI modelleri oluşturuldu."
        ]
    }