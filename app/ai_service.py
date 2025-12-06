import os
import logging
import asyncio
import requests
import time
import uuid
import json
import re
from typing import List, Dict, Any, Optional
from openai import OpenAI
from tavily import TavilyClient
from .config import settings
try:
    import fal_client  # type: ignore
except Exception:
    fal_client = None

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


# Yardımcı: HTTP olmayan markdown image'larını temizle
def _remove_non_http_images(markdown_text: str) -> str:
    """
    IMG_REF_* gibi placeholder linklerden kaynaklanan kırık görselleri temizler.
    """
    pattern = r'!\[[^\]]*\]\((?!https?://)[^)]+\)'
    return re.sub(pattern, '', markdown_text)


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
def generate_image_prompts(analysis_text: str) -> List[Dict[str, str]]:
    """
    Rapor içindeki model isimlerini ve IMG_REF kimliklerini yakalayıp
    her biri için görsel üretim promptu döner.
    """
    system_prompt = """
    You are an AI Fashion Designer.
    Extract up to 5 model concepts from the report.
    For each concept return:
    - model_name: a short name from the report (reuse existing wording)
    - ref_id: the IMG_REF_* token nearest to that model if present (e.g., IMG_REF_1).
              If none is present, leave it empty.
    - prompt: vivid English prompt describing the garment for a diffusion model
    Return JSON: {"items": [{"model_name": "...", "ref_id": "IMG_REF_1", "prompt": "..."}]}
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": analysis_text}],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return data.get("items", [])
    except Exception as e:
        logger.error(f"Görsel prompt çıkarma hatası: {e}")
        return []


def generate_ai_images(prompt_items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    FAL (flux2-pro) üzerinden görsel üretir. Key yoksa boş döner.
    """
    api_key = settings.fal_api_key
    if not api_key:
        logger.info("❕ FAL_API_KEY yok, görsel üretimi atlanıyor.")
        return []

    base_url = getattr(settings, "fal_base_url", "https://fal.run").rstrip("/")
    model_path = getattr(settings, "fal_model_path", "fal-ai/flux/dev").strip("/")
    run_url = f"{base_url}/{model_path}"
    poll_url = f"{base_url}/{model_path}"  # request_id eklenecek

    # fal_client varsa resmi SDK ile kullan, yoksa HTTP fallback
    use_sdk = fal_client is not None
    if use_sdk:
        os.environ["FAL_KEY"] = api_key

    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json",
    }

    def _run_prompt(prompt: str) -> Optional[str]:
        # Önce SDK dene, hata olursa HTTP fallback
        if use_sdk:
            try:
                handler = fal_client.submit(
                    model_path,
                    arguments={
                        "prompt": prompt,
                        "num_images": 1,
                    },
                )
                result = handler.get()
                images = result.get("images") or result.get("output", {}).get("images")
                if images:
                    first = images[0]
                    if isinstance(first, dict):
                        return first.get("url")
                    return first
            except Exception as e:
                logger.error(f"FAL SDK hata: {e}. HTTP fallback deneniyor. prompt='{prompt[:80]}'")

        try:
            run_resp = requests.post(
                run_url,
                headers=headers,
                json={"prompt": prompt},
                timeout=30,
            )
            run_resp.raise_for_status()
            data = run_resp.json()

            # Bazı modeller direkt images döndürüyor (request_id olmadan)
            direct_images = data.get("images") or data.get("output", {}).get("images")
            if direct_images:
                first = direct_images[0]
                if isinstance(first, dict):
                    url = first.get("url")
                    if url:
                        return url
                elif isinstance(first, str):
                    return first

            req_id = data.get("request_id")
            if not req_id:
                logger.error(f"FAL run yanıtında request_id yok. Yanıt: {run_resp.text[:200]}")
                return None

            # Poll result
            for _ in range(15):  # ~30s max (2s * 15)
                time.sleep(2)
                res = requests.get(f"{poll_url}/{req_id}", headers=headers, timeout=20)
                if res.status_code == 404:
                    logger.error("FAL poll 404 - endpoint veya model yolu hatalı.")
                    break
                res.raise_for_status()
                data = res.json()
                status = data.get("status")
                if status == "COMPLETED":
                    images = data.get("images") or data.get("output", {}).get("images")
                    if images:
                        # image can be dict with url or direct url list
                        if isinstance(images, list):
                            first = images[0]
                            if isinstance(first, dict):
                                return first.get("url")
                            return first
                    break
                if status in ("FAILED", "CANCELLED"):
                    break
            return None
        except Exception as e:
            logger.error(f"FAL görsel üretim hatası: {e}")
            return None

    results: List[Dict[str, str]] = []
    for item in prompt_items[:5]:  # en fazla 5 görsel
        prompt = item.get("prompt")
        if not prompt:
            continue
        logger.info(f"FAL görsel isteği: {prompt[:80]}...")
        url = _run_prompt(prompt)
        if url:
            results.append({
                "model_name": item.get("model_name", "").strip(),
                "ref_id": item.get("ref_id", "").strip(),
                "url": url
            })
        else:
            logger.error("FAL görsel isteği başarısız (URL alınamadı).")
    return results


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
    ref_lookup = {f"IMG_REF_{i + 1}": img for i, img in enumerate(research_result["market_images"])}

    ai_generated_items: List[Dict[str, str]] = []
    image_triggers = ["çiz", "görsel", "tasarım", "resim", "resimler", "foto", "fotoğraf", "image", "picture", "draw"]
    # Talep üzerine market researchte her zaman görsel üret, fal_api_key varsa
    should_generate_images = True if settings.fal_api_key else (generate_images or any(x in user_message.lower() for x in image_triggers))
    ref_ids_ordered = list(ref_lookup.keys())

    if should_generate_images:
        prompt_items = await loop.run_in_executor(None, generate_image_prompts, final_report)
        logger.info(f"Görsel prompt sayısı: {len(prompt_items)}")

        # Prompt çıkarılamazsa basit bir fallback prompt ekle
        if not prompt_items:
            prompt_items = [{
                "model_name": (user_message[:50] or "AI Model").strip(),
                "ref_id": ref_ids_ordered[0] if ref_lookup else "",
                "prompt": f"High-quality fashion product photo, {user_message}, studio lighting, 4k, detailed fabric texture"
            }]
            logger.info("Prompt bulunamadı, fallback prompt ile görsel üretilecek.")

        # Her promptu en yakın pazar referansıyla eşleştir (yoksa sırayla ata)
        normalized_prompts: List[Dict[str, str]] = []
        for idx, item in enumerate(prompt_items):
            ref_id = (item.get("ref_id") or (ref_ids_ordered[idx % len(ref_ids_ordered)] if ref_ids_ordered else "")).strip()
            normalized_prompts.append({
                "model_name": item.get("model_name", "").strip(),
                "ref_id": ref_id,
                "prompt": item.get("prompt", "").strip()
            })

        ai_generated_items = await loop.run_in_executor(None, generate_ai_images, normalized_prompts)
        logger.info(f"Üretilen AI görsel adedi: {len(ai_generated_items)}")
    else:
        logger.info("Görsel üretimi atlandı (tetikleyici kelime yok veya generate_images=False).")

    # Pazar referansı altına AI görsellerini yerleştir
    paired_blocks: List[str] = []
    for ref_id, ref_url in ref_lookup.items():
        block = f"#### {ref_id}\n- Pazar Referansı: ![]({ref_url})"
        matches = [m for m in ai_generated_items if m.get("ref_id") == ref_id and m.get("url")]
        for m in matches:
            model_name = m.get("model_name") or "AI Model"
            block += f"\n- Önerimiz ({model_name}): ![]({m['url']})"
        paired_blocks.append(block)

    pairing_section = ""
    if paired_blocks:
        pairing_section = "\n\n### Pazar Referansı + AI Model Görselleri\n" + "\n\n".join(paired_blocks)
    elif ai_generated_items:
        # Tavily kota hatası vb. durumlarda pazar referansı yoksa bile AI görsellerini göster
        ai_only = []
        for m in ai_generated_items:
            url = m.get("url")
            if not url:
                continue
            model_name = m.get("model_name") or "AI Model"
            ai_only.append(f"- Önerimiz ({model_name}): ![]({url})")
        if ai_only:
            pairing_section = "\n\n### AI Model Görselleri\n" + "\n".join(ai_only)

    combined_report = _remove_non_http_images(final_report + pairing_section)

    ai_generated_urls_only = [m["url"] for m in ai_generated_items if m.get("url")]
    combined_images = research_result["market_images"] + ai_generated_urls_only

    return {
        "content": combined_report,
        "image_urls": combined_images,
        "process_log": [
            "Fiyat aralıkları (Min-Max) analiz edildi.",
            f"{len(research_result['market_images'])} adet ürün görseli ve çalışan link toplandı."
        ]
    }