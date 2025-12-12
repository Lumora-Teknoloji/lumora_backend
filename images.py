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
    """
    if not url: return False

    try:
        parsed = urlparse(url)
        clean_path = parsed.path.lower()
    except:
        return False

    valid_extensions = ('.jpg', '.jpeg', '.png', '.webp')
    if not clean_path.endswith(valid_extensions):
        return False

    url_lower = url.lower()
    banned_keywords = [
        'logo', 'icon', 'avatar', 'user', 'profile', 'banner', 'button',
        'sprite', 'svg', 'loader', 'gif', 'promo', 'footer', 'header',
        'favicon', 'thumbnail', 'pixel', 'overlay', 'adserver', 'placeholder',
        'food', 'recipe', 'bakery' # Gıda ile ilgili kelimeleri de engelle
    ]
    if any(keyword in url_lower for keyword in banned_keywords):
        return False

    return True

# --- 2. MAKYAJ: E-TİCARET STÜDYO PROMPTU ---
def enhance_follow_up_prompt(base_prompt: str) -> str:
    """
    Promptu, e-ticaret sitesinde satılacak şekilde
    boydan, stüdyo ışıklı ve net bir ürün fotoğrafına dönüştürür.
    """
    enhancements = (
        ", full body photograph, professional e-commerce studio photoshoot, "
        "bright softbox lighting, evenly lit, seamless neutral grey studio background, "
        "sharp focus from head to toe, highly detailed fabric texture, "
        "catalog style, lookbook aesthetic, 8k resolution"
    )
    return f"{base_prompt.strip()}{enhancements}"


def validate_images_with_vision(image_urls: List[str], filter_type: str = "market") -> List[str]:
    """Toplu doğrulama (Basitleştirilmiş)"""
    safe = [u for u in image_urls if is_quality_fashion_image(u)]
    return safe[:8]


# --- KRİTİK GÜNCELLEME: SIKI RENK VE MODEL KONTROLÜ ---
def validate_image_content_match(image_url: str, description: str) -> bool:
    """
    Görselin, aranan açıklama ile BİREBİR uyuşup uyuşmadığını kontrol eder.
    """
    if not image_url or not openai_client: return True

    if not is_quality_fashion_image(image_url): return False

    # Promptu çok daha katı hale getirdik
    system_prompt = """
    You are a STRICT Fashion Quality Control AI. Do not be lenient.
    
    Task: Verify if the image matches the description EXACTLY.
    Description: "{description}"
    
    RULES FOR REJECTION (Reply 'NO' if any apply):
    1. WRONG COLOR: If description says 'Emerald Green' and image is 'Sage', 'Lime', 'Beige' or 'Black', REJECT. Color must be vivid and exact match.
    2. WRONG ITEM: If description says 'Dress' and image is a 'Jumpsuit', 'Coat', 'Top' or 'Shoes', REJECT.
    3. WRONG CONTENT: If image shows food, scenery, text, or multiple items, REJECT.
    4. VISIBILITY: If the item is not clearly visible or cropped too much, REJECT.
    
    Output ONLY "YES" or "NO".
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt.format(description=description)},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": image_url, "detail": "low"}}
                ]}
            ],
            max_tokens=5,
            temperature=0.0
        )
        result = response.choices[0].message.content.strip().upper()

        # Loglama ekleyelim ki hatayı görelim
        if "YES" in result:
            return True
        else:
            # logger.info(f"Vision Reddedildi: {description} -> {image_url}") # İstersen açabilirsin
            return False

    except Exception as e:
        logger.warning(f"Vision Match Hatası: {e}")
        return False


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
            final_prompt = item.get("prompt", "")

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

