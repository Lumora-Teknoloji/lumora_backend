"""
Image Processing - Görsel filtreleme, doğrulama ve üretim
"""
import json
import re
import logging
import requests
import concurrent.futures
from typing import List, Dict, Any, Optional
from .clients import openai_client
from ..config import settings

logger = logging.getLogger(__name__)


def _remove_non_http_images(markdown_text: str) -> str:
    """
    IMG_REF_* gibi placeholder linklerden kaynaklanan kırık görselleri temizler.
    """
    if not markdown_text:
        return ""
    pattern = r'!\[[^\]]*\]\((?!https?://|http://)[^)]+\)'
    return re.sub(pattern, '', markdown_text)


def is_quality_fashion_image(url: str) -> bool:
    """Temel görsel kalite filtresi (String bazlı - hızlı eleme)"""
    if not url:
        return False
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


def verify_image_with_serp(image_url: str) -> bool:
    """SerpApi ile görsel doğrulama (varlık kontrolü)"""
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


def get_image_source_page_with_serp(image_url: str) -> Optional[str]:
    """SerpApi ile görsel kaynak sayfasını bulma (ürün sayfası odaklı)"""
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
                if has_category and not has_product:
                    return False
                return has_product or len(url.split('/')) > 5

            def score_url(url: str) -> int:
                url_lower = url.lower()
                score = 0
                if any(ind in url_lower for ind in product_indicators):
                    score += 10
                if any(ind in url_lower for ind in category_indicators):
                    score -= 5
                if len(url.split('/')) > 5:
                    score += 3
                ecommerce_domains = [
                    'trendyol.com', 'hepsiburada.com', 'n11.com', 'gittigidiyor.com',
                    'amazon.com', 'zara.com', 'mango.com', 'hm.com', 'lcwaikiki.com'
                ]
                if any(domain in url_lower for domain in ecommerce_domains):
                    score += 2
                return score

            candidate_urls = []
            inline_images = data.get('inline_images', [])
            for img_result in inline_images:
                url = img_result.get('link') or img_result.get('source') or img_result.get('url')
                if url and url.startswith('http'):
                    candidate_urls.append(url)

            results = data.get('results', [])
            for result in results:
                url = result.get('link') or result.get('url')
                if url and url.startswith('http'):
                    candidate_urls.append(url)

            visual_matches = data.get('visual_matches', [])
            for match in visual_matches:
                url = match.get('link') or match.get('url')
                if url and url.startswith('http'):
                    candidate_urls.append(url)

            if not candidate_urls:
                return None

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


def validate_images_with_vision(image_urls: List[str], filter_type: str = "market") -> List[str]:
    """GPT-4o Vision ile akıllı görsel doğrulama"""
    if not image_urls or not openai_client:
        return image_urls

    safe_candidates = []
    risky_domains = [
        'instagram.com', 'facebook.com', 'cdn.instagram', 'fbcdn.net',
        'tiktok.com', 'pinterest', 'twimg.com'
    ]
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
            if not isinstance(indices, list):
                return candidates
            verified_urls = [candidates[i] for i in indices if isinstance(i, int) and 0 <= i < len(candidates)]
            return verified_urls
        except json.JSONDecodeError:
            return candidates

    except Exception as e:
        logger.error(f"Vision filtre hatası: {e}. Filtre devre dışı bırakılıyor, ham liste dönülüyor.")
        return candidates[:4]


def generate_image_prompts(analysis_text: str) -> List[Dict[str, str]]:
    """Analiz metninden görsel prompt'ları çıkarır"""
    if not openai_client:
        return []
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Extract 5 fashion models. JSON: {'items': [{'model_name': '...', 'ref_id': 'IMG_REF_X', 'prompt': '...'}]}"
                },
                {"role": "user", "content": analysis_text}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content).get("items", [])
    except Exception as e:
        logger.error(f"Görsel prompt üretme hatası: {e}")
        return []


def extract_visual_style(user_text: str) -> str:
    """Kullanıcı metninden görsel stil anahtar kelimelerini çıkarır"""
    if not openai_client:
        return ""
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Extract visual style keywords (English)."},
                {"role": "user", "content": user_text}
            ],
            max_tokens=60
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Görsel stil çıkarma hatası: {e}")
        return ""


def generate_ai_images(prompt_items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """FAL AI ile görsel üretir"""
    if not settings.fal_api_key:
        return []
    
    results = []
    headers = {
        "Authorization": f"Key {settings.fal_api_key}",
        "Content-Type": "application/json"
    }

    for item in prompt_items[:5]:
        try:
            prompt = item.get("prompt", "") + ", hyper-realistic, 8k, e-commerce style"
            res = requests.post(
                "https://fal.run/fal-ai/flux/dev",
                headers=headers,
                json={"prompt": prompt, "image_size": "portrait_4_3"},
                timeout=30
            )
            url = res.json().get("images")[0].get("url")
            if url:
                results.append({**item, "url": url})
        except Exception as e:
            logger.error(f"AI görsel üretme hatası: {e}")
            pass
    
    return results

