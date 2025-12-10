"""
Research & Reporting - Veri toplama ve raporlama
"""
import logging
import json
import asyncio
from typing import List, Dict, Any
from .clients import tavily_client, openai_client
from .images import (
    is_quality_fashion_image,
    validate_images_with_vision,
    validate_single_image_is_dress
)
from ..config import settings

logger = logging.getLogger(__name__)

# --- MEVCUT FONKSİYONLAR ---

def analyze_runway_trends(topic: str) -> Dict[str, Any]:
    if not tavily_client:
        return {"context": "", "runway_images": []}

    logger.info(f"👠 Podyum Analizi: {topic}")
    runway_queries = [
        f"Vogue Runway {topic} trends Spring/Summer 2026 Paris Milan -buy",
        f"high fashion designer collections 2025 {topic} catwalk photos",
        f"best {topic} moments from recent fashion weeks"
    ]
    runway_context = "### RUNWAY DATA (HIGH FASHION ONLY) ###\n"
    raw_runway_images = []

    try:
        for q in runway_queries:
            try:
                response = tavily_client.search(query=q, search_depth="advanced", include_images=True, max_results=3)
                for res in response.get('results', []):
                    runway_context += f"KAYNAK: {res.get('title')}\nURL: {res.get('url')}\nÖZET: {res.get('content', '')[:800]}\n\n"
                for img in response.get('images', []):
                    if img.startswith('http'): raw_runway_images.append(img)
            except: continue

        filtered = [img for img in raw_runway_images if is_quality_fashion_image(img)]
        unique = list(set(filtered))
        final_imgs = validate_images_with_vision(unique, filter_type="runway") or unique[:4]
        return {"context": runway_context, "runway_images": final_imgs[:4]}
    except Exception as e:
        return {"context": f"Hata: {e}", "runway_images": []}

def deep_market_research(topic: str) -> Dict[str, Any]:
    if not tavily_client:
        return {"context": "", "market_images": []}
    logger.info(f"🔍 Pazar Analizi: {topic}")

    queries = [f"{topic} 2026 trends consumer behavior", f"{topic} best sellers trendyol zara 2025", f"popular {topic} fabrics 2026"]
    context_data = "### MARKET DATA ###\n"

    try:
        for q in queries:
            try:
                res = tavily_client.search(query=q, search_depth="advanced", include_images=False, max_results=4)
                for r in res.get('results', []):
                    context_data += f"BAŞLIK: {r.get('title')}\nİÇERİK: {r.get('content')}\n\n"
            except: continue
        return {"context": context_data, "market_images": []}
    except Exception as e:
        return {"context": str(e), "market_images": []}

# --- YENİ EKLENEN TREND VE ARAMA FONKSİYONLARI ---

def extract_trend_ideas(topic: str, context_data: str) -> List[str]:
    """Toplanan verilerden 5 trend model fikri çıkarır."""
    if not openai_client: return []

    system_prompt = "You are a Fashion Trend Analyst. Extract 5 specific commercial product types from data."
    user_prompt = f"TOPIC: {topic}\nDATA: {context_data[:3000]}\nOutput JSON list of strings. Ex: ['Silver Dress', 'Red Bag']"

    try:
        res = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            response_format={"type": "json_object"}
        )
        data = json.loads(res.choices[0].message.content)
        items = data.get("items", []) or data.get("trends", [])
        if isinstance(items, list) and items: return items[:5]
        return [f"{topic} Model {i}" for i in range(1, 6)]
    except:
        return [f"{topic} Model {i}" for i in range(1, 6)]

def search_specific_best_seller(model_name: str) -> Dict[str, Any]:
    """Model adı için özel görsel ve link araması yapar."""
    if not tavily_client: return {}

    query = f"best selling {model_name} buy online trendyol zara 2025"
    try:
        res = tavily_client.search(query=query, search_depth="advanced", include_images=True, max_results=2)

        # Görsel seçimi
        best_img = None
        candidates = [img for img in res.get('images', []) if is_quality_fashion_image(img)]

        if candidates:
            # İlk adayı Vision ile kontrol et, olmazsa bile kullan (Fallback)
            if validate_single_image_is_dress(candidates[0]):
                best_img = candidates[0]
            else:
                best_img = candidates[0] # Vision reddetse bile boş kalmasın

        # Link seçimi
        best_link = None
        best_title = model_name
        if res.get('results'):
            best_link = res['results'][0].get('url')
            best_title = res['results'][0].get('title')

        return {
            "search_term": model_name,
            "real_title": best_title,
            "img": best_img,
            "link": best_link
        }
    except:
        return {}

# --- GÜNCELLENEN RAPOR FONKSİYONU ---

def generate_strategic_report(user_message: str, research_data: str, specific_products: List[Dict] = []) -> str:
    """
    Raporu yazar. specific_products=LISTE alarak hatayı engeller.
    """
    if not openai_client: return "OpenAI hatası."

    products_context = "### BULUNAN GERÇEK ÇOK SATANLAR ###\n"
    if specific_products:
        for i, p in enumerate(specific_products):
            products_context += f"{i+1}. {p.get('search_term')} (Link: {p.get('link')})\n"
    else:
        products_context = "Veri bulunamadı, genel analiz yap."

    system_prompt = """
    Sen Kıdemli Moda Stratejistisin.
    
    GÖREVİN:
    Sana verilen 'BULUNAN GERÇEK ÇOK SATANLAR' listesini kullanarak raporun 4. ve 5. bölümlerini doldur.
    
    KURALLAR:
    1. BÖLÜM 4'te: Sana verdiğim 5 gerçek modeli analiz et.
    2. Görsel yer tutucularını ([[...]]) yeni satıra yaz.
    
    RAPOR FORMATI:
    # 💎 [KONU] - 2026 VİZYON RAPORU
    
    ## 🌍 BÖLÜM 1: DEFİLE İZLERİ
    (Analiz...)
    [[RUNWAY_VISUAL_1]]
    [[RUNWAY_VISUAL_2]]
    
    ## 📈 BÖLÜM 2: TİCARİ TRENDLER
    (Analiz...)
    
    ## 💰 BÖLÜM 3: FİYAT ANALİZİ
    | Segment | Min | Max | Ort |
    | :--- | :--- | :--- | :--- |
    | ... | ... | ... | ... |
    
    ## 🏆 BÖLÜM 4: TOP 5 TİCARİ MODEL
    ### 1. [Model Adı]
    * Detay: ...
    [[VISUAL_CARD_1]]
    
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
                {"role": "user", "content": f"KONU: {user_message}\n\n{research_data}\n\n{products_context}"}
            ],
            temperature=0.4
        )
        return response.choices[0].message.content
    except: return "Rapor hatası."