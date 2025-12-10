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

