import os
import logging
import asyncio
import requests
import time
import uuid
import json
import re
import concurrent.futures
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
            # Vision işlemleri bazen uzun sürebilir, timeout artırıldı
            openai_client = OpenAI(api_key=settings.openai_api_key, timeout=45.0)
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
    pattern = r'!\[[^\]]*\]\((?!https?://|http://)[^)]+\)'
    return re.sub(pattern, '', markdown_text)


# [MEVCUT] Temel Görsel Kalite Filtresi (String Bazlı - Hızlı Eleme)
def is_quality_fashion_image(url: str) -> bool:
    if not url: return False
    url_lower = url.lower()

    # 1. Uzantı Kontrolü
    valid_extensions = ('.jpg', '.jpeg', '.png', '.webp')
    if not any(ext in url_lower for ext in valid_extensions):
        return False

    # SVG ve GIF kesinlikle yasak
    if '.svg' in url_lower or '.gif' in url_lower:
        return False

    # 2. Yasaklı Kelimeler
    banned_keywords = [
        'logo', 'icon', 'avatar', 'user', 'profile', 'banner',
        'button', 'sprite', 'svg', 'loader', 'gif', 'promo',
        'footer', 'header', 'favicon', 'thumbnail', 'pixel',
        'sprite', 'blank', 'transparent', 'chart', 'size',
        'overlay', 'track', 'adserver', 'placeholder', 'static',
        'loading', 'spinner'
    ]

    if any(keyword in url_lower for keyword in banned_keywords):
        return False

    return True


# [MEVCUT] SerpApi ile Görsel Doğrulama (Varlık Kontrolü)
def verify_image_with_serp(image_url: str) -> bool:
    if not settings.serp_api_key:
        return True

    try:
        params = {
            "engine": "google_reverse_image",
            "image_url": image_url,
            "api_key": settings.serp_api_key
        }
        response = requests.get("https://serpapi.com/search.json", params=params, timeout=5)

        if response.status_code == 200:
            return True
        elif response.status_code == 401:
            logger.warning("SerpApi yetkilendirme hatası (API Key geçersiz).")
            return True
        else:
            logger.warning(f"SerpApi görseli doğrulayamadı ({response.status_code}): {image_url}")
            return False

    except Exception as e:
        logger.warning(f"SerpApi bağlantı hatası: {e}")
        return True


