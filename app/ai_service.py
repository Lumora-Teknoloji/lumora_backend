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
# 2. GELİŞMİŞ PAZAR VE PSİKOLOJİ ARAŞTIRMASI
# -----------------------------------------------------------------------------

def deep_market_research(topic: str) -> Dict[str, Any]:
    """
    Segment verisi, Trend Nedenleri (Why) ve Görselleri toplar.
    """
    if not tavily_client:
        return {"context": "Hata: Tavily Client yok.", "market_images": []}

    logger.info(f"🔍 Derin Analiz Başlıyor: {topic}")

    # SORGULARI STRATEJİK OLARAK BÖLÜYORUZ
    queries = [
        # A. TREND NEDENLERİ (PSİKOLOJİ & KÜLTÜR) - YENİ
        f"why is {topic} trending 2025 consumer psychology social media impact",
        f"{topic} modasını etkileyen diziler ve akımlar 2025",

        # B. SEGMENT VE FİYAT (TİCARİ)
        f"{topic} en çok satan modeller ve fiyatları trendyol modanisa",  # Orta
        f"{topic} luxury design price trends vakko beymen",  # Üst
        f"{topic} ucuz toptan fiyatları merter osmanbey",  # İmalat/Alt

        # C. KUMAŞ VE TEKNİK DETAY (İMALAT)
        f"{topic} 2025 fabric trends material details wgsn"
    ]

    context_data = "### MARKET INTELLIGENCE DATA ###\n"
    market_images = []

    try:
        all_results = []
        # Her sorguyu çalıştır
        for q in queries:
            response = tavily_client.search(
                query=q,
                search_depth="advanced",
                include_images=True,
                max_results=3
            )
            all_results.extend(response.get('results', []))

            # Görselleri topla
            raw_imgs = response.get('images', [])
            # Sadece geçerli ve temiz linkleri al
            valid_imgs = [img for img in raw_imgs if img and img.startswith("http")]
            market_images.extend(valid_imgs)

        # 1. Metin Verilerini İşle
        for i, res in enumerate(all_results):
            context_data += f"- KAYNAK: {res['title']}\n"
            context_data += f"- BİLGİ: {res['content']}\n"
            context_data += f"- URL: {res['url']}\n\n"

        # 2. Görselleri İŞLENMİŞ olarak LLM'e sun
        # LLM'in resmi "görmesi" için URL'in temiz olması lazım.
        context_data += "### KULLANILABİLİR GÖRSEL HAVUZU ###\n"
        unique_images = list(set(market_images))[:10]  # Tekrarları sil ve ilk 10'u al

        for i, img in enumerate(unique_images):
            context_data += f"IMG_{i + 1}: {img}\n"

        return {"context": context_data, "market_images": unique_images}

    except Exception as e:
        logger.error(f"Araştırma Hatası: {e}")
        return {"context": f"Hata: {e}", "market_images": []}


# -----------------------------------------------------------------------------
# 3. İMALATÇI ODAKLI RAPORLAMA (MANTIKLI EŞLEŞTİRME İLE)
# -----------------------------------------------------------------------------

