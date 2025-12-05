import os
import logging
import asyncio
import requests
import uuid
import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
from tavily import TavilyClient
from .config import settings

# Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# 1. BAŞLATMA
# -----------------------------------------------------------------------------
openai_client: Optional[OpenAI] = None
tavily_client: Optional[TavilyClient] = None


def initialize_ai_clients():
    global openai_client, tavily_client
    try:
        if settings.openai_api_key:
            openai_client = OpenAI(api_key=settings.openai_api_key)
            logger.info("✅ OpenAI Hazır")
        if settings.tavily_api_key:
            tavily_client = TavilyClient(api_key=settings.tavily_api_key)
            logger.info("✅ Tavily Hazır")
    except Exception as e:
        logger.error(f"❌ Başlatma Hatası: {e}")


initialize_ai_clients()


# -----------------------------------------------------------------------------
# 2. NİYET ANALİZİ VE SOHBET MODÜLÜ (YENİ EKLENEN KISIM)
# -----------------------------------------------------------------------------

def analyze_user_intent(message: str) -> str:
    """
    Kullanıcının mesajı bir 'Sohbet/Sorgu' mu yoksa 'Pazar Araştırması' mı?
    """
    if not openai_client: return "MARKET_RESEARCH"  # Varsayılan

    try:
        # Basit bir sınıflandırma yapıyoruz
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system",
                 "content": "You are a classifier. Classify the user input into 'GENERAL_CHAT' (greetings, who are you, capabilities, accuracy, source questions, casual talk) or 'MARKET_RESEARCH' (asking for trends, prices, fashion advice, products, analysis). Return ONLY the category name."},
                {"role": "user", "content": message}
            ],
            temperature=0.0
        )
        return response.choices[0].message.content.strip()
    except:
        return "MARKET_RESEARCH"