# [MEVCUT] SerpApi ile Görsel Kaynak Sayfasını Bulma (Ürün Sayfası Odaklı)
def get_image_source_page_with_serp(image_url: str) -> Optional[str]:
    if not settings.serp_api_key:
        return None

    try:
        params = {
            "engine": "google_reverse_image",
            "image_url": image_url,
            "api_key": settings.serp_api_key
        }
        response = requests.get("https://serpapi.com/search.json", params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()

            product_indicators = [
                '/urun/', '/product/', '/item/', '/p/', '/pd/', '/products/',
                'urun-detay', 'product-detail', 'item-detail', 'product-page',
                'trendyol.com/butik', 'hepsiburada.com/urun', 'n11.com/urun',
                'gittigidiyor.com/urun', 'amazon.com/dp/', 'amazon.com.tr/dp/'
            ]

            category_indicators = [
                '/kategori/', '/category/', '/c/', '/collections/', '/collection/',
                '/butik/', '/brand/', '/marka/', '/store/', '/magaza/',
                '/anasayfa', '/home', '/index', '/main'
            ]

            def is_product_page(url: str) -> bool:
                url_lower = url.lower()
                has_category = any(ind in url_lower for ind in category_indicators)
                has_product = any(ind in url_lower for ind in product_indicators)
                if has_category and not has_product: return False
                return has_product or len(url.split('/')) > 5

            def score_url(url: str) -> int:
                url_lower = url.lower()
                score = 0
                if any(ind in url_lower for ind in product_indicators): score += 10
                if any(ind in url_lower for ind in category_indicators): score -= 5
                if len(url.split('/')) > 5: score += 3
                ecommerce_domains = ['trendyol.com', 'hepsiburada.com', 'n11.com', 'gittigidiyor.com', 'amazon.com',
                                     'zara.com', 'mango.com', 'hm.com', 'lcwaikiki.com']
                if any(domain in url_lower for domain in ecommerce_domains): score += 2
                return score

            candidate_urls = []
            inline_images = data.get('inline_images', [])
            for img_result in inline_images:
                url = img_result.get('link') or img_result.get('source') or img_result.get('url')
                if url and url.startswith('http'): candidate_urls.append(url)

            results = data.get('results', [])
            for result in results:
                url = result.get('link') or result.get('url')
                if url and url.startswith('http'): candidate_urls.append(url)

            visual_matches = data.get('visual_matches', [])
            for match in visual_matches:
                url = match.get('link') or match.get('url')
                if url and url.startswith('http'): candidate_urls.append(url)

            if not candidate_urls: return None

            scored_urls = [(url, score_url(url)) for url in candidate_urls]
            scored_urls.sort(key=lambda x: x[1], reverse=True)

            best_url, best_score = scored_urls[0]

            if is_product_page(best_url) or best_score >= 5:
                return best_url
            elif len(scored_urls) > 1:
                return scored_urls[1][0]

            return best_url

        elif response.status_code == 401:
            logger.warning("SerpApi yetkilendirme hatası (API Key geçersiz).")
            return None
        else:
            return None

    except Exception as e:
        logger.warning(f"SerpApi bağlantı hatası: {e}")
        return None


# [GÜNCELLENDİ] GPT-4o Vision ile Akıllı Görsel Doğrulama
def validate_images_with_vision(image_urls: List[str], filter_type: str = "market") -> List[str]:
    if not image_urls or not openai_client:
        return image_urls

    safe_candidates = []
    risky_domains = ['instagram.com', 'facebook.com', 'cdn.instagram', 'fbcdn.net', 'tiktok.com', 'pinterest',
                     'twimg.com']
    for url in image_urls:
        if not any(d in url.lower() for d in risky_domains) and len(url) < 1000:
            safe_candidates.append(url)

    # Maliyet optimizasyonu: Sadece en iyi 8 adayı kontrol et
    candidates = safe_candidates[:8]
    if not candidates:
        return image_urls[:8]

    logger.info(f"👁️ Vision API ({filter_type.upper()}) ile {len(candidates)} görsel taranıyor...")

    if filter_type == "runway":
        prompt_text = "Select indices of images that are ONLY professional RUNWAY/CATWALK photos. Exclude product shots, selfies, text. JSON list of ints only."
    else:
        prompt_text = "Select indices of images that are ONLY clear fashion PRODUCT photography (garments on models/mannequins). Exclude logos, banners. JSON list of ints only."

    messages_content = [{"type": "text", "text": prompt_text}]

    for url in candidates:
        messages_content.append({"type": "image_url", "image_url": {"url": url, "detail": "low"}})

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": messages_content}],
            max_tokens=100,
            temperature=0.0
        )

        result_text = response.choices[0].message.content.strip()
        clean_text = result_text.replace("```json", "").replace("```", "").strip()

        try:
            indices = json.loads(clean_text)
            if not isinstance(indices, list): return candidates
            verified_urls = [candidates[i] for i in indices if isinstance(i, int) and 0 <= i < len(candidates)]
            return verified_urls
        except json.JSONDecodeError:
            return candidates

    except Exception as e:
        logger.error(f"Vision filtre hatası: {e}. Filtre devre dışı bırakılıyor, ham liste dönülüyor.")
        return candidates[:4]


# -----------------------------------------------------------------------------
# 2. NİYET ANALİZİ VE SOHBET
# -----------------------------------------------------------------------------