def generate_strategic_report(user_message: str, research_data: str) -> str:
    """
    İmalatçıya özel, maliyet hesaplı ve 'Neden' analizi içeren rapor.
    """
    system_prompt = """
    Sen Kıdemli Tekstil Mühendisi ve Moda Stratejistisin.

    GÖREVİN:
    Üreticiye 2025/2026 için **Veri Odaklı İmalat Raporu** hazırlamak.

    ⚠️ KRİTİK GÖRSEL KURALI:
    Sana 'IMG_' ile başlayan görsel linkleri verildi.
    Eğer bir modeli anlatırken görsel kullanacaksan, **LİNKİN İÇERİĞİNİ TAHMİN ETMEYE ÇALIŞMA.**
    Sadece linkin yapısından veya bağlamından %100 eminsen o linki kullan. 
    Emin değilsen görsel koyma, "Görsel Referansı: Pazar Araştırması Eki" yaz geç. 
    **Yanlış görsel koymak, hiç görsel koymamaktan kötüdür.**

    ⚠️ İMALAT VE MALİYET KURALI:
    Üretim maliyetini (Target Cost) şöyle hesapla:
    Bulduğun Raf Fiyatı (Perakende) / 4 = Tahmini Üretim Maliyeti.
    (Örn: 2000 TL satış fiyatı varsa, hedef maliyet 500 TL olmalıdır).

    RAPOR FORMATI (Markdown):

    # 🏭 [KONU] - 2025/2026 STRATEJİK İMALAT DOSYASI

    ## 📈 BÖLÜM 1: TREND SÜRÜCÜLERİ (NEDEN BU TREND VAR?)
    *(Burada 'Why Trending' sorgularından gelen veriyi kullan)*
    * **Psikolojik Neden:** (Örn: İnsanların kaçış psikolojisi, nostalji...)
    * **Kültürel Etki:** (Örn: Popüler diziler, TikTok akımları...)
    * **Ekonomik Faktör:** (Örn: "Sessiz Lüks" gibi kalıcı parça arayışı...)

    ## 💰 BÖLÜM 2: SEGMENT VE FİYAT ANALİZİ
    | Segment | Ortalama Raf Fiyatı | Hedef İmalat Maliyeti (Fiyat/4) | Kumaş & İşçilik Notu |
    | :--- | :--- | :--- | :--- |
    | Giriş (Alt) | ... TL | ... TL | (Örn: Polyester karışımlı) |
    | Orta (Hacim) | ... TL | ... TL | (Örn: Yerli krep/şifon) |
    | Üst (Lüks) | ... TL | ... TL | (Örn: İthal kumaş, ağır işçilik) |

    ## 🏆 BÖLÜM 3: ÜRETİLECEK TOP 5 MODEL (BEST SELLERS)

    ### 1. [Ticari Model Adı]
    * **Tasarım:** (Net imalat tarifi)
    * **Kumaş:** (Gramaj ve tür ver)
    * **Hedef Segment:** ...

    > **🛍️ PAZAR VERİSİ**
    > * **Benzer Rakip Fiyatı:** ... TL
    > * **Bizim Hedef Maliyetimiz:** ... TL (Maksimum)
    > * **Referans Görsel:** (Eğer emin olduğun bir IMG linki varsa buraya koy: ![Ref](URL) - Yoksa boş bırak)

    ...(Diğer Modeller)...

    ## 🔗 REFERANSLAR
    * [Site Adı](URL)
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"KONU: {user_message}\n\nVERİLER:\n{research_data}"}
            ],
            temperature=0.6  # Daha tutarlı olması için düşürdük
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Rapor Hatası: {e}"


# -----------------------------------------------------------------------------
# 4. GÖRSEL PROMPT (SDXL)
# -----------------------------------------------------------------------------
# (Bu kısım aynı kalabilir, görsel üretimi opsiyonel olduğu için)
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
    # (Replicate kodu buraya)
    return []


# -----------------------------------------------------------------------------
# 5. ANA ORKESTRASYON
# -----------------------------------------------------------------------------

async def generate_ai_response(user_message: str, generate_images: bool = False) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()

    # 1. Araştırma
    research_result = await loop.run_in_executor(None, deep_market_research, user_message)

    # 2. Raporlama
    final_report = await loop.run_in_executor(None, generate_strategic_report, user_message, research_result["context"])

    # 3. Görsel Üretim (Opsiyonel)
    ai_generated_urls = []
    if generate_images or any(x in user_message.lower() for x in ["çiz", "görsel", "tasarım"]):
        prompts = await loop.run_in_executor(None, generate_image_prompts, final_report)
        ai_generated_urls = await loop.run_in_executor(None, generate_ai_images, prompts)

    # 4. Frontend Galerisi (Burada tüm resimleri galeri olarak sunmak en güvenlisidir)
    combined_images = research_result["market_images"] + ai_generated_urls

    return {
        "content": final_report,
        "image_urls": combined_images,
        "process_log": [
            "Trend psikolojisi ve nedenleri analiz edildi.",
            "Raf fiyatlarından hedef imalat maliyetleri hesaplandı.",
            f"{len(research_result['market_images'])} adet referans görsel bulundu."
        ]
    }