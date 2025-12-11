"""
Research & Reporting - Veri toplama ve raporlama
"""
import logging
import json
import re
import asyncio
from typing import List, Dict, Any
from .clients import tavily_client, openai_client
from .images import (
    is_quality_fashion_image,
    validate_images_with_vision,
    validate_image_content_match
)

logger = logging.getLogger(__name__)

# --- 1. VERİ TOPLAMA FONKSİYONLARI ---

def analyze_runway_trends(topic: str) -> Dict[str, Any]:
    """Podyum ve defile trendlerini analiz eder"""
    if not tavily_client: return {"context": "", "runway_images": []}
    logger.info(f"👠 Podyum Analizi: {topic}")
    runway_queries = [
        f"Vogue Runway {topic} trends Spring/Summer 2026 Paris Milan -buy",
        f"high fashion designer collections 2025 {topic} catwalk photos"
    ]
    runway_context = "### RUNWAY DATA ###\n"
    raw_runway_images = []
    try:
        for q in runway_queries:
            try:
                response = tavily_client.search(query=q, search_depth="advanced", include_images=True, max_results=5)
                for res in response.get('results', []):
                    runway_context += f"KAYNAK: {res.get('title')}\nURL: {res.get('url')}\nÖZET: {res.get('content', '')[:800]}\n\n"
                for img in response.get('images', []):
                    if is_quality_fashion_image(img): raw_runway_images.append(img)
            except: continue

        unique = list(set(raw_runway_images))
        return {"context": runway_context, "runway_images": unique[:4]}
    except Exception as e:
        return {"context": f"Hata: {e}", "runway_images": []}


def deep_market_research(topic: str) -> Dict[str, Any]:
    """Genel pazar araştırması"""
    if not tavily_client: return {"context": "", "market_images": []}
    logger.info(f"🔍 Pazar Analizi (Genel): {topic}")
    queries = [f"{topic} 2026 trends consumer behavior", f"{topic} best sellers 2025"]
    context_data = "### MARKET DATA ###\n"
    try:
        for q in queries:
            try:
                res = tavily_client.search(query=q, search_depth="advanced", include_images=False, max_results=3)
                for r in res.get('results', []):
                    context_data += f"BAŞLIK: {r.get('title')}\nİÇERİK: {r.get('content')}\n\n"
            except: continue
        return {"context": context_data, "market_images": []}
    except Exception as e:
        return {"context": str(e), "market_images": []}


# --- 2. AKILLI GÖRSEL VE STİL ÇIKARMA (GÜNCELLENDİ) ---

def extract_visual_search_terms(report_text: str, user_topic: str = "") -> List[Dict[str, str]]:
    """Görsel terimlerini çıkarır."""
    if not openai_client: return []

    match = re.search(r'#{1,3}\s*.*B[ÖO]L[ÜU]M\s*4', report_text, re.IGNORECASE)
    if not match: match = re.search(r'#{1,3}\s*.*TOP\s*5', report_text, re.IGNORECASE)

    start_index = match.start() if match else 0
    relevant_text = report_text[start_index:start_index+4000]

    system_prompt = f"""
    You are an expert AI Visual Director.
    INPUT: User Request "{user_topic}" + Report Section.
    
    TASK: Extract 5 concrete fashion items.
    
    CRITICAL RULES:
    1. **OUTFIT/COMBINATIONS:** If user asked for "Kombin" or "Outfit", the AI Prompt MUST be: "Full body shot of a fashion model wearing [Item] paired with [Accessories], street style/studio."
    2. **ISOLATION:** Don't mix items. Item 1 prompt is only about Item 1.
    3. **SPECIFICITY:** Search queries must be short (e.g. "Zümrüt Yeşili Saten Elbise").
    
    JSON FORMAT:
    {{
      "items": [
        {{
          "name": "Item Name",
          "search_query": "Turkish Query",
          "ai_prompt": "Detailed English prompt (Model wearing...)"
        }}
      ]
    }}
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": relevant_text}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content).get("items", [])
    except: return []


# --- 3. NOKTA ATIŞI ARAMA (ISRARCI AVCI MODU) ---

def find_visual_match_for_model(search_query: str) -> Dict[str, str]:
    if not tavily_client: return {}

    query = f"{search_query} trendyol modanisa zara 2025 product photo"

    try:
        # 1. GENİŞ HAVUZ (10 Resim İste)
        res = tavily_client.search(query=query, search_depth="advanced", include_images=True, max_results=10)

        candidates = []
        for img in res.get('images', []):
            if is_quality_fashion_image(img):
                candidates.append(img)

        # 3. SIRALI DOĞRULAMA (Bulana Kadar Dene)
        for img_url in candidates:
            if validate_image_content_match(img_url, search_query):
                page_url = res['results'][0].get('url') if res.get('results') else ""
                return {"img": img_url, "page": page_url}

        logger.warning(f"⚠️ Uygun görsel bulunamadı: {search_query}")
        return {}

    except Exception as e:
        logger.error(f"Görsel arama hatası: {e}")
        return {}


# --- 4. RAPORLAMA ---

def generate_strategic_report(user_message: str, research_data: str) -> str:
    if not openai_client: return "OpenAI hatası."

    system_prompt = """
    Sen Kıdemli Moda Stratejistisin.
    GÖREVİN: "{user_message}" için rapor yaz.

    KURALLAR:
    1. **FORMAT YASAĞI:** Asla kendi kafana göre "🎨 AI Tasarım:" veya "📸 Piyasa Örneği:" gibi başlıklar atma.
    2. **GÖRSEL KARTI:** Sadece ve sadece `[[VISUAL_CARD_x]]` placeholder'ını kullan. Gerisini sistem halledecek.
       Örnek:
       ### 1. Zümrüt Elbise
       * Açıklama...
       [[VISUAL_CARD_1]]
    
    3. Tablolar Dinamik Olsun (| Sütun | Sütun |).
    4. Bölüm 1.1 (Sosyal Medya) mutlaka olsun.

    RAPOR ŞABLONU:
    # 💎 [KONU] - 2026 VİZYON RAPORU

    ## 🌍 BÖLÜM 1: GLOBAL DEFİLE İZLERİ
    (Analiz...)
    [[RUNWAY_VISUAL_1]]
    [[RUNWAY_VISUAL_2]]

    ## 📈 BÖLÜM 1.1: SOSYAL MEDYA VE INFLUENCER ETKİLERİ
    (Sosyal medya trendleri...)

    ## 📈 BÖLÜM 2: TİCARİ TRENDLER
    (Analiz...) 

    [DİNAMİK BÖLÜM 3]
    [DİNAMİK TABLO]

    ## 🏆 BÖLÜM 4: TOP 5 TİCARİ MODEL
    ### 1. [Madde Adı]
    * Detaylar...
    [[VISUAL_CARD_1]]

    (5'e kadar devam et)

    ## 🛍️ BÖLÜM 5: RAKİP VİTRİNİ
    ### 🛒 [Ürün Adı]
    * Detay: ...
    * Link: [İncele](TAM_URL)
    """

    try:
        formatted_prompt = system_prompt.format(user_message=user_message)
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": formatted_prompt},
                {"role": "user", "content": f"VERİ:\n{research_data}"}
            ],
            temperature=0.4
        )
        return response.choices[0].message.content
    except: return "Rapor hatası."