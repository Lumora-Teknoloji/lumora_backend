"""
Research & Reporting - Veri toplama ve raporlama
"""
import logging
import json
import re
import asyncio
from typing import List, Dict, Any
from app.services.core.clients import tavily_client, openai_client
from app.services.ai.image_gen_service import (
    is_quality_fashion_image,
    validate_images_with_vision,
    validate_image_content_match
)

logger = logging.getLogger(__name__)


# --- 1. VERİ TOPLAMA FONKSİYONLARI ---

def analyze_runway_trends(topic: str) -> Dict[str, Any]:
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
            except Exception as e:
                logger.warning(f"Runway search error: {e}")
                continue

        unique = list(set(raw_runway_images))
        return {"context": runway_context, "runway_images": unique[:4]}
    except Exception as e:
        return {"context": f"Hata: {e}", "runway_images": []}


def deep_market_research(topic: str) -> Dict[str, Any]:
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
            except Exception as e:
                logger.warning(f"Market search error: {e}")
                continue
        return {"context": context_data, "market_images": []}
    except Exception as e:
        return {"context": str(e), "market_images": []}


# --- 2. AKILLI GÖRSEL VE STİL ÇIKARMA (GÜNCELLENDİ: CONTEXT INJECTION) ---

def extract_visual_search_terms(report_text: str, user_topic: str = "") -> List[Dict[str, str]]:
    if not openai_client: return []

    match = re.search(r'#{1,3}\s*.*B[ÖO]L[ÜU]M\s*4', report_text, re.IGNORECASE)
    if not match: match = re.search(r'#{1,3}\s*.*TOP\s*5', report_text, re.IGNORECASE)

    start_index = match.start() if match else 0
    relevant_text = report_text[start_index:start_index+4000]

    # PROMPT DEĞİŞİKLİĞİ: "MERGE" (BİRLEŞTİRME) TALİMATI EKLENDİ
    system_prompt = f"""
    You are an expert AI Visual Director.
    INPUT: Report Section 4 (Top Items) and User's Main Topic: "{user_topic}".
    
    TASK: Extract the 5 items listed in the headers and create a MERGED prompt.
    
    CRITICAL RULES:
    1. **NAME:** Extract the EXACT Turkish title (e.g., "1. Payet ve Parıltı").
    2. **AI_PROMPT_BASE:** This is for the image generator.
       - YOU MUST COMBINE the User's Main Topic ("{user_topic}") with the Item Name.
       - Example: If User Topic is "V-neck dress" and Item is "Sequins", output: "V-neck evening dress made of sequin fabric, glittering texture".
       - Do NOT just write "Sequins". The image must show the MAIN TOPIC with the detail applied.
    3. **SEARCH_QUERY:** Specific Turkish query for market search (e.g. "{user_topic} payet elbise").
    
    JSON FORMAT:
    {{
      "items": [
        {{
          "name": "Exact Turkish Title",
          "search_query": "Merged Turkish Query",
          "ai_prompt_base": "Merged English Prompt describing both the Item and User Topic"
        }}
      ]
    }}
    """
    try:
        response = openai_client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": relevant_text}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content).get("items", [])
    except Exception: return []


# ... (Importlar ve önceki fonksiyonlar aynı) ...

# --- 3. NOKTA ATIŞI ARAMA (GÜNCELLENDİ: GARANTİLİ SONUÇ) ---