def analyze_user_intent(message: str, chat_history: List[Dict[str, str]] = []) -> str:
    if not openai_client: return "MARKET_RESEARCH"

    recent_history = chat_history[-3:] if chat_history else []
    history_text = json.dumps(recent_history, ensure_ascii=False)

    system_prompt = f"""
    You are an intent classifier for a Fashion AI.
    HISTORY: {history_text}
    CURRENT USER MESSAGE: "{message}"

    CATEGORIES:
    1. MARKET_RESEARCH: User asks for a NEW topic analysis (e.g., "Abiye trendleri", "Spor ayakkabı modası").
    2. FOLLOW_UP: User refers to the previous topic/report OR asks about the results (e.g., "Why this price?", "Change color", "Draw this").
    3. GENERAL_CHAT: Greetings, "Who are you?", or general fashion knowledge.

    OUTPUT: Return ONLY one of the category names above.
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0.0,
            max_tokens=20
        )
        intent = response.choices[0].message.content.strip().upper()
        if "MARKET" in intent: return "MARKET_RESEARCH"
        if "FOLLOW" in intent: return "FOLLOW_UP"
        if "GENERAL" in intent: return "GENERAL_CHAT"
        return "MARKET_RESEARCH"
    except:
        return "MARKET_RESEARCH"


def handle_general_chat(message: str) -> str:
    system_prompt = "Sen Kıdemli Moda Stratejisisin. Kullanıcının sorularına profesyonel ve samimi cevap ver."
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": message}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception:
        return "Üzgünüm, şu an yanıt veremiyorum."


async def handle_follow_up(message: str, chat_history: List[Dict[str, str]]) -> str:
    if not openai_client: return "Sistem hatası."

    system_msg = """
    Sen Kıdemli Moda Stratejistisin.
    GÖREVİN: Sohbet geçmişindeki (History) rapor verilerine dayanarak kullanıcının sorusunu yanıtla.
    Yeni görsel istenirse onayla.
    """

    messages = [{"role": "system", "content": system_msg}]
    for msg in chat_history[-6:]:
        if msg.get("role") in ["user", "assistant"]:
            messages.append({"role": msg.get("role"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": message})

    try:
        response = openai_client.chat.completions.create(model="gpt-4o", messages=messages, temperature=0.7)
        return response.choices[0].message.content
    except Exception as e:
        return f"Cevap üretilemedi: {e}"


# -----------------------------------------------------------------------------
# 3. VERİ TOPLAMA AJANLARI
# -----------------------------------------------------------------------------

def analyze_runway_trends(topic: str) -> Dict[str, Any]:
    if not tavily_client: return {"context": "", "runway_images": []}
    logger.info(f"👠 Podyum Analizi: {topic}")

    runway_queries = [
        f"Vogue Runway {topic} trends Spring/Summer 2026 Paris Milan -buy",
        f"high fashion designer collections 2025 {topic} catwalk photos",
        f"best {topic} moments from recent fashion weeks haute couture review"
    ]

    runway_context = "### RUNWAY DATA (HIGH FASHION ONLY) ###\n"
    raw_runway_images = []

    try:
        for q in runway_queries:
            try:
                response = tavily_client.search(query=q, search_depth="advanced", include_images=True, max_results=3)
                results = response.get('results', [])
                for res in results:
                    runway_context += f"KAYNAK: {res.get('title')}\nURL: {res.get('url')}\nÖZET: {res.get('content', '')[:800]}\n\n"
                for img_url in response.get('images', []):
                    if img_url and img_url.startswith('http'): raw_runway_images.append(img_url)
            except:
                continue

        filtered = [img for img in raw_runway_images if is_quality_fashion_image(img)]
        unique = list(set(filtered))
        # [GARANTİ] Vision boş dönerse filtered listeyi kullan
        final_imgs = validate_images_with_vision(unique, filter_type="runway") or unique[:4]

        return {"context": runway_context, "runway_images": final_imgs}
    except Exception as e:
        return {"context": f"Hata: {e}", "runway_images": []}


def deep_market_research(topic: str) -> Dict[str, Any]:
    if not tavily_client: return {"context": "", "market_images": []}
    logger.info(f"🔍 Pazar Analizi: {topic}")

    queries = [
        f"{topic} 2025/2026 trends consumer behavior",
        f"{topic} best sellers trendyol zara 2025",
        f"popular {topic} fabrics and colors 2026"
    ]

    context_data = "### MARKET DATA & PRODUCT LINKS ###\n"
    raw_image_pool = []
    market_images_result = []

    try:
        image_to_page_map = {}
        for q in queries:
            try:
                response = tavily_client.search(query=q, search_depth="advanced", include_images=True, max_results=4)
                page_urls = [res.get('url') for res in response.get('results', [])]
                for img_url in response.get('images', []):
                    if img_url and img_url.startswith("http"):
                        raw_image_pool.append(img_url)
                        if img_url not in image_to_page_map and page_urls: image_to_page_map[img_url] = page_urls[0]
                for res in response.get('results', []):
                    context_data += f"BAŞLIK: {res.get('title')}\nİÇERİK: {res.get('content')}\nURL: {res.get('url')}\n\n"
            except:
                continue

        candidates = [img for img in raw_image_pool if is_quality_fashion_image(img)]
        unique = list(set(candidates))
        # [GARANTİ] Vision boş dönerse unique listeyi kullan
        final_market_images = validate_images_with_vision(unique, filter_type="market") or unique[:10]

        if settings.serp_api_key and final_market_images:
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                f_to_url = {executor.submit(get_image_source_page_with_serp, url): url for url in final_market_images}
                for f in concurrent.futures.as_completed(f_to_url):
                    img = f_to_url[f]
                    try:
                        page = f.result()
                    except:
                        page = None
                    market_images_result.append({'img': img, 'page': page or image_to_page_map.get(img, img)})
        else:
            for img in final_market_images:
                market_images_result.append({'img': img, 'page': image_to_page_map.get(img, img)})

        return {"context": context_data, "market_images": market_images_result[:10]}
    except Exception as e:
        return {"context": str(e), "market_images": []}


# -----------------------------------------------------------------------------
# 4. RAPORLAMA
# -----------------------------------------------------------------------------

def generate_strategic_report(user_message: str, research_data: str) -> str:
    if not openai_client: return "OpenAI hatası."

    system_prompt = """
    Sen Kıdemli Moda Stratejistisin.

    KURALLAR:
    1. Şablonu KOPYALAMA, içini GERÇEK verilerle veya tahminlerinle DOLDUR.
    2. Bölüm 4'te 5 modeli tek tek detaylandır.
    3. Görsel yer tutucularını ([[...]]) METNİN İÇİNE GÖMME, yeni satıra yaz.

    RAPOR ŞABLONU:
    # 💎 [KONU] - 2026 VİZYON RAPORU

    ## 🌍 BÖLÜM 1: GLOBAL DEFİLE İZLERİ
    (Analiz...)
    [[RUNWAY_VISUAL_1]]
    [[RUNWAY_VISUAL_2]]

    ## 📈 BÖLÜM 2: TİCARİ TRENDLER
    (Analiz...)

    ## 💰 BÖLÜM 3: FİYAT ANALİZİ
    | Segment | Min | Max | Ort |
    | :--- | :--- | :--- | :--- |
    | Eko | ... | ... | ... |
    | Orta | ... | ... | ... |
    | Lüks | ... | ... | ... |

    ## 🏆 BÖLÜM 4: TOP 5 TİCARİ MODEL
    ### 1. [Model Adı]
    * Detaylar...
    [[VISUAL_CARD_1]]

    ### 2. [Model Adı]
    * Detaylar...
    [[VISUAL_CARD_2]]

    (5'e kadar devam et)

    ## 🛍️ BÖLÜM 5: RAKİP VİTRİNİ
    ### 🛒 [Ürün Adı]
    * Fiyat: ...
    * Link: [İncele](TAM_URL)
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"KONU: {user_message}\nVERİLER:\n{research_data}"}
            ],
            temperature=0.4
        )
        return response.choices[0].message.content
    except Exception:
        return "Rapor hatası."