# ... (extract_image_request, extract_previous_image_context, modify_image_prompt, generate_custom_images AYNI KALACAK) ...
def extract_image_request(user_message: str) -> Dict[str, Any]:
    # ... (Aynı kod) ...
    if not openai_client:
        return {"count": 1, "description": user_message, "prompts": []}

    system_prompt = """
    You are an image request parser. Extract:
    1. count: How many images? (default 1)
    2. description: What to draw?
    3. prompts: Detailed English prompts.
    
    Return JSON: {"count": N, "description": "...", "prompts": ["..."]}
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
            response_format={"type": "json_object"}, temperature=0.3
        )
        result = json.loads(response.choices[0].message.content)
        count = min(max(int(result.get("count", 1)), 1), 10)
        description = result.get("description", user_message)
        prompts = result.get("prompts", [])
        if len(prompts) < count:
            for i in range(len(prompts), count): prompts.append(f"{description}, variation {i+1}")
        enhanced_prompts = [enhance_follow_up_prompt(p) for p in prompts[:count]]
        return {"count": count, "description": description, "prompts": enhanced_prompts}
    except Exception as e:
        return {"count": 1, "description": user_message, "prompts": [enhance_follow_up_prompt(user_message)]}

def extract_previous_image_context(chat_history: List[Dict[str, str]]) -> Dict[str, Any]:
    # ... (Aynı kod) ...
    if not openai_client or not chat_history: return {"found": False, "description": "", "original_request": "", "url": ""}
    recent_messages = chat_history[-5:]
    history_text = json.dumps(recent_messages, ensure_ascii=False)
    system_prompt = "Find the LAST generated image info. JSON: {'found': bool, 'description': '...', 'original_request': '...', 'url': '...'}"
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": f"CHAT HISTORY:\n{history_text}"}],
            response_format={"type": "json_object"}, temperature=0.0
        )
        return json.loads(response.choices[0].message.content)
    except: return {"found": False}

def modify_image_prompt(original_description: str, modification_request: str) -> Dict[str, Any]:
    # ... (Aynı kod) ...
    if not openai_client: return {"count": 1, "prompts": [original_description], "modification_type": "regenerate"}
    system_prompt = "Modify image prompt. JSON: {'count': N, 'prompts': ['...'], 'modification_type': '...'}"
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": f"ORIGINAL: {original_description}\nREQUEST: {modification_request}"}],
            response_format={"type": "json_object"}, temperature=0.3
        )
        result = json.loads(response.choices[0].message.content)
        count = min(max(int(result.get("count", 1)), 1), 10)
        prompts = result.get("prompts", [])
        if not prompts: prompts = [original_description]
        while len(prompts) < count: prompts.append(f"{prompts[0]}, variation {len(prompts)+1}")
        enhanced_prompts = [enhance_follow_up_prompt(p) for p in prompts[:count]]
        return {"count": count, "prompts": enhanced_prompts, "modification_type": result.get("modification_type", "variation")}
    except: return {"count": 1, "prompts": [enhance_follow_up_prompt(original_description)], "modification_type": "regenerate"}

def generate_custom_images(prompts: List[str]) -> List[Dict[str, Any]]:
    # ... (Aynı kod) ...
    if not settings.fal_api_key: return []
    results = []
    headers = {"Authorization": f"Key {settings.fal_api_key}", "Content-Type": "application/json"}
    for idx, prompt in enumerate(prompts, 1):
        try:
            logger.info(f"🎨 Özel görsel {idx}/{len(prompts)} üretiliyor...")
            res = requests.post("https://fal.run/fal-ai/flux/dev", headers=headers, json={"prompt": prompt, "image_size": "portrait_4_3"}, timeout=30)
            if res.status_code == 200:
                img_url = res.json().get("images", [{}])[0].get("url")
                results.append({"url": img_url, "prompt": prompt})
                logger.info(f"✅ Özel görsel {idx} başarıyla üretildi")
            else:
                logger.error(f"❌ HTTP {res.status_code}")
                results.append({"url": None, "prompt": prompt})
        except Exception as e:
            logger.error(f"❌ Özel görsel hatası: {e}")
            results.append({"url": None, "prompt": prompt})
    return results