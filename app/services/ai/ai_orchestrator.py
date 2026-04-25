"""
Orchestrator - Ana AI yanıt üretimi orkestrasyonu
"""
import asyncio
import logging
import re
import secrets
from typing import List, Dict, Any
from app.services.core.clients import openai_client
from app.services.ai.intent import analyze_user_intent, handle_general_chat, handle_follow_up, extract_category_from_message, extract_production_parameters
from app.services.ai.database_query import handle_database_query
import json
from app.services.intelligence.intelligence_formatter import get_intelligence_context, get_structured_intelligence_context, format_structured_report
from app.services.intelligence.intelligence_client import intelligence_client
from app.services.ai.semantic_matcher import semantic_match_and_rank
from app.services.data.research import (
    generate_strategic_report,
    find_visual_match_for_model,
    extract_visual_search_terms
)
from app.services.data.trends import get_google_trends, format_trends_for_report
from app.services.ai.image_gen_service import (
    generate_image_prompts,
    generate_ai_images,
    _remove_non_http_images,
    enhance_follow_up_prompt,
    extract_image_request,
    extract_previous_image_context,
    modify_image_prompt,
    generate_custom_images
)
from app.core.config import settings

logger = logging.getLogger(__name__)


def check_visual_necessity(user_message: str) -> bool:
    """Kullanıcının görsel isteyip istemediğini kontrol eder"""
    if not openai_client: return False
    system_prompt = "Analyze request: Concrete Fashion Item (Dress, Shoe) -> YES. Abstract (Color, Fabric) -> NO. Reply YES/NO."
    try:
        response = openai_client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
            max_tokens=5, temperature=0.0
        )
        return "YES" in response.choices[0].message.content.upper()
    except: return False


def check_report_content_for_visuals(report_text: str) -> bool:
    """Rapor içeriğinde görsel gerektiren öğeler olup olmadığını kontrol eder"""
    concrete_triggers = ["elbise", "ceket", "pantolon", "etek", "gömlek", "bluz", "tulum", "ayakkabı", "çanta", "dress", "sandalet", "kombin"]
    text_lower = report_text.lower()
    for word in concrete_triggers:
        if word in text_lower: return True
    return False


