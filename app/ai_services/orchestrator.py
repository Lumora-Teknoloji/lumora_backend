"""
Orchestrator - Ana AI yanıt üretimi orkestrasyonu
"""
import asyncio
import logging
from typing import List, Dict, Any
from .clients import openai_client
from .intent import analyze_user_intent, handle_general_chat, handle_follow_up
from .research import (
    analyze_runway_trends,
    deep_market_research,
    generate_strategic_report,
    find_visual_match_for_model,
    extract_visual_search_terms
)
from .images import (
    generate_image_prompts,
    extract_visual_style,
    generate_ai_images,
    _remove_non_http_images
)
from ..config import settings

logger = logging.getLogger(__name__)

async def generate_ai_response(
    user_message: str,
    chat_history: List[Dict[str, str]] = [],
    generate_images: bool = False
) -> Dict[str, Any]:

    loop = asyncio.get_event_loop()

    # 1. Niyet Analizi
    intent = await loop.run_in_executor(None, analyze_user_intent, user_message, chat_history)
    logger.info(f"🧠 Algılanan Niyet: {intent}")

    if intent == "GENERAL_CHAT":
        content = await loop.run_in_executor(None, handle_general_chat, user_message)
        # Genel sohbette görsel üretilmez
        return {"content": content, "image_urls": [], "image_links": {}, "process_log": ["Sohbet edildi."]}

    if intent == "FOLLOW_UP":
        response_text = await handle_follow_up(user_message, chat_history)

        # --- GÜNCELLEME: EMNİYET KİLİDİ ---
        # Kullanıcı açıkça görsel istemediyse veya modifikasyon yapmadıysa görsel üretme.
        # Bu, "Peki ya şu?" gibi metin odaklı sorularda boş yere görsel üretimini engeller.
        visual_triggers = ["çiz", "tasarla", "görsel", "resim", "foto", "image", "draw", "rengi", "modeli", "kumaşı"]
        is_visual_request = any(w in user_message.lower() for w in visual_triggers)

        should_gen = bool(settings.fal_api_key) and is_visual_request
        ai_generated_items = []

        if should_gen:
            logger.info("🎨 Görsel isteği tespit edildi, çizim yapılıyor...")
            prompt_items = await loop.run_in_executor(None, generate_image_prompts, response_text)
            if not prompt_items and "görsel" in user_message.lower():
                prompt_items = [{"model_name": "Requested", "prompt": f"Fashion illustration of {user_message}"}]
            ai_generated_items = await loop.run_in_executor(None, generate_ai_images, prompt_items)
        else:
            logger.info("💬 Metin odaklı devam sorusu (Görsel üretilmedi).")

        combined_images = [d['url'] for d in ai_generated_items if d.get('url')]
        for item in ai_generated_items:
            if item.get('url'):
                response_text += f"\n\n![{item.get('model_name')}]({item['url']})"

        return {
            "content": response_text,
            "image_urls": combined_images,
            "image_links": {u: None for u in combined_images},
            "process_log": ["Devam yanıtı verildi."]
        }

    # === MARKET RESEARCH (AKILLI CIMBIZLAMA AKIŞI) ===
    # (Bu kısım aynı kalıyor, değiştirmeye gerek yok)
    f_m = loop.run_in_executor(None, deep_market_research, user_message)
    f_r = loop.run_in_executor(None, analyze_runway_trends, user_message)
    market_res, runway_res = await asyncio.gather(f_m, f_r)

    full_data = f"{runway_res.get('context','')}\n===\n{market_res.get('context','')}"

    logger.info("📝 Rapor yazılıyor...")
    final_report = await loop.run_in_executor(None, generate_strategic_report, user_message, full_data)

    logger.info("🧠 Rapordan model detayları ayrıştırılıyor...")
    extracted_items = await loop.run_in_executor(None, extract_visual_search_terms, final_report)

    if not extracted_items:
        extracted_items = [{"name": f"Model {i}", "search_query": f"{user_message} trend {i}", "ai_prompt": f"Fashion {user_message}"} for i in range(1,6)]

    should_gen_ai = bool(settings.fal_api_key)

    tasks_real_img = []
    tasks_ai_img = []

    for item in extracted_items:
        tasks_real_img.append(loop.run_in_executor(None, find_visual_match_for_model, item['search_query']))
        if should_gen_ai:
            prompt_data = [{"model_name": item['name'], "ref_id": "", "prompt": item['ai_prompt'] + ", e-commerce style, 8k"}]
            tasks_ai_img.append(loop.run_in_executor(None, generate_ai_images, prompt_data))

    logger.info("⚡ Görsel işlemleri başlatılıyor...")
    real_images_results = await asyncio.gather(*tasks_real_img)
    ai_images_results = await asyncio.gather(*tasks_ai_img) if should_gen_ai else []

    final_content = final_report
    runway_imgs = runway_res.get("runway_images", [])

    for i in range(1, 4):
        ph = f"[[RUNWAY_VISUAL_{i}]]"
        if i <= len(runway_imgs): final_content = final_content.replace(ph, f"![Defile {i}]({runway_imgs[i-1]})")
        else: final_content = final_content.replace(ph, "")

    for i in range(1, 6):
        ph = f"[[VISUAL_CARD_{i}]]"
        item_info = extracted_items[i-1] if i <= len(extracted_items) else {"name": f"Model {i}"}
        real_data = real_images_results[i-1] if i <= len(real_images_results) else {}
        ai_list = ai_images_results[i-1] if i <= len(ai_images_results) else []
        ai_data = ai_list[0] if ai_list else {}

        m_url = real_data.get('img')
        m_page = real_data.get('page')
        ai_url = ai_data.get('url')
        model_name = item_info['name']

        replacement = ""
        if m_url and ai_url:
            replacement = f"\n| Çok Satan ({model_name}) | AI Tasarım ({model_name}) |\n|:---:|:---:|\n| <a href='{m_page}' target='_blank'><img src='{m_url}' width='200'/></a> | <img src='{ai_url}' width='200'/> |\n"
        elif m_url:
            replacement = f"\n| Çok Satan ({model_name}) |\n|:---:|\n| <a href='{m_page}' target='_blank'><img src='{m_url}' width='200'/></a> |\n"
        elif ai_url:
            replacement = f"\n| AI Tasarım ({model_name}) |\n|:---:|\n| <img src='{ai_url}' width='200'/> |\n"

        final_content = final_content.replace(ph, replacement)

        if replacement and ph not in final_report:
             if model_name in final_content:
                 parts = final_content.split(model_name, 1)
                 if len(parts) > 1:
                     final_content = parts[0] + model_name + "\n" + replacement + parts[1]

    final_content = _remove_non_http_images(final_content)

    all_urls = [x.get('img') for x in real_images_results if x.get('img')] + \
               [item['url'] for sublist in ai_images_results for item in sublist if item.get('url')] + \
               runway_imgs

    link_map = {x.get('img'): x.get('page') for x in real_images_results if x.get('img')}
    for u in all_urls:
        if u not in link_map: link_map[u] = None

    return {
        "content": final_content,
        "image_urls": all_urls,
        "image_links": link_map,
        "process_log": ["Analiz ve akıllı eşleştirme tamamlandı."]
    }