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


# --- 3. YENİ: GÖRSEL ÜRETİM İSTEĞİ ÇIKARICI ---
def extract_image_request(user_message: str) -> Dict[str, Any]:
    """
    Kullanıcı mesajından görsel üretim detaylarını çıkarır.
    Sayı belirtilmezse default 1 adet.
    """
    if not openai_client:
        return {"count": 1, "description": user_message, "prompts": []}
    
    system_prompt = """
    You are an image request parser for a fashion AI.
    Extract the following from the user message:
    1. count: How many images? (default: 1 if not specified)
    2. description: What should be in the image? (in Turkish or English)
    3. prompts: List of detailed prompts for FAL AI image generation
    
    Examples:
    - "3 v yaka" -> count: 3, description: "V yaka tişört"
    - "kırmızı elbise" -> count: 1, description: "Kırmızı elbise"
    - "5 tane mavi gömlek" -> count: 5, description: "Mavi gömlek"
    - "polo yaka" -> count: 1, description: "Polo yaka tişört"
    
    Return JSON: {"count": N, "description": "...", "prompts": ["prompt1", "prompt2", ...]}
    Each prompt should be unique and detailed for fashion product photography.
    Prompts should be in English for better image generation.
    """
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        result = json.loads(response.choices[0].message.content)
        
        # Sayı sınırlaması (1-10 arası)
        count = min(max(int(result.get("count", 1)), 1), 10)
        description = result.get("description", user_message)
        
        # Eğer prompt listesi yoksa veya yetersizse, otomatik oluştur
        prompts = result.get("prompts", [])
        if len(prompts) < count:
            base_prompt = f"High fashion product photography of {description}, professional studio lighting, e-commerce style, 8k resolution, clean background"
            prompts = [f"{base_prompt}, variation {i+1}" for i in range(count)]
        
        return {
            "count": count,
            "description": description,
            "prompts": prompts[:count]
        }
    except Exception as e:
        logger.error(f"Görsel isteği çıkarma hatası: {e}")
        return {
            "count": 1, 
            "description": user_message, 
            "prompts": [f"High fashion product photography of {user_message}, professional studio lighting, 8k"]
        }


# --- 4. YENİ: ÖNCEKİ GÖRSEL BAĞLAMINI ÇIKARICI ---
def extract_previous_image_context(chat_history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Chat geçmişinden en son üretilen görselin bilgilerini çıkarır.
    """
    if not openai_client or not chat_history:
        return {"found": False, "description": "", "original_request": "", "url": ""}
    
    # Son 5 mesajı al (görsel bilgisi bulmak için)
    recent_messages = chat_history[-5:]
    history_text = json.dumps(recent_messages, ensure_ascii=False)
    
    system_prompt = """
    Analyze the chat history and find the LAST generated image information.
    Look for:
    1. Image descriptions (what was generated)
    2. Original user requests for images
    3. Image URLs (if present in markdown format like ![...](...))
    
    Return JSON:
    {
        "found": true/false,
        "description": "what the image shows (in original language)",
        "original_request": "user's original request that triggered image generation",
        "url": "last image url if found, empty string if not"
    }
    """
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"CHAT HISTORY:\n{history_text}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        logger.error(f"Önceki görsel bilgisi çıkarma hatası: {e}")
        return {"found": False, "description": "", "original_request": "", "url": ""}


# --- 5. YENİ: GÖRSEL MODİFİKASYON PROMPT ÜRETİCİ ---
def modify_image_prompt(original_description: str, modification_request: str) -> Dict[str, Any]:
    """
    Önceki görsel açıklamasını alır ve yeni isteğe göre prompt üretir.
    """
    if not openai_client:
        return {"count": 1, "prompts": [original_description], "modification_type": "regenerate"}
    
    system_prompt = """
    You are an image prompt modifier for a fashion AI.
    
    Given:
    - ORIGINAL: The previous image description
    - REQUEST: What user wants to change
    
    Generate modified prompts. Handle these cases:
    1. "aynısından bir daha" / "tekrar üret" / "bir tane daha" -> Same prompt with slight variation
    2. "farklı açıdan" / "arkadan" / "yandan" -> Add angle: "back view", "side view", "3/4 view"
    3. "daha koyu/açık" -> Modify color: "darker shade", "lighter shade"
    4. "bunu kırmızı/mavi/yeşil yap" -> Change color completely
    5. "3 tane daha" / "5 adet ver" -> Generate multiple variations
    6. "daha uzun/kısa" -> Modify length
    7. "farklı kumaş" -> Change fabric texture
    
    Return JSON:
    {
        "count": number of images to generate (default 1),
        "prompts": ["prompt1", "prompt2", ...],
        "modification_type": "regenerate|angle|color|style|variation|size|fabric"
    }
    
    All prompts should be in English for better image generation quality.
    """
    
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"ORIGINAL: {original_description}\nREQUEST: {modification_request}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        result = json.loads(response.choices[0].message.content)
        
        count = min(max(int(result.get("count", 1)), 1), 10)
        prompts = result.get("prompts", [])
        
        # Eğer prompt yoksa, orijinali kullan
        if not prompts:
            prompts = [f"High fashion product photography of {original_description}, professional studio lighting, 8k"]
        
        # Prompt sayısını count'a eşitle
        while len(prompts) < count:
            prompts.append(f"{prompts[0]}, variation {len(prompts) + 1}")
        
        return {
            "count": count,
            "prompts": prompts[:count],
            "modification_type": result.get("modification_type", "variation")
        }
    except Exception as e:
        logger.error(f"Prompt modifikasyon hatası: {e}")
        return {
            "count": 1,
            "prompts": [f"High fashion product photography of {original_description}, professional studio lighting, 8k"],
            "modification_type": "regenerate"
        }


# --- 6. YENİ: ÖZEL GÖRSEL ÜRETİCİ ---
def generate_custom_images(prompts: List[str]) -> List[Dict[str, Any]]:
    """
    Verilen prompt listesi için FAL AI'dan görsel üretir.
    generate_ai_images fonksiyonunun basitleştirilmiş versiyonu.
    """
    if not settings.fal_api_key:
        return []
    
    results = []
    headers = {"Authorization": f"Key {settings.fal_api_key}", "Content-Type": "application/json"}
    
    for idx, prompt in enumerate(prompts, 1):
        try:
            final_prompt = f"{prompt}, e-commerce style, clear background, detailed texture"
            
            logger.info(f"🎨 Özel görsel {idx}/{len(prompts)} üretiliyor...")
            res = requests.post(
                "https://fal.run/fal-ai/flux/dev",
                headers=headers,
                json={"prompt": final_prompt, "image_size": "portrait_4_3"},
                timeout=30
            )
            if res.status_code == 200:
                img_url = res.json().get("images", [{}])[0].get("url")
                results.append({"url": img_url, "prompt": prompt})
                logger.info(f"✅ Özel görsel {idx} başarıyla üretildi")
            else:
                logger.error(f"❌ HTTP {res.status_code}: {res.text}")
                results.append({"url": None, "prompt": prompt})
        except Exception as e:
            logger.error(f"❌ Özel görsel hatası: {e}")
            results.append({"url": None, "prompt": prompt})
    
    return results