"""
Image Processing - Görsel filtreleme, doğrulama ve üretim
"""
import json
import re
import logging
import requests
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional
from .clients import openai_client
from ..config import settings

logger = logging.getLogger(__name__)


def _remove_non_http_images(markdown_text: str) -> str:
    """Placeholder linkleri temizler."""
    if not markdown_text: return ""
    pattern = r'!\[[^\]]*\]\((?!https?://|http://)[^)]+\)'
    return re.sub(pattern, '', markdown_text)


# --- 1. GÜVENLİK: URL TEMİZLİK İSTASYONU ---
def is_quality_fashion_image(url: str) -> bool:
    """
    Görselin Vision API tarafından desteklenip desteklenmediğini kontrol eder.
    Query parametrelerini (?token=...) görmezden gelerek uzantıyı kontrol eder.
    """
    if not url: return False

    try:
        # URL'i parçala ve sadece dosya yolunu (path) al.
        # Böylece ?sig=123 kısmı uzantı kontrolünü bozmaz.
        parsed = urlparse(url)
        clean_path = parsed.path.lower()
    except:
        return False

    # OpenAI sadece bunları kabul eder
    valid_extensions = ('.jpg', '.jpeg', '.png', '.webp')
    if not clean_path.endswith(valid_extensions):
        return False

    # Yasaklı kelimeler (Logo, ikon vb.)
    url_lower = url.lower()
    banned_keywords = [
        'logo', 'icon', 'avatar', 'user', 'profile', 'banner', 'button',
        'sprite', 'svg', 'loader', 'gif', 'promo', 'footer', 'header',
        'favicon', 'thumbnail', 'pixel', 'overlay', 'adserver', 'placeholder'
    ]
    if any(keyword in url_lower for keyword in banned_keywords):
        return False

    return True

# --- 2. MAKYAJ: FOLLOW-UP PROMPT ZENGİNLEŞTİRİCİ ---
def enhance_follow_up_prompt(base_prompt: str) -> str:
    """Sohbet modundaki basit çizim isteklerini stüdyo kalitesine yükseltir."""
    enhancements = (
        ", hyper-realistic, volumetric lighting, high fashion editorial, "
        "professional studio photography, 8k resolution, detailed texture, "
        "neutral background"
    )
    return f"{base_prompt.strip()}{enhancements}"


def validate_images_with_vision(image_urls: List[str], filter_type: str = "market") -> List[str]:
    """Toplu doğrulama (Basitleştirilmiş)"""
    # URL temizliği zaten is_quality_fashion_image ile yapılıyor
    safe = [u for u in image_urls if is_quality_fashion_image(u)]
    return safe[:8]


def validate_image_content_match(image_url: str, description: str) -> bool:
    """
    Görselin, aranan açıklama ile uyuşup uyuşmadığını kontrol eder.
    """
    if not image_url or not openai_client: return True

    # URL Güvenlik Kontrolü (Tekrar)
    if not is_quality_fashion_image(image_url): return False

    system_prompt = """
    You are a strict Fashion Quality Control AI.
    Compare the IMAGE with the DESCRIPTION.
    
    CRITICAL RULES:
    1. COLOR MATCH: If description says 'Yellow', image MUST be Yellow. Rejet Blue/Red etc.
    2. ITEM MATCH: If description says 'Dress', image MUST be a Dress. Reject Shoes/Bags.
    3. PHOTO TYPE: Must be a real product/model photo. Reject text/logos.
    
    Output ONLY "YES" or "NO".
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": f"DESCRIPTION: {description}"},
                    {"type": "image_url", "image_url": {"url": image_url, "detail": "low"}}
                ]}
            ],
            max_tokens=5,
            temperature=0.0
        )
        result = response.choices[0].message.content.strip().upper()
        return "YES" in result
    except Exception as e:
        logger.warning(f"Vision Match Hatası: {e}")
        return False # Hata durumunda risk alma, reddet.


def generate_image_prompts(analysis_text: str) -> List[Dict[str, str]]:
    """Görsel prompt üretici"""
    if not openai_client: return []
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Extract 5 fashion models. JSON: {'items': [{'model_name': '...', 'ref_id': 'IMG_REF_X', 'prompt': '...'}]}"},
                {"role": "user", "content": analysis_text}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content).get("items", [])
    except: return []

def extract_visual_style(user_text: str) -> str:
    if not openai_client: return ""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": f"Extract visual style keywords from: {user_text}"}],
            max_tokens=60
        )
        return response.choices[0].message.content.strip()
    except: return ""

def validate_single_image_is_dress(image_url: str) -> bool:
    return is_quality_fashion_image(image_url)

def generate_ai_images(prompt_items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """FAL AI Görsel Üretimi"""
    if not settings.fal_api_key: return []

    results = []
    headers = {"Authorization": f"Key {settings.fal_api_key}", "Content-Type": "application/json"}

    for idx, item in enumerate(prompt_items[:5], 1):
        try:
            # Prompt zaten orchestrator'da zenginleştirilmiş geliyor.
            final_prompt = item.get("prompt", "") + ", e-commerce style, clear background"

            logger.info(f"Görsel {idx}/5 üretiliyor: {item.get('model_name')}")
            res = requests.post(
                "https://fal.run/fal-ai/flux/dev",
                headers=headers,
                json={"prompt": final_prompt, "image_size": "portrait_4_3"},
                timeout=30
            )
            if res.status_code == 200:
                img_url = res.json().get("images", [{}])[0].get("url")
                results.append({**item, "url": img_url})
                logger.info(f"✅ Görsel {idx} başarıyla üretildi")
            else:
                logger.error(f"❌ HTTP {res.status_code}")
                results.append({**item, "url": None})
        except Exception as e:
            logger.error(f"❌ Görsel hatası: {e}")
            results.append({**item, "url": None})

    return results