def handle_general_chat(message: str) -> str:
    """
    Kullanıcının kimlik, yetenek ve doğruluk ile ilgili sorularını yanıtlar.
    """
    system_prompt = """
    Sen Kıdemli Moda Stratejisi Asistanısın (AI Fashion Strategist).

    KİMLİĞİN VE YETENEKLERİN:
    1. **Amacın:** Tekstil üreticilerine ve markalara 2025/2026 sezonu için veri odaklı üretim, tasarım ve fiyatlandırma stratejileri sunmak.
    2. **Neler Yapabilirsin:** - Global trendleri (WGSN, Vogue) ve tüketici psikolojisini analiz ederim.
       - Pazar yerlerindeki (Trendyol, Modanisa) gerçek ürünleri ve fiyatları tararım.
       - Üretim maliyetlerini hesaplayıp kâr marjı analizi yaparım.
    3. **Nasıl Çalışırsın:** Ben 'Lumora' arama motorunu kullanarak internetteki CANLI verileri (Real-Time Data) tararım. Ezberden konuşmam, o an piyasada ne varsa onu raporlarım.
    4. **Doğruluk Oranın:** Canlı web verilerine ve gerçek pazar listelerine dayandığım için analizlerim güncel ve yüksek doğrulukludur. Ancak nihai ticari risk ve karar her zaman kullanıcıya aittir.
    5. **Kaynakların:** Verileri Vogue, WGSN, Trendyol, Modanisa, Hepsiburada, Pinterest ve global moda yayınlarından anlık olarak çekerim.

    GÖREVİN:
    Kullanıcının sorusuna bu kimliğe uygun, profesyonel, güven veren ve yardımsever bir dille cevap ver.
    Eğer "Naber" gibi basit bir selam verdiyse, kendini tanıt ve "Sizin için hangi ürün grubunu analiz etmemi istersiniz?" diye sor.
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return "Üzgünüm, şu an yanıt veremiyorum."


# -----------------------------------------------------------------------------
# 3. DERİN PAZAR ARAŞTIRMASI (ARAŞTIRMA MODU)
# -----------------------------------------------------------------------------

def deep_market_research(topic: str) -> Dict[str, Any]:
    """
    Segment verisi, Trend Nedenleri ve KONKRET ÜRÜN verilerini toplar.
    """
    if not tavily_client:
        return {"context": "Hata: Tavily Client yok.", "market_images": []}

    logger.info(f"🔍 Derin Pazar ve Ürün Analizi: {topic}")

    queries = [
        # A. TREND NEDENLERİ
        f"why is {topic} trending 2025 consumer psychology",

        # B. TİCARİ ÜRÜN ARAMASI
        f"{topic} fiyatları satın al trendyol en çok satanlar",
        f"{topic} modelleri ve fiyatları modanisa sefamerve",
        f"{topic} abiye fiyatları hepsiburada",

        # C. LÜKS VE İMALAT
        f"{topic} luxury design price vakko beymen",
        f"{topic} 2025 fabric trends wgsn"
    ]

    context_data = "### MARKET DATA & PRODUCT LISTINGS ###\n"
    market_images = []

    try:
        all_results = []
        for q in queries:
            response = tavily_client.search(
                query=q,
                search_depth="advanced",
                include_images=True,
                max_results=3
            )
            all_results.extend(response.get('results', []))

            raw_imgs = response.get('images', [])
            valid_imgs = [img for img in raw_imgs if img and img.startswith("http")]
            market_images.extend(valid_imgs)

        for i, res in enumerate(all_results):
            context_data += f"--- ARAMA SONUCU {i + 1} ---\n"
            context_data += f"BAŞLIK: {res['title']}\n"
            context_data += f"METİN (Fiyat/Ürün Bul): {res['content']}\n"
            context_data += f"LİNK: {res['url']}\n\n"

        context_data += "### PAZAR GÖRSEL HAVUZU ###\n"
        unique_images = list(set(market_images))[:12]

        for i, img in enumerate(unique_images):
            context_data += f"IMG_REF_{i + 1}: {img}\n"

        return {"context": context_data, "market_images": unique_images}

    except Exception as e:
        logger.error(f"Araştırma Hatası: {e}")
        return {"context": f"Hata: {e}", "market_images": []}


# -----------------------------------------------------------------------------
# 4. STRATEJİK İMALAT RAPORU (ARAŞTIRMA MODU)
# -----------------------------------------------------------------------------

def generate_strategic_report(user_message: str, research_data: str) -> str:
    system_prompt = """
    Sen Kıdemli Moda Stratejistisin.

    GÖREVİN:
    Üreticiye 2025/2026 sezonu için **GERÇEKÇİ FİYAT ARALIKLARI** ve **RAKİP ANALİZİ** sunan rapor hazırla.

    ⚠️ 1. FİYAT ARALIĞI KURALI:
    'MARKET DATA' içindeki rakamları tara. Asla tek fiyat verme, ARALIK ver (Örn: "1.200 TL - 1.800 TL").

    ⚠️ 2. İMALAT MALİYETİ KURALI:
    Hedef İmalat Maliyeti = (Fiyat Aralığının Ortalaması) / 4.

    ⚠️ 3. CANLI VİTRİN KURALI:
    Bölüm 4'te arama sonuçlarında bulduğun GERÇEK ürünleri (Fiyat, Link, Resim) listele.

    RAPOR FORMATI (Markdown):

    # 🏭 [KONU] - 2025/2026 STRATEJİK İMALAT DOSYASI

    ## 📈 BÖLÜM 1: TREND TETİKLEYİCİLERİ (NEDEN ŞİMDİ?)
    * **Popüler Kültür / Sosyal Medya:** (Dizi, TikTok akımı vb.)
    * **Tüketici Psikolojisi:** ...

    ## 💰 BÖLÜM 2: DETAYLI SEGMENT VE FİYAT ANALİZİ
    | Segment | Pazar Fiyat Aralığı (Min - Max) | Hedef İmalat Maliyeti (~1/4) | Kumaş & Kalite |
    | :--- | :--- | :--- | :--- |
    | **Giriş (Pazaryeri)** | ... - ... TL | ... TL | (Örn: Polyester) |
    | **Orta (Markalı)** | ... - ... TL | ... TL | (Örn: Krep, Astarlı) |
    | **Üst (Lüks)** | ... - ... TL | ... TL | (Örn: İpek, Tasarım) |

    ## 🏆 BÖLÜM 3: ÜRETİLECEK TOP 5 MODEL
    ### 1. [Model Adı]
    * **Tasarım:** ...
    * **Kumaş:** ...
    * **Pazar Referansı:** (Varsa IMG_REF: ![Ref](IMG_REF_LINKI))

    ...(Diğer Modeller)...

    ## 🛍️ BÖLÜM 4: SAHADA SATILAN RAKİP ÜRÜNLER (CANLI VİTRİN)
    *(Bulduğun gerçek ürünleri listele)*

    ### 🛒 Rakip 1: [Ürün Adı]
    * **Fiyat:** ... TL
    * **Site:** [Trendyol/Modanisa vb.]
    * **Link:** [Ürüne Git](URL)
    * **Görsel:** ![Görsel](IMG_REF_LINKI_EGER_VARSA)

    ...(Diğer Rakipler)...

    ## 🔗 KAYNAKÇA
    * [Site Adı](URL)
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"KONU: {user_message}\n\nVERİLER:\n{research_data}"}
            ],
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Rapor Hatası: {e}"


