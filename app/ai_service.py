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
# 2. NİYET ANALİZİ VE SOHBET MODÜLÜ
# -----------------------------------------------------------------------------

def analyze_user_intent(message: str) -> str:
    """
    Kullanıcının mesajı bir 'Sohbet/Sorgu' mu yoksa 'Pazar Araştırması' mı?
    """
    if not openai_client: return "MARKET_RESEARCH"

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system",
                 "content": "You are a classifier. Classify the user input into 'GENERAL_CHAT' or 'MARKET_RESEARCH'. Return ONLY the category name."},
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
    GÖREVİN: Kullanıcının sorusuna profesyonel, güven veren bir dille cevap ver.
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
    Linkleri bozmadan toplamak için optimize edildi.
    """
    if not tavily_client:
        return {"context": "Hata: Tavily Client yok.", "market_images": []}

    logger.info(f"🔍 Derin Pazar ve Ürün Analizi: {topic}")

    queries = [
        # A. TREND NEDENLERİ
        f"why is {topic} trending 2025 consumer psychology",

        # B. TİCARİ ÜRÜN ARAMASI (Direkt Ürün Sayfalarını Hedefle)
        # "ürün detayı" kelimesi ekleyerek kategori sayfalarından kaçmaya çalışıyoruz
        f"{topic} ürün detayı satın al trendyol",
        f"{topic} abiye elbise satın al modanisa fiyat",
        f"{topic} modelleri ve fiyatları hepsiburada",

        # C. LÜKS VE İMALAT
        f"{topic} luxury design price vakko beymen",
        f"{topic} 2025 fabric trends wgsn"
    ]

    context_data = "### MARKET DATA & PRODUCT LINKS ###\n"
    market_images = []

    try:
        all_results = []
        for q in queries:
            response = tavily_client.search(
                query=q,
                search_depth="advanced",
                include_images=True,
                max_results=4
            )
            all_results.extend(response.get('results', []))

            raw_imgs = response.get('images', [])
            valid_imgs = [img for img in raw_imgs if img and img.startswith("http")]
            market_images.extend(valid_imgs)

        # 1. Metin Verilerini İşle (Linkleri ID ile etiketle)
        for i, res in enumerate(all_results):
            # Sadece geçerli HTTP linklerini alıyoruz
            url = res.get('url', '')
            if not url.startswith('http'): continue

            context_data += f"--- SONUÇ ID: {i + 1} ---\n"
            context_data += f"BAŞLIK: {res['title']}\n"
            context_data += f"İÇERİK: {res['content']}\n"
            context_data += f"TAM_URL: {url}\n\n"  # "TAM_URL" etiketiyle LLM'e işaret ediyoruz

        context_data += "### PAZAR GÖRSEL HAVUZU ###\n"
        unique_images = list(set(market_images))[:12]

        for i, img in enumerate(unique_images):
            context_data += f"IMG_REF_{i + 1}: {img}\n"

        return {"context": context_data, "market_images": unique_images}

    except Exception as e:
        logger.error(f"Araştırma Hatası: {e}")
        return {"context": f"Hata: {e}", "market_images": []}


# -----------------------------------------------------------------------------
# 4. STRATEJİK İMALAT RAPORU (LİNK KORUMALI)
# -----------------------------------------------------------------------------

def generate_strategic_report(user_message: str, research_data: str) -> str:
    system_prompt = """
    Sen Kıdemli Moda Stratejistisin.

    GÖREVİN:
    Üreticiye 2025/2026 sezonu için **GERÇEKÇİ FİYAT ARALIKLARI** ve **ÇALIŞAN LİNKLERLE RAKİP ANALİZİ** sunan rapor hazırla.

    ⚠️ 1. LİNK KURALI (HAYATİ ÖNEMLİ):
    - Bölüm 4'te ürünleri listelerken, 'MARKET DATA' içinde 'TAM_URL:' etiketli satırı bul.
    - O URL'yi **HARFİ HARFİNE, HİÇ DEĞİŞTİRMEDEN** kopyala.
    - Asla linki kısaltma (.... koyma).
    - Asla link uydurma.
    - Eğer URL yoksa o ürünü listeye koyma.

    ⚠️ 2. FİYAT VE MALİYET KURALI:
    - Fiyatları TEK RAKAM verme, ARALIK ver (Örn: "1.200 TL - 1.800 TL").
    - Hedef İmalat Maliyeti = (Fiyat Aralığının Ortalaması) / 4.

    RAPOR FORMATI (Markdown):

    # 🏭 [KONU] - 2025/2026 STRATEJİK İMALAT DOSYASI

    ## 📈 BÖLÜM 1: TREND TETİKLEYİCİLERİ (NEDEN ŞİMDİ?)
    * **Popüler Kültür:** (Dizi, TikTok akımı vb.)
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
    *(Bulduğun, linki çalışan gerçek ürünleri listele)*

    ### 🛒 Rakip 1: [Ürün Başlığı]
    * **Fiyat:** ... TL
    * **Site:** [Trendyol/Modanisa vb.]
    * **Ürüne Git:** [👉 Ürünü İncele](BURAYA_TAM_URL_GELECEK_ASLA_KISALTMA)
    * **Görsel:** ![Görsel](IMG_REF_LINKI_EGER_VARSA)

    ### 🛒 Rakip 2: [Ürün Başlığı]
    * **Fiyat:** ... TL
    * **Site:** ...
    * **Ürüne Git:** [👉 Ürünü İncele](BURAYA_TAM_URL_GELECEK_ASLA_KISALTMA)
    * **Görsel:** ![Görsel](IMG_REF_LINKI_EGER_VARSA)

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
            temperature=0.4  # Link hatasını önlemek için sıcaklığı düşürdüm
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
    return []


# -----------------------------------------------------------------------------
# 6. ANA ORKESTRASYON
# -----------------------------------------------------------------------------

async def generate_ai_response(user_message: str, generate_images: bool = False) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()

    # ADIM 1: Niyet Analizi
    intent = await loop.run_in_executor(None, analyze_user_intent, user_message)

    if intent == "GENERAL_CHAT":
        chat_response = await loop.run_in_executor(None, handle_general_chat, user_message)
        return {
            "content": chat_response,
            "image_urls": [],
            "process_log": ["Sohbet modu aktif."]
        }

    # ADIM 2: Araştırma
    research_result = await loop.run_in_executor(None, deep_market_research, user_message)

    # ADIM 3: Raporlama
    final_report = await loop.run_in_executor(None, generate_strategic_report, user_message, research_result["context"])

    # ADIM 4: Görsel (Opsiyonel)
    ai_generated_urls = []
    if generate_images or any(x in user_message.lower() for x in ["çiz", "görsel", "tasarım"]):
        prompts = await loop.run_in_executor(None, generate_image_prompts, final_report)
        ai_generated_urls = await loop.run_in_executor(None, generate_ai_images, prompts)

    combined_images = research_result["market_images"] + ai_generated_urls

    return {
        "content": final_report,
        "image_urls": combined_images,
        "process_log": [
            "Fiyat aralıkları (Min-Max) analiz edildi.",
            f"{len(research_result['market_images'])} adet ürün görseli ve çalışan link toplandı."
        ]
    }