def find_visual_match_for_model(search_query: str) -> Dict[str, str]:
    if not tavily_client: return {}

    # GÜNCELLEME 1: Sorguyu "Alışveriş" odaklı yapıyoruz
    query = f"{search_query} satın al abiye elbise online satış fiyatları -food -recipe"

    try:
        # 1. GENİŞ HAVUZ (Tavily'den görselleri çek)
        res = tavily_client.search(
            query=query,
            search_depth="advanced",
            include_images=True,
            max_results=8
        )

        candidates = []
        for img in res.get('images', []):
            # Temel kalite kontrolü (Uzantı, yasaklı kelimeler vs.)
            if is_quality_fashion_image(img):
                candidates.append(img)

        # Ürün linkini almaya çalış (Görselin olduğu sayfa)
        page_url = ""
        if res.get('results'):
            # Genellikle ilk sonuç en alakalı satış sitesidir
            page_url = res['results'][0].get('url')

        if not candidates:
            return {}

        # 2. AKILLI SEÇİM & FALLBACK (GÜVENLİK AĞI)

        # Adım A: İlk 3 görseli "Sıkı Yapay Zeka Kontrolü"nden geçir.
        # Bu, rengi ve modeli birebir tutan "mükemmel" görseli arar.
        for img_url in candidates[:3]:
            if validate_image_content_match(img_url, search_query):
                return {"img": img_url, "page": page_url}

        # Adım B (YENİ): Eğer yapay zeka hepsini reddettiyse (çok katı davrandıysa),
        # elimizdeki "teknik olarak sağlam" olan İLK görseli zorla döndür.
        # Çünkü kullanıcı hiç görsel görmemektense, %80 benzeyen bir görseli görmeyi tercih eder.
        logger.info(f"⚠️ Sıkı eşleşme bulunamadı, en iyi aday kullanılıyor: {search_query}")
        return {"img": candidates[0], "page": page_url}

    except Exception as e:
        logger.error(f"Görsel arama hatası: {e}")
        return {}


# ... (generate_strategic_report fonksiyonu aynı kalacak) ...


# --- 4. RAPORLAMA (GÜNCELLENMİŞ TABLO MANTIĞI) ---

def generate_strategic_report(user_message: str, research_data: str) -> str:
    if not openai_client: return "OpenAI hatası."

    system_prompt = """
    Sen Kıdemli Moda Stratejistisin.
    GÖREVİN: Kullanıcının sorusu: "{user_message}" için stratejik rapor yaz.

    KURALLAR:
    1. Şablonu KOPYALAMA, içini GERÇEK verilerle doldur.
    
    2. **STRICT MARKDOWN TABLE RULES (CRITICAL):**
       - Tabloları oluştururken KESİNLİKLE Markdown çizelge formatına uy.
       - Sütunları ayırmak için '|' işaretini kullan.
       - Başlık ile içerik arasına '|---|---|---|' satırını MUTLAKA ekle.
       - Asla metinleri sıkıştırma, sütunlar arasında boşluk bırak.
       
       A) EĞER KONU "RENK" İSE:
          - Başlık: "## 🎨 BÖLÜM 3: RENK KARAKTERİSTİĞİ"
          - Tablo: | Renk Tonu | Psikolojik Etkisi | En Çok Kullanılan Parça | Kombin |

       B) EĞER KONU "KUMAŞ" İSE:
          - Başlık: "## 🧵 BÖLÜM 3: KUMAŞ ANALİZİ"
          - Tablo: | Kumaş Tipi | Mevsim | Maliyet | Kullanım Alanı |

       C) EĞER KONU "ÜRÜN" İSE:
          - Başlık: "## 💰 BÖLÜM 3: FİYAT ANALİZİ"
          - Tablo: | Segment | Min Fiyat | Max Fiyat | Ort. Fiyat |

    3. **GÖRSEL YER TUTUCULARI ([[VISUAL_CARD_x]]):**
       - Bölüm 4'te her maddenin ALTINA [[VISUAL_CARD_x]] ekle.
       - Madde başlığı ve açıklamasından SONRA gelmeli.

    RAPOR ŞABLONU:
    # 💎 [KONU] - 2026 VİZYON RAPORU

    ## 🌍 BÖLÜM 1: GLOBAL DEFİLE İZLERİ
    (Analiz...)
    [[RUNWAY_VISUAL_1]]
    [[RUNWAY_VISUAL_2]]

    ## 📈 BÖLÜM 1.1: SOSYAL MEDYA
    (Analiz...) 

    ## 📈 BÖLÜM 2: TİCARİ TRENDLER
    (Analiz...) 

    [DİNAMİK BÖLÜM 3 BAŞLIĞI]
    [DİNAMİK TABLO]

    [DİNAMİK BÖLÜM 4 BAŞLIĞI]
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
            model="gemini-2.5-flash",
            messages=[
                {"role": "system", "content": formatted_prompt},
                {"role": "user", "content": f"VERİ:\n{research_data}"}
            ],
            temperature=0.4
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Rapor oluşturma hatası: {e}")
        return "Rapor oluşturulurken bir hata meydana geldi."