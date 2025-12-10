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
        # Market için daha net: Sadece ürün görselleri
        prompt_text = "Select indices of images that are ONLY fashion PRODUCT photography (garments/products on models/mannequins/white background). Exclude runway photos, logos, banners, lifestyle shots. JSON list of ints only."

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


def validate_single_image_is_dress(image_url: str) -> bool:
    """Tek bir görselin elbise olup olmadığını Vision API ile kontrol eder"""
    if not image_url or not openai_client:
        return False
    
    try:
        prompt_text = (
            "Is this image showing a DRESS or GARMENT (clothing item)? "
            "Respond with ONLY 'yes' if it's a dress/garment, 'no' otherwise. "
            "Exclude non-clothing items, abstract art, text-only images."
        )
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": {"url": image_url, "detail": "low"}}
                ]
            }],
            max_tokens=10,
            temperature=0.0
        )
        
        result = response.choices[0].message.content.strip().lower()
        is_dress = "yes" in result or "true" in result
        logger.info(f"Vision kontrolü: {image_url[:50]}... -> {'Elbise ✅' if is_dress else 'Elbise değil ❌'}")
        return is_dress
    except Exception as e:
        logger.error(f"Vision kontrol hatası: {e}")
        # Hata durumunda varsayılan olarak True döndür (görseli kabul et)
        return True


def generate_ai_images(prompt_items: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """FAL AI ile görsel üretir"""
    if not settings.fal_api_key:
        return []
    
    results = []
    headers = {
        "Authorization": f"Key {settings.fal_api_key}",
        "Content-Type": "application/json"
    }

    for idx, item in enumerate(prompt_items[:5], 1):
        try:
            prompt = item.get("prompt", "") + ", hyper-realistic, 8k, e-commerce style"
            logger.info(f"Görsel {idx}/5 üretiliyor: {item.get('model_name', 'Unknown')}")
            res = requests.post(
                "https://fal.run/fal-ai/flux/dev",
                headers=headers,
                json={"prompt": prompt, "image_size": "portrait_4_3"},
                timeout=30
            )
            if res.status_code == 200:
                response_data = res.json()
                images = response_data.get("images", [])
                if images and len(images) > 0:
                    url = images[0].get("url")
                    if url:
                        results.append({**item, "url": url})
                        logger.info(f"✅ Görsel {idx} başarıyla üretildi")
                    else:
                        logger.warning(f"⚠️ Görsel {idx} için URL bulunamadı")
                else:
                    logger.warning(f"⚠️ Görsel {idx} için images array boş")
            else:
                logger.error(f"❌ Görsel {idx} üretme hatası: HTTP {res.status_code}")
        except Exception as e:
            logger.error(f"❌ Görsel {idx} üretme hatası: {e}")
            # Hata olsa bile item'ı ekle (URL olmadan) ki sıralama bozulmasın
            results.append({**item, "url": None})
    
    logger.info(f"Toplam {len(results)} görsel üretildi (başarılı: {sum(1 for r in results if r.get('url'))})")
    return results