# -----------------------------------------------------------------------------
# 5. GÖRSEL ÜRETİMİ
# -----------------------------------------------------------------------------

def generate_image_prompts(analysis_text: str) -> List[Dict[str, str]]:
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system",
                 "content": "Extract 5 fashion models. JSON: {'items': [{'model_name': '...', 'ref_id': 'IMG_REF_X', 'prompt': '...'}]}"},
                {"role": "user", "content": analysis_text}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content).get("items", [])
    except:
        return []


def extract_visual_style(user_text: str) -> str:
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "Extract visual style keywords (English)."},
                      {"role": "user", "content": user_text}],
            max_tokens=60
        )
        return response.choices[0].message.content.strip()
    except:
        return ""


def generate_ai_images(prompt_items):
    if not settings.fal_api_key: return []
    results = []
    headers = {"Authorization": f"Key {settings.fal_api_key}", "Content-Type": "application/json"}

    for item in prompt_items[:5]:
        try:
            prompt = item.get("prompt") + ", hyper-realistic, 8k, e-commerce style"
            res = requests.post("https://fal.run/fal-ai/flux/dev", headers=headers,
                                json={"prompt": prompt, "image_size": "portrait_4_3"}, timeout=30)
            url = res.json().get("images")[0].get("url")
            if url: results.append({**item, "url": url})
        except:
            pass
    return results


# -----------------------------------------------------------------------------
# 6. ANA ORKESTRASYON
# -----------------------------------------------------------------------------

