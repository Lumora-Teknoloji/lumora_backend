"""
Orchestrator - Ana AI yanıt üretimi orkestrasyonu
"""
import asyncio
import logging
from typing import List, Dict, Any
from .clients import openai_client
from .intent import analyze_user_intent, handle_general_chat, handle_follow_up
from .research import analyze_runway_trends, deep_market_research, generate_strategic_report
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
    """
    Ana AI yanıt üretimi fonksiyonu
    Kullanıcı mesajını analiz eder ve uygun yanıtı üretir
    """
    loop = asyncio.get_event_loop()

    # Niyet analizi
    intent = await loop.run_in_executor(None, analyze_user_intent, user_message, chat_history)
    logger.info(f"🧠 Niyet: {intent}")

    # GENERAL_CHAT durumu
    if intent == "GENERAL_CHAT":
        content = await loop.run_in_executor(None, handle_general_chat, user_message)
        return {
            "content": content,
            "image_urls": [],
            "image_links": {},
            "process_log": ["Sohbet."]
        }

    # FOLLOW_UP durumu
    if intent == "FOLLOW_UP":
        response_text = await handle_follow_up(user_message, chat_history)

        # Görsel üretimi (FAL API key varsa)
        should_gen = bool(settings.fal_api_key)
        ai_generated_items = []

        if should_gen:
            prompt_items = await loop.run_in_executor(None, generate_image_prompts, response_text)
            # Eğer prompt çıkmazsa (sohbet metniyse), zorla prompt üret
            if not prompt_items and "görsel" in user_message.lower():
                prompt_items = [{
                    "model_name": "Requested Visual",
                    "prompt": f"Fashion illustration of {user_message}"
                }]

            ai_generated_items = await loop.run_in_executor(None, generate_ai_images, prompt_items)

        combined_images = [d['url'] for d in ai_generated_items]
        # Görselleri metne ekle
        for item in ai_generated_items:
            response_text += f"\n\n![{item.get('model_name')}]({item['url']})"

        return {
            "content": response_text,
            "image_urls": combined_images,
            "image_links": {u: None for u in combined_images},
            "process_log": ["Sohbet devamı."]
        }

    # MARKET_RESEARCH durumu
    # Paralel olarak market ve runway araştırması yap
    f_m = loop.run_in_executor(None, deep_market_research, user_message)
    f_r = loop.run_in_executor(None, analyze_runway_trends, user_message)
    market_res, runway_res = await asyncio.gather(f_m, f_r)

    # Rapor üretimi
    full_data = f"{runway_res.get('context', '')}\n===\n{market_res.get('context', '')}"
    final_report = await loop.run_in_executor(
        None,
        generate_strategic_report,
        user_message,
        full_data
    )

    market_images = market_res.get("market_images", [])
    ref_lookup = {f"IMG_REF_{i + 1}": img['img'] for i, img in enumerate(market_images)}

    # AI görsel üretimi (FAL API key varsa)
    should_gen = bool(settings.fal_api_key)
    ai_generated_items = []

    if should_gen:
        p_items = await loop.run_in_executor(None, generate_image_prompts, final_report)
        # Eğer rapordan prompt çıkmazsa, kullanıcı mesajından üret
        if not p_items:
            p_items = [{
                "model_name": "Trend Analysis",
                "ref_id": "",
                "prompt": f"High fashion photography of {user_message}, studio light, 8k"
            }]

        style = await loop.run_in_executor(None, extract_visual_style, user_message)
        # Promptları zenginleştir
        for p in p_items:
            p['prompt'] = f"{p['prompt']}, {style}"

        ai_generated_items = await loop.run_in_executor(None, generate_ai_images, p_items)

    # Görsel entegrasyonu
    final_content = final_report
    runway_imgs = runway_res.get("runway_images", [])

    # Defile görselleri
    for i in range(1, 3):
        ph = f"[[RUNWAY_VISUAL_{i}]]"
        if i <= len(runway_imgs):
            final_content = final_content.replace(ph, f"![Defile {i}]({runway_imgs[i - 1]})")
        else:
            final_content = final_content.replace(ph, "")

    # AI / Pazar görselleri
    for i in range(1, 6):
        ph = f"[[VISUAL_CARD_{i}]]"
        ai_item = ai_generated_items[i - 1] if i <= len(ai_generated_items) else None

        replacement = ""
        if ai_item:
            ai_url = ai_item.get("url")
            m_url = ref_lookup.get(ai_item.get("ref_id"), "")
            m_page = next((d['page'] for d in market_images if d['img'] == m_url), m_url)

            if m_url and ai_url:
                replacement = (
                    f"\n| Pazar Ref. | AI Tasarım ({ai_item.get('model_name')}) |\n"
                    f"|:---:|:---:|\n"
                    f"| <a href='{m_page}' target='_blank'><img src='{m_url}' width='200'/></a> | "
                    f"<img src='{ai_url}' width='200'/> |\n"
                )
            elif ai_url:
                replacement = (
                    f"\n| AI Tasarım ({ai_item.get('model_name')}) |\n"
                    f"|:---:|\n"
                    f"| <img src='{ai_url}' width='200'/> |\n"
                )

        final_content = final_content.replace(ph, replacement)

        # Eğer LLM placeholder'ı unuttuysa ve görsel varsa, sona ekle
        if ai_item and ph not in final_report:
            final_content += f"\n\n### Ek Model Görseli {i}\n{replacement}"

    final_content = _remove_non_http_images(final_content)

    combined_images = (
        [d['img'] for d in market_images] +
        [d['url'] for d in ai_generated_items] +
        runway_imgs
    )
    image_links = {img: None for img in combined_images}
    for d in market_images:
        image_links[d['img']] = d['page']

    return {
        "content": final_content,
        "image_urls": combined_images,
        "image_links": image_links,
        "process_log": ["Tamamlandı."]
    }