async def generate_ai_response(
    user_message: str,
    chat_history: List[Dict[str, str]] = [],
    generate_images: bool = False,
    stream_callback: Any = None
) -> Dict[str, Any]:
    """
    Ana AI yanıt üretimi fonksiyonu
    Kullanıcı mesajını analiz eder ve uygun yanıtı üretir
    """
    loop = asyncio.get_event_loop()
    fallback_warning = False

    # Niyet analizi
    if generate_images:
        intent = "IMAGE_GENERATION"
    else:
        intent = await loop.run_in_executor(None, analyze_user_intent, user_message, chat_history)
    
    logger.info(f"🧠 Niyet: {intent} (Zorunlu Görsel: {generate_images})")

    # --- GENERAL CHAT ---
    if intent == "GENERAL_CHAT":
        # handle_general_chat artık async ve streaming destekliyor + chat_history ile bağlam koruyor
        content = await handle_general_chat(user_message, chat_history, stream_callback)
        return {"content": content, "image_urls": [], "image_links": {}, "process_log": ["Sohbet edildi."]}

    # --- DATABASE_QUERY --- (Veritabanından direkt veri çekimi)
    if intent == "DATABASE_QUERY":
        logger.info("🗄️ DATABASE_QUERY akışı başlatıldı (Doğrudan SQL Çekimi)")
        return await handle_database_query(user_message)

    # --- TREND_ANALYSIS --- (Intelligence servisinden gerçek tahmin verileri)
    if intent == "TREND_ANALYSIS":
        logger.info("📊 TREND_ANALYSIS akışı başlatıldı")

        # 1. Mesajdan detaylı üretim parametreleri çıkar
        params = await loop.run_in_executor(None, extract_production_parameters, user_message)
        category = params.get("product_category")
        target_audience = params.get("target_audience", "Genel")
        gender = params.get("gender", "Genel")
        age_group = params.get("age_group", "Genel")
        seasonality = params.get("seasonality", "Genel")
        material = params.get("material", "Belirtilmedi")
        fit = params.get("fit", "Belirtilmedi")
        length = params.get("length", "Belirtilmedi")
        collar = params.get("collar", "Belirtilmedi")
        sleeve = params.get("sleeve", "Belirtilmedi")
        occasion = params.get("occasion", "Genel")
        budget_segment = params.get("budget_segment", "Genel")
        style_keywords = ", ".join(params.get("style_keywords", [])) or "Belirtilmedi"
        
        logger.info(f"🏷️ Extracted Params: {json.dumps(params, ensure_ascii=False)}")

        # 2. Intelligence servisinden raw tahminleri çek ve Semantic Matcher ile filtrele/sırala
        try:
            predictions = await intelligence_client.predict(category=category, top_n=50)
            matched_predictions, confidence = semantic_match_and_rank(predictions, params)
        except Exception as e:
            logger.warning(f"Intelligence predict veya semantic match hatası: {e}")
            matched_predictions, confidence = [], 0.0

        if confidence >= 20:
            intel_context = format_structured_report(matched_predictions, category=category, params=params)
        else:
            intel_context = ""

        if not intel_context:
            logger.warning(f"İç veri yetersiz (confidence={confidence:.1f}), kullanıcıya veri yok mesajı verilecek.")
            intel_context = "Şu anda veritabanımızda bu filtrelere uygun yeterli ürün veya tahmin verisi bulunmamaktadır. Lütfen kullanıcıya veritabanında veri olmadığını açık ve net bir şekilde belirt. Veri uydurma."

        # 3. Intelligence verileri + GPT-4o = zengin trend raporu
        system_prompt = f"""Sen Kıdemli Moda Analisti, Trend Uzmanı ve Ürün Stratejistisin.
Aşağıda veritabanımızdaki GERÇEK trend verileri var. Tüm yorumların bu verilere dayansın.

{intel_context}

Kullanıcı Profili ve Tasarım Detayları:
- Kategori: {category or 'Tümü'}
- Cinsiyet / Yaş: {gender} / {age_group}
- Hedef Kitle: {target_audience}
- Sezon: {seasonality}
- Kullanım Alanı: {occasion}
- Bütçe/Segment: {budget_segment}
- Stil Anahtar Kelimeleri: {style_keywords}

Tasarımsal Kısıtlamalar:
- Kumaş: {material}
- Kalıp: {fit}
- Boy: {length}
- Yaka: {collar}
- Kol: {sleeve}

GÖREVİN:
Yukarıdaki gerçek verileri kullanarak profesyonel bir trend raporu oluştur.
KESİNLİKLE aşağıdaki Markdown şablonuna uygun yaz:

# 📊 [{category or 'Genel Moda'}] — Sezonluk Üretim Stratejisi

> **AI Öngörüsü:** "[Veriye dayalı 1-2 cümle özet]"

## 1. Pazar Dinamikleri
- Yukarıdaki trend dağılımı ve skorları yorumla
- Kategorinin genel sağlığı hakkında veri destekli yorum

## 2. Üretim Önerileri ({seasonality})
| Özellik | Önerilen | Alternatif |
|:---|:---|:---|
| **Kumaş** | [Veri + {material} bazlı öneri] | [Risk/Niş alternatif] |
| **Kalıp** | [Top ürünlerden çıkan kalıp trendi] | [Farklılaşma önerisi] |
| **Renk** | [Yukarıdaki renk verisinden] | [Cesur seçenek] |

## 3. Fiyatlandırma ({budget_segment})
- Yukarıdaki fiyat dağılımını yorumla
- Hedef kitle ({target_audience}) için konumlandırma önerisi

## 4. Aksiyon Maddeleri
1. [Veri destekli somut tavsiye]
2. [Veri destekli somut tavsiye]
3. [Opsiyonel 3. tavsiye]

KRİTİK KURALLAR:
- Her iddiayı yukarıdaki verilerle destekle (skor, fiyat, renk istatistikleri)
- Top 5 ürün tablosunu doğrudan dahil et
- Hayali veri UYDURMA, sadece verilen istatistikleri kullan"""

        try:
            response = openai_client.chat.completions.create(
                model="gemini-2.5-flash",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.5
            )
            content = response.choices[0].message.content
        except Exception as e:
            logger.error(f"TREND_ANALYSIS GPT hatası: {e}")
            content = f"## 📊 Trend Analizi\n\n{intel_context}\n\n*Detaylı yorum şu an oluşturulamadı.*"

        # --- FAL.AI GÖRSEL ENTEGRASYONU (TREND_ANALYSIS İÇİN) ---
        image_urls = []
        user_needs_visuals = await loop.run_in_executor(None, check_visual_necessity, user_message)
        
        if bool(settings.fal_api_key) and user_needs_visuals and matched_predictions:
            logger.info("TREND_ANALYSIS için Fal.ai görsel üretimi başlatıldı...")
            
            prompt_items = []
            for idx, p in enumerate(matched_predictions[:3], 1):
                name = p.get('name') or "Fashion trend item"
                color = p.get('dominant_color') or ""
                fabric = p.get('fabric_type') or ""
                desc = " ".join([c for c in [color, fabric, name] if c])
                base_prompt = f"Fashion product photography of {desc}"
                enhanced = enhance_follow_up_prompt(base_prompt)
                prompt_items.append({"model_name": name, "prompt": enhanced})
                
            ai_generated = await loop.run_in_executor(None, generate_ai_images, prompt_items)
            
            if ai_generated:
                content += "\n\n### 🎨 AI Tasarım Yorumları (Fal.ai)\n"
                # Resimleri grid mantığına yaklaştırmak için esnek alan
                for item in ai_generated:
                    if item.get("url"):
                        content += f"\n**{item.get('model_name')}:**\n![{item.get('model_name')}]({item['url']})\n"
                        image_urls.append(item["url"])

        return {
            "content": content,
            "image_urls": image_urls,
            "image_links": {},
            "process_log": [f"Intelligence trend analizi tamamlandı (kategori={category or 'hepsi'})."]
        }

    # --- IMAGE_GENERATION durumu - Yeni görsel üretimi ---
    if intent == "IMAGE_GENERATION":
        if not settings.fal_api_key:
            return {
                "content": "Görsel üretimi için FAL API anahtarı yapılandırılmamış.",
                "image_urls": [],
                "image_links": {},
                "process_log": ["Görsel üretimi başarısız - API key eksik."]
            }

        # Kullanıcı isteğini analiz et (sayı ve açıklama çıkar)
        image_request = await loop.run_in_executor(None, extract_image_request, user_message)
        count = image_request["count"]
        description = image_request["description"]
        prompts = image_request["prompts"]

        logger.info(f"🎨 Görsel üretimi: {count} adet - {description}")

        # TUTARLILIK İÇİN MASTER SEED
        master_seed = secrets.randbelow(100_000_000)

        # Görselleri üret
        generated_images = await loop.run_in_executor(None, generate_custom_images, prompts, master_seed)

        # Başarılı görselleri filtrele
        successful_images = [img for img in generated_images if img.get("url")]

        # Yanıt metni oluştur
        if successful_images:
            content = f"**{description}** için {len(successful_images)} adet görsel ürettim:\n\n"
            for idx, img in enumerate(successful_images, 1):
                content += f"![{description} {idx}]({img['url']})\n\n"
        else:
            content = "Üzgünüm, görsel üretilirken bir hata oluştu. Lütfen tekrar deneyin."

        return {
            "content": content,
            "image_urls": [],  # Boş bırak - sadece markdown görseli gösterilsin
            "image_links": {},
            "process_log": [f"{count} adet görsel üretimi tamamlandı (Seed: {master_seed})."]
        }

    # --- IMAGE_MODIFICATION durumu - Önceki görseli modifiye etme ---
    if intent == "IMAGE_MODIFICATION":
        if not settings.fal_api_key:
            return {
                "content": "Görsel üretimi için FAL API anahtarı yapılandırılmamış.",
                "image_urls": [],
                "image_links": {},
                "process_log": ["API key eksik."]
            }

        # Önceki görsel bilgisini chat_history'den çıkar
        prev_context = await loop.run_in_executor(
            None, extract_previous_image_context, chat_history
        )

        # TUTARLILIK İÇİN SEED
        modification_seed = secrets.randbelow(100_000_000)

        if not prev_context.get("found"):
            # Önceki görsel bulunamadı, yeni görsel üretimi yap
            logger.info("⚠️ Önceki görsel bulunamadı, yeni üretim yapılıyor")
            image_request = await loop.run_in_executor(None, extract_image_request, user_message)
            prompts = image_request["prompts"]
            description = image_request["description"]
            mod_type = "new"
        else:
            # Önceki görseli modifiye et
            original_desc = prev_context.get("description") or prev_context.get("original_request", "")
            logger.info(f"🔄 Görsel modifikasyonu: {original_desc} -> {user_message}")

            modification = await loop.run_in_executor(
                None, modify_image_prompt, original_desc, user_message
            )
            prompts = modification["prompts"]
            description = original_desc
            mod_type = modification.get("modification_type", "variation")

            logger.info(f"📝 Modifikasyon tipi: {mod_type}, {len(prompts)} görsel üretilecek")

        # Görselleri üret
        generated_images = await loop.run_in_executor(None, generate_custom_images, prompts, modification_seed)

        # Başarılı görselleri filtrele
        successful_images = [img for img in generated_images if img.get("url")]

        # Yanıt metni oluştur
        if successful_images:
            if prev_context.get("found"):
                mod_messages = {
                    "regenerate": "tekrar ürettim",
                    "angle": "farklı açıdan ürettim",
                    "color": "renk değişikliği ile ürettim",
                    "style": "stil değişikliği ile ürettim",
                    "variation": "varyasyonlarını ürettim",
                    "size": "boyut değişikliği ile ürettim",
                    "fabric": "farklı kumaş ile ürettim"
                }
                mod_text = mod_messages.get(mod_type, "yeni versiyonlarını ürettim")
                content = f"**{description}** için {len(successful_images)} görsel {mod_text}:\n\n"
            else:
                content = f"**{description}** için {len(successful_images)} adet görsel ürettim:\n\n"

            for idx, img in enumerate(successful_images, 1):
                content += f"![{description} {idx}]({img['url']})\n\n"
        else:
            content = "Üzgünüm, görsel üretilirken bir hata oluştu. Lütfen tekrar deneyin."

        return {
            "content": content,
            "image_urls": [],  # Boş bırak - sadece markdown görseli gösterilsin
            "image_links": {},
            "process_log": [f"Görsel modifikasyonu ({mod_type}) tamamlandı."]
        }

    # --- FOLLOW UP ---
    if intent == "FOLLOW_UP":
        response_text = await handle_follow_up(user_message, chat_history)

        if "hatırlayamıyorum" in response_text.lower():
            return {"content": "Önceki veriye ulaşamadım. Lütfen tasarımı detaylandırın.", "image_urls": [], "image_links": {}, "process_log": ["Hafıza kaybı."]}

        visual_triggers = ["çiz", "tasarla", "görsel", "resim", "foto", "image", "draw", "kombin"]
        is_visual_request = any(w in user_message.lower() for w in visual_triggers)
        should_gen = bool(settings.fal_api_key) and is_visual_request
        ai_generated_items = []

        if should_gen:
            prompt_items = await loop.run_in_executor(None, generate_image_prompts, response_text)
            # MAKYAJ: Promptları güzelleştir
            for item in prompt_items:
                item['prompt'] = enhance_follow_up_prompt(item['prompt'])

            if not prompt_items and "görsel" in user_message.lower():
                enhanced = enhance_follow_up_prompt(f"Fashion illustration of {user_message}")
                prompt_items = [{"model_name": "Requested", "prompt": enhanced}]

            ai_generated_items = await loop.run_in_executor(None, generate_ai_images, prompt_items)

        combined_images = [d['url'] for d in ai_generated_items if d.get('url')]
        for item in ai_generated_items:
            if item.get('url'):
                response_text += f"\n\n**{item.get('model_name')}:**\n![{item.get('model_name')}]({item['url']})"

        return {"content": response_text, "image_urls": combined_images, "image_links": {}, "process_log": ["Devam yanıtı verildi."]}

    # === MARKET RESEARCH ===
    # Intelligence servisinden kapsamlı araştırma (Tavily + DB trend verileri)
    extracted_category = await loop.run_in_executor(None, extract_category_from_message, user_message)
    f_t = loop.run_in_executor(None, get_google_trends, user_message)

    # Intelligence /research/comprehensive endpoint'ini çağır
    async def _call_intelligence_research():
        import httpx
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{settings.intelligence_url}/research/comprehensive",
                    json={"topic": user_message, "category": extracted_category},
                    headers={"X-Internal-Key": settings.intelligence_internal_key},
                )
                if resp.status_code == 200:
                    return resp.json().get("data", {})
        except Exception as e:
            logger.warning(f"Intelligence research hatası: {e}")
        return None

    f_research = _call_intelligence_research()
    trends_res, research_data = await asyncio.gather(f_t, f_research)

    # Google Trends verisini formatla
    trends_text = format_trends_for_report(trends_res)

    # Intelligence'dan gelen birleşik veri (Tavily + DB trend)
    if research_data and research_data.get("combined_context"):
        full_data = research_data["combined_context"]
        runway_res = research_data.get("runway", {})
    else:
        # Fallback: Intelligence kapalıysa direkt Tavily (eski davranış)
        from app.services.data.research import analyze_runway_trends, deep_market_research
        f_m = loop.run_in_executor(None, deep_market_research, user_message)
        f_r = loop.run_in_executor(None, analyze_runway_trends, user_message)
        market_res, runway_res = await asyncio.gather(f_m, f_r)
        full_data = f"{runway_res.get('context','')}\n===\n{market_res.get('context','')}"

    if trends_text:
        full_data += f"\n\n=== GOOGLE TRENDS VERİSİ ===\n{trends_text}"
    
    final_report = await loop.run_in_executor(None, generate_strategic_report, user_message, full_data)

    if fallback_warning:
        warning_msg = "> ℹ️ **Bilgilendirme:** Bu konu için analiz motorumuzda (Intelligence) yeterli güncel veri bulunamadı. Bu yüzden aşağıdaki rapor, veritabanımız yerine güncel **internet trend araştırmalarına (Tavily & Google)** dayanılarak hazırlanmıştır.\n\n"
        final_report = warning_msg + final_report

    user_needs_visuals = await loop.run_in_executor(None, check_visual_necessity, user_message)
    if not user_needs_visuals:
        if await loop.run_in_executor(None, check_report_content_for_visuals, final_report):
            user_needs_visuals = True

    should_gen_ai = bool(settings.fal_api_key) and user_needs_visuals

    # 1. Rapordan maddeleri çek (Context Injection ile)
    extracted_items = await loop.run_in_executor(None, extract_visual_search_terms, final_report, user_message)

    if not extracted_items and user_needs_visuals:
        extracted_items = [{"name": f"Trend {i}", "search_query": f"{user_message} trend {i}", "ai_prompt_base": f"{user_message} trend item"} for i in range(1,6)]

    # 2. Rapor Görselleri İçin Prompt Hazırla
    if should_gen_ai:
        for item in extracted_items:
            # İngilizce başlığı al
            english_name = item.get('ai_prompt_base', item['name'])
            # Prompt artık context injection ile research.py'dan dolu geliyor
            base_prompt = f"Fashion product photography of {english_name}"
            # Stüdyo makyajını ekle
            item['ai_prompt'] = enhance_follow_up_prompt(base_prompt)

    # 3. Paralel Arama ve Çizim Başlat
    tasks_real_img = []
    tasks_ai_img = []

    for item in extracted_items:
        tasks_real_img.append(loop.run_in_executor(None, find_visual_match_for_model, item['search_query']))
        if should_gen_ai:
            prompt_data = [{"model_name": item['name'], "ref_id": "", "prompt": item['ai_prompt']}]
            tasks_ai_img.append(loop.run_in_executor(None, generate_ai_images, prompt_data))

    real_images_results = await asyncio.gather(*tasks_real_img)
    ai_images_results = await asyncio.gather(*tasks_ai_img) if should_gen_ai else []

    # 4. Görsel Entegrasyonu
    final_content = final_report
    runway_imgs = runway_res.get("runway_images", [])

    for i in range(1, 4):
        ph = f"[[RUNWAY_VISUAL_{i}]]"
        if i <= len(runway_imgs):
            final_content = final_content.replace(ph, f"\n![Defile {i}]({runway_imgs[i-1]})\n")
        else:
            final_content = final_content.replace(ph, "")

    # 5. Model Görsellerini Yerleştir (DÜZELTİLDİ: BOŞ BAŞLIK TEMİZLİĞİ)
    for i in range(1, 6):
        ph = f"[[VISUAL_CARD_{i}]]"
        item_info = extracted_items[i-1] if i <= len(extracted_items) else {"name": f"Model {i}"}
        real_data = real_images_results[i-1] if i <= len(real_images_results) else {}
        ai_list = ai_images_results[i-1] if (should_gen_ai and i <= len(ai_images_results)) else []
        ai_data = ai_list[0] if ai_list else {}

        m_url = real_data.get('img')
        m_page = real_data.get('page')
        ai_url = ai_data.get('url')
        model_name = item_info['name']

        replacement = ""
        # Mantıksal görsel yerleşimi
        if m_url and ai_url:
            replacement = f"\n> **📸 Piyasa:**\n> ![{model_name}]({m_url})\n> [🔗 İncele]({m_page})\n>\n> **🎨 AI Tasarım:**\n> ![{model_name}]({ai_url})\n"
        elif m_url:
            replacement = f"\n> **📸 Piyasa:**\n> ![{model_name}]({m_url})\n> [🔗 İncele]({m_page})\n"
        elif ai_url:
            replacement = f"\n> **🎨 AI Tasarım:**\n> ![{model_name}]({ai_url})\n"

        # Replacement boşsa (yani görsel yoksa) başlıklar da eklenmeyecek
        final_content = final_content.replace(ph, replacement)

        # Placeholder yoksa manuel ekle (Sadece replacement doluysa)
        if replacement and ph not in final_report:
            if model_name in final_content:
                parts = final_content.split(model_name, 1)
                if len(parts) > 1:
                    final_content = parts[0] + model_name + "\n" + replacement + parts[1]

    final_content = _remove_non_http_images(final_content)

    # Tüm linkleri topla
    all_urls = [x.get('img') for x in real_images_results if x.get('img')] + \
               [item['url'] for sublist in ai_images_results for item in sublist if item.get('url')] + \
               runway_imgs

    link_map = {x.get('img'): x.get('page') for x in real_images_results if x.get('img')}
    for u in all_urls:
        if u not in link_map: link_map[u] = None

    return {"content": final_content, "image_urls": all_urls, "image_links": link_map, "process_log": ["Tamamlandı."]}