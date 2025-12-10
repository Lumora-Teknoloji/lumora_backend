"""
Research & Reporting - Veri toplama ve raporlama
"""
import logging
from typing import List, Dict, Any
from .clients import tavily_client, openai_client
from .images import (
    is_quality_fashion_image,
    validate_images_with_vision,
    validate_single_image_is_dress
)
from ..config import settings

logger = logging.getLogger(__name__)


def analyze_runway_trends(topic: str) -> Dict[str, Any]:
    """Podyum/defile trendlerini analiz eder"""
    if not tavily_client:
        return {"context": "", "runway_images": []}
    
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
                response = tavily_client.search(
                    query=q,
                    search_depth="advanced",
                    include_images=True,
                    max_results=3
                )
                results = response.get('results', [])
                for res in results:
                    runway_context += (
                        f"KAYNAK: {res.get('title')}\n"
                        f"URL: {res.get('url')}\n"
                        f"ÖZET: {res.get('content', '')[:800]}\n\n"
                    )
                for img_url in response.get('images', []):
                    if img_url and img_url.startswith('http'):
                        raw_runway_images.append(img_url)
            except Exception as e:
                logger.warning(f"Runway sorgu hatası: {e}")
                continue

        filtered = [img for img in raw_runway_images if is_quality_fashion_image(img)]
        unique = list(set(filtered))
        
        # Vision API ile elbise kontrolü yap - Tavily görsellerini filtrele
        # Önce genel filtreleme (runway görselleri)
        validated_imgs = validate_images_with_vision(unique, filter_type="runway") or unique
        
        # Sonra her görseli tek tek elbise kontrolünden geçir
        dress_images = []
        for img_url in validated_imgs:
            if validate_single_image_is_dress(img_url):
                dress_images.append(img_url)
                if len(dress_images) >= 5:  # 5 elbise bulduk, dur
                    break
        
        # Eğer 5 elbise bulunamadıysa, validated_imgs'den devam et
        if len(dress_images) < 5:
            for img_url in validated_imgs:
                if img_url not in dress_images:
                    dress_images.append(img_url)
                    if len(dress_images) >= 5:
                        break
        
        # Tavily'den çekilen görselleri sınırlamıyoruz, orchestrator'da sınırlanacak
        final_imgs = dress_images
        logger.info(f"Runway görsellerinden {len(final_imgs)} elbise görseli seçildi")

        return {"context": runway_context, "runway_images": final_imgs}
    except Exception as e:
        logger.error(f"Runway analizi hatası: {e}")
        return {"context": f"Hata: {e}", "runway_images": []}


def deep_market_research(topic: str) -> Dict[str, Any]:
    """Pazar araştırması yapar"""
    if not tavily_client:
        return {"context": "", "market_images": []}
    
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
                response = tavily_client.search(
                    query=q,
                    search_depth="advanced",
                    include_images=True,
                    max_results=4
                )
                page_urls = [res.get('url') for res in response.get('results', [])]
                for img_url in response.get('images', []):
                    if img_url and img_url.startswith("http"):
                        raw_image_pool.append(img_url)
                        if img_url not in image_to_page_map and page_urls:
                            image_to_page_map[img_url] = page_urls[0]
                for res in response.get('results', []):
                    context_data += (
                        f"BAŞLIK: {res.get('title')}\n"
                        f"İÇERİK: {res.get('content')}\n"
                        f"URL: {res.get('url')}\n\n"
                    )
            except Exception as e:
                logger.warning(f"Market sorgu hatası: {e}")
                continue

        candidates = [img for img in raw_image_pool if is_quality_fashion_image(img)]
        unique = list(set(candidates))
        
        # Vision API ile elbise kontrolü yap - Tavily görsellerini filtrele
        # Önce genel filtreleme (ürün görselleri)
        validated_imgs = validate_images_with_vision(unique, filter_type="market") or unique
        
        # Sonra her görseli tek tek elbise kontrolünden geçir
        dress_images = []
        for img_url in validated_imgs:
            if validate_single_image_is_dress(img_url):
                dress_images.append(img_url)
                if len(dress_images) >= 5:  # 5 elbise bulduk, dur
                    break
        
        # Eğer 5 elbise bulunamadıysa, validated_imgs'den devam et
        if len(dress_images) < 5:
            for img_url in validated_imgs:
                if img_url not in dress_images:
                    dress_images.append(img_url)
                    if len(dress_images) >= 5:
                        break
        
        # Market görselleri: Fix 5 elbise görseli
        final_market_images = dress_images[:5]
        logger.info(f"Tavily görsellerinden {len(final_market_images)} elbise görseli seçildi")

        # Tavily'den gelen sayfa URL'lerini kullan
        for img in final_market_images:
            market_images_result.append({
                'img': img,
                'page': image_to_page_map.get(img, img)
            })

        return {"context": context_data, "market_images": market_images_result}
    except Exception as e:
        logger.error(f"Market araştırması hatası: {e}")
        return {"context": str(e), "market_images": []}


def generate_strategic_report(user_message: str, research_data: str) -> str:
    """Stratejik rapor üretir"""
    if not openai_client:
        return "OpenAI hatası."

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
    except Exception as e:
        logger.error(f"Rapor üretme hatası: {e}")
        return "Rapor hatası."