# -----------------------------------------------------------------------------
# 5. GÖRSEL PROMPT (OPSİYONEL)
# -----------------------------------------------------------------------------
def generate_image_prompts(analysis_text: str) -> List[str]:
    system_prompt = "You are an AI Fashion Designer. Extract top 3 models and create prompts."
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": analysis_text}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content).get("prompts", [])
    except:
        return []


def generate_ai_images(prompts: List[str]) -> List[str]:
    # Replicate entegrasyonu buraya
    return []


# -----------------------------------------------------------------------------
# 6. ANA ORKESTRASYON (AKILLI YÖNLENDİRME)
# -----------------------------------------------------------------------------

async def generate_ai_response(user_message: str, generate_images: bool = False) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()

    # ADIM 1: Niyet Analizi (Bu soru araştırma mı yoksa sohbet mi?)
    intent = await loop.run_in_executor(None, analyze_user_intent, user_message)

    # SENARYO A: NORMAL SOHBET (Naber, Kimsin, Kaynakların ne?)
    if intent == "GENERAL_CHAT":
        chat_response = await loop.run_in_executor(None, handle_general_chat, user_message)
        return {
            "content": chat_response,
            "image_urls": [],
            "process_log": ["Kullanıcı niyeti: Genel Sohbet", "Asistan kimliği ile yanıtlandı."]
        }

    # SENARYO B: PAZAR ARAŞTIRMASI (Abiye trendleri, Fiyat analizi vb.)
    # 2. Derin Araştırma
    research_result = await loop.run_in_executor(None, deep_market_research, user_message)

    # 3. Raporlama
    final_report = await loop.run_in_executor(None, generate_strategic_report, user_message, research_result["context"])

    # 4. Görsel Tasarım (Opsiyonel)
    ai_generated_urls = []
    if generate_images or any(x in user_message.lower() for x in ["çiz", "görsel", "tasarım"]):
        prompts = await loop.run_in_executor(None, generate_image_prompts, final_report)
        ai_generated_urls = await loop.run_in_executor(None, generate_ai_images, prompts)

    combined_images = research_result["market_images"] + ai_generated_urls

    return {
        "content": final_report,
        "image_urls": combined_images,
        "process_log": [
            "Kullanıcı niyeti: Pazar Araştırması",
            "Fiyat aralıkları ve trend nedenleri analiz edildi.",
            f"{len(research_result['market_images'])} adet referans görsel toplandı."
        ]
    }