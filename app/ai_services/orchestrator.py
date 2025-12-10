"""
Orchestrator - Ana AI yanıt üretimi orkestrasyonu
"""
import asyncio
import logging
import re
from typing import List, Dict, Any
from .clients import openai_client
from .intent import analyze_user_intent, handle_general_chat, handle_follow_up
from .research import (
    analyze_runway_trends,
    deep_market_research,
    generate_strategic_report,
    extract_trend_ideas,
    search_specific_best_seller
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

    # 1. NİYET ANALİZİ
    intent = await loop.run_in_executor(None, analyze_user_intent, user_message, chat_history)

    if intent == "GENERAL_CHAT":
        content = await loop.run_in_executor(None, handle_general_chat, user_message)
        return {"content": content, "image_urls": [], "image_links": {}, "process_log": ["Sohbet."]}

    if intent == "FOLLOW_UP":
        response_text = await handle_follow_up(user_message, chat_history)
        return {"content": response_text, "image_urls": [], "image_links": {}, "process_log": ["Devam."]}

    # === MARKET RESEARCH (YENİLENMİŞ AKIŞ) ===

    # Adım 1: Geniş Tarama
    f_m = loop.run_in_executor(None, deep_market_research, user_message)
    f_r = loop.run_in_executor(None, analyze_runway_trends, user_message)
    market_res, runway_res = await asyncio.gather(f_m, f_r)

    base_context = f"{runway_res.get('context', '')}\n===\n{market_res.get('context', '')}"

    # Adım 2: Trendlerden 5 Somut Model Fikri Çıkar
    logger.info("💡 Trend fikirleri çıkarılıyor...")
    model_ideas = await loop.run_in_executor(None, extract_trend_ideas, user_message, base_context)

    # Adım 3: Her Fikir İçin NOKTA ATIŞI Arama Yap
    logger.info(f"🔎 {len(model_ideas)} model için özel arama başlatılıyor...")
    specific_tasks = [loop.run_in_executor(None, search_specific_best_seller, idea) for idea in model_ideas]
    specific_results = await asyncio.gather(*specific_tasks)

    # Adım 4: Raporu Yazdır (HATANIN ÇÖZÜLDÜĞÜ YER)
    # specific_results artık doğru şekilde gönderiliyor
    final_report = await loop.run_in_executor(
        None,
        generate_strategic_report,
        user_message,
        base_context,
        specific_results
    )

    # Adım 5: AI Görsel (Opsiyonel / Yedek)
    ai_generated = []
    if settings.fal_api_key:
        prompts = []
        style = await loop.run_in_executor(None, extract_visual_style, user_message)
        for item in specific_results:
            if item.get('search_term'):
                prompts.append({
                    "model_name": item['search_term'],
                    "prompt": f"Professional product photo of {item['search_term']}, {style}, white background, 8k"
                })
        ai_generated = await loop.run_in_executor(None, generate_ai_images, prompts)

    # Adım 6: Entegrasyon
    final_content = final_report
    runway_imgs = runway_res.get("runway_images", [])

    # Defile Görselleri
    for i in range(1, 4):
        ph = f"[[RUNWAY_VISUAL_{i}]]"
        if i <= len(runway_imgs):
            final_content = final_content.replace(ph, f"![Defile {i}]({runway_imgs[i-1]})")
        else:
            final_content = final_content.replace(ph, "")

    # Model Görselleri
    for i in range(1, 6):
        ph = f"[[VISUAL_CARD_{i}]]"

        real_data = specific_results[i-1] if i <= len(specific_results) else {}
        ai_data = ai_generated[i-1] if i <= len(ai_generated) else {}

        real_img = real_data.get('img')
        real_link = real_data.get('link')
        ai_img = ai_data.get('url')
        name = real_data.get('search_term', f'Model {i}')

        replacement = ""
        if real_img and ai_img:
            replacement = (
                f"\n| Çok Satan ({name}) | AI Tasarım |\n|:---:|:---:|\n"
                f"| <a href='{real_link}' target='_blank'><img src='{real_img}' width='200'/></a> | "
                f"<img src='{ai_img}' width='200'/> |\n"
            )
        elif real_img:
            replacement = (
                f"\n| Çok Satan ({name}) |\n|:---:|\n"
                f"| <a href='{real_link}' target='_blank'><img src='{real_img}' width='200'/></a> |\n"
            )
        elif ai_img:
            replacement = (
                f"\n| AI Tasarım ({name}) |\n|:---:|\n"
                f"| <img src='{ai_img}' width='200'/> |\n"
            )

        final_content = final_content.replace(ph, replacement)

        if replacement and ph not in final_report:
             final_content += f"\n\n### Model {i} Görselleri\n{replacement}"

    final_content = _remove_non_http_images(final_content)

    all_urls = [x['url'] for x in ai_generated] + [x['img'] for x in specific_results if x.get('img')] + runway_imgs
    link_map = {x['img']: x['link'] for x in specific_results if x.get('img')}
    for u in all_urls:
        if u not in link_map: link_map[u] = None

    return {
        "content": final_content,
        "image_urls": all_urls,
        "image_links": link_map,
        "process_log": ["Analiz tamamlandı."]
    }