async def generate_ai_response(user_message: str, chat_history: List[Dict[str, str]] = [],
                               generate_images: bool = False) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()

    intent = await loop.run_in_executor(None, analyze_user_intent, user_message, chat_history)
    logger.info(f"🧠 Niyet: {intent}")

    if intent == "GENERAL_CHAT":
        content = await loop.run_in_executor(None, handle_general_chat, user_message)
        return {"content": content, "image_urls": [], "image_links": {}, "process_log": ["Sohbet."]}

    if intent == "FOLLOW_UP":
        response_text = await handle_follow_up(user_message, chat_history)

        # [DÜZELTME] "Görsel çiz" denmese bile Follow-up'ta görsel üretmeyi dene
        should_gen = bool(settings.fal_api_key)

        ai_generated_items = []
        if should_gen:
            prompt_items = await loop.run_in_executor(None, generate_image_prompts, response_text)
            # Eğer prompt çıkmazsa (sohbet metniyse), zorla prompt üret
            if not prompt_items and "görsel" in user_message.lower():
                prompt_items = [{"model_name": "Requested Visual", "prompt": f"Fashion illustration of {user_message}"}]

            ai_generated_items = await loop.run_in_executor(None, generate_ai_images, prompt_items)

        combined_images = [d['url'] for d in ai_generated_items]
        # Görselleri metne ekle
        for item in ai_generated_items:
            response_text += f"\n\n![{item.get('model_name')}]({item['url']})"

        return {
            "content": response_text,
            "image_urls": combined_images,
            "image_links": {u: None for u in combined_images},
            "process_log": ["Sohbet devamı."]
        }

    # MARKET RESEARCH
    f_m = loop.run_in_executor(None, deep_market_research, user_message)
    f_r = loop.run_in_executor(None, analyze_runway_trends, user_message)
    market_res, runway_res = await asyncio.gather(f_m, f_r)

    full_data = f"{runway_res.get('context', '')}\n===\n{market_res.get('context', '')}"
    final_report = await loop.run_in_executor(None, generate_strategic_report, user_message, full_data)

    market_images = market_res.get("market_images", [])
    ref_lookup = {f"IMG_REF_{i + 1}": img['img'] for i, img in enumerate(market_images)}

    # [DÜZELTME] Keyword kontrolünü kaldırdım. Key varsa üret.
    should_gen = bool(settings.fal_api_key)
    ai_generated_items = []

    if should_gen:
        p_items = await loop.run_in_executor(None, generate_image_prompts, final_report)
        # [GARANTİ] Eğer rapordan prompt çıkmazsa, kullanıcı mesajından üret
        if not p_items:
            p_items = [{"model_name": "Trend Analysis", "ref_id": "",
                        "prompt": f"High fashion photography of {user_message}, studio light, 8k"}]

        style = await loop.run_in_executor(None, extract_visual_style, user_message)
        # Promptları zenginleştir
        for p in p_items:
            p['prompt'] = f"{p['prompt']}, {style}"

        ai_generated_items = await loop.run_in_executor(None, generate_ai_images, p_items)

    # Görsel Entegrasyonu
    final_content = final_report
    runway_imgs = runway_res.get("runway_images", [])

    # Defile
    for i in range(1, 3):
        ph = f"[[RUNWAY_VISUAL_{i}]]"
        if i <= len(runway_imgs):
            final_content = final_content.replace(ph, f"![Defile {i}]({runway_imgs[i - 1]})")
        else:
            final_content = final_content.replace(ph, "")

    # AI / Pazar
    for i in range(1, 6):
        ph = f"[[VISUAL_CARD_{i}]]"
        ai_item = ai_generated_items[i - 1] if i <= len(ai_generated_items) else None

        replacement = ""
        if ai_item:
            ai_url = ai_item.get("url")
            m_url = ref_lookup.get(ai_item.get("ref_id"), "")
            m_page = next((d['page'] for d in market_images if d['img'] == m_url), m_url)

            if m_url and ai_url:
                replacement = f"\n| Pazar Ref. | AI Tasarım ({ai_item.get('model_name')}) |\n|:---:|:---:|\n| <a href='{m_page}' target='_blank'><img src='{m_url}' width='200'/></a> | <img src='{ai_url}' width='200'/> |\n"
            elif ai_url:
                replacement = f"\n| AI Tasarım ({ai_item.get('model_name')}) |\n|:---:|\n| <img src='{ai_url}' width='200'/> |\n"

        final_content = final_content.replace(ph, replacement)

        # [ZORLA EKLEME] Eğer LLM placeholder'ı unuttuysa ve görsel varsa, sona ekle
        if ai_item and ph not in final_report:
            final_content += f"\n\n### Ek Model Görseli {i}\n{replacement}"

    final_content = _remove_non_http_images(final_content)

    combined_images = [d['img'] for d in market_images] + [d['url'] for d in ai_generated_items] + runway_imgs
    image_links = {img: None for img in combined_images}
    for d in market_images: image_links[d['img']] = d['page']

    return {
        "content": final_content,
        "image_urls": combined_images,
        "image_links": image_links,
        "process_log": ["Tamamlandı."]
    }