import logging
import asyncio
from typing import Dict, Any

from app.core.config import settings
from app.services.ai.intent import extract_category_from_message
from app.services.data.trends import get_google_trends, format_trends_for_report
from app.services.data.research import (
    generate_strategic_report,
    find_visual_match_for_model,
    extract_visual_search_terms
)
from app.services.ai.image_gen_service import generate_ai_images, enhance_follow_up_prompt, _remove_non_http_images
from app.services.ai.ai_orchestrator import check_visual_necessity, check_report_content_for_visuals

logger = logging.getLogger(__name__)

async def handle_market_research(
    user_message: str
) -> Dict[str, Any]:
    """
    MARKET_RESEARCH niyetini işler.
    Intelligence servisinden veya Tavily'den pazar araştırması yapar.
    Google Trends verilerini çeker ve görsel entegrasyonu ile rapor sunar.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    fallback_warning = False

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
        fallback_warning = True
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
            
            import inspect
            if inspect.iscoroutinefunction(generate_ai_images):
                tasks_ai_img.append(generate_ai_images(prompt_data))
            else:
                tasks_ai_img.append(loop.run_in_executor(None, generate_ai_images, prompt_data))

    real_images_results = await asyncio.gather(*tasks_real_img)
    ai_images_results = await asyncio.gather(*tasks_ai_img) if should_gen_ai else []

    # 4. Görsel Entegrasyonu
    final_content = final_report
    runway_imgs = runway_res.get("runway_images", []) if hasattr(runway_res, "get") else []

    for i in range(1, 4):
        ph = f"[[RUNWAY_VISUAL_{i}]]"
        if i <= len(runway_imgs):
            final_content = final_content.replace(ph, f"\n![Defile {i}]({runway_imgs[i-1]})\n")
        else:
            final_content = final_content.replace(ph, "")

    # 5. Model Görsellerini Yerleştir
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
