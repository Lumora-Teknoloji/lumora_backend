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
    validate_single_image_is_dress,

)

logger = logging.getLogger(__name__)

# --- MEVCUT FONKSİYONLAR ---

def analyze_runway_trends(topic: str) -> Dict[str, Any]:
    if not tavily_client: return {"context": "", "runway_images": []}
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
    if not tavily_client: return {"context": "", "market_images": []}
    logger.info(f"🔍 Pazar Analizi (Genel): {topic}")
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

# --- YENİ: RAPORDAN AKILLI VERİ ÇIKARMA ---

def extract_visual_search_terms(report_text: str) -> List[Dict[str, str]]:
    """
    Oluşturulan raporun 'Bölüm 4' kısmını okur ve her madde için:
    1. Kısa Başlık (Örn: Asimetrik Abiye)
    2. Arama Sorgusu (Örn: Asimetrik kırmızı saten abiye satın al)
    3. AI Prompt (İngilizce detaylı tarif)
    çıkarır. Regex yerine LLM kullanır, hatasızdır.
    """
    if not openai_client: return []

    # Raporun sadece ilgili kısmını alalım (Token tasarrufu)
    section_4_start = report_text.find("## 🏆 BÖLÜM 4")
    if section_4_start == -1: return []
    relevant_text = report_text[section_4_start:section_4_start+3000]

    system_prompt = """
    You are a Data Extractor. Analyze the "TOP 5 MODEL" section of the fashion report.
    For EACH of the 5 models, extract:
    1. "name": The model name (e.g. "Asimetrik Abiye").
    2. "search_query": A specific search query to find this product on e-commerce sites (e.g. "Asimetrik tek omuz saten abiye satın al").
    3. "ai_prompt": A detailed English prompt to generate an image of this model (e.g. "Asymmetric one shoulder satin evening dress, high quality, studio light").
    
    Return ONLY a JSON object with a key "items" containing the list of 5 objects.
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": relevant_text}
            ],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return data.get("items", [])
    except Exception as e:
        logger.error(f"Extractor hatası: {e}")
        return []

# --- NOKTA ATIŞI ARAMA ---

def find_visual_match_for_model(search_query: str) -> Dict[str, str]:
    """
    Spesifik arama sorgusu ile görsel arar.
    """
    if not tavily_client: return {}

    # Sorguyu biraz daha özelleştirelim
    query = f"{search_query} trendyol zara modanisa 2025"
    logger.info(f"🔎 Görsel Aranıyor: {query}")

    try:
        res = tavily_client.search(query=query, search_depth="advanced", include_images=True, max_results=2)

        best_img = ""
        best_link = ""

        candidates = [img for img in res.get('images', []) if is_quality_fashion_image(img)]
        if candidates:
            # Hız için ilk adayı alıyoruz
            best_img = candidates[0]

        if res.get('results'):
            best_link = res['results'][0].get('url')

        if best_img:
            return {"img": best_img, "page": best_link}

    except Exception as e:
        logger.error(f"Görsel arama hatası: {e}")

    return {}

# --- RAPORLAMA ---

def generate_strategic_report(user_message: str, research_data: str) -> str:
    if not openai_client: return "OpenAI hatası."

    system_prompt = """
    Sen Kıdemli Moda Stratejistisin.
    
    KURALLAR:
    1. Şablonu KOPYALAMA, içini GERÇEK verilerle veya mantıklı tahminlerle DOLDUR.
    2. Bölüm 4'te 5 modeli tek tek "### 1. [Model Adı]" formatında yaz.
    3. Görsel yer tutucularını ([[...]]) METNİN İÇİNE GÖMME, yeni satıra yaz.
    
    RAPOR ŞABLONU:
    # 💎 [KONU] - 2026 VİZYON RAPORU
    
    ## 🌍 BÖLÜM 1: GLOBAL DEFİLE İZLERİ
    (Analiz...)
    [[RUNWAY_VISUAL_1]]
    [[RUNWAY_VISUAL_2]]
    
    ## 📈 BÖLÜM 1.1: SOSYAL MEDYA VE INFLUENCER ETKİLERİ
    (Sosyal medya akımları TikTok, Pinterest Instagram vs. , influencer ve kumaş tercihleri hakkında bilgi ver) 
    
    ## 📈 BÖLÜM 2: TİCARİ TRENDLER
    (Analiz, sosyal medya akımları, influencer ve kumaş tercihleri hakkında bilgi ver) 
    
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
                {"role": "user", "content": f"KONU: {user_message}\nVERİ:\n{research_data}"}
            ],
            temperature=0.4
        )
        return response.choices[0].message.content
    except: return "Rapor hatası."