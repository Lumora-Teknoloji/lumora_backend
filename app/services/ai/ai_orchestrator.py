"""
Orchestrator - Ana AI yanıt üretimi orkestrasyonu
"""
import asyncio
import logging
import re
import secrets
from typing import List, Dict, Any
from app.services.core.clients import openai_client, get_model_name
from app.services.ai.intent import analyze_user_intent, handle_general_chat, handle_follow_up, extract_production_parameters, check_visual_necessity, check_report_content_for_visuals
from app.services.ai.database_query import handle_database_query
from app.core.config import settings

# Import the new handlers
from app.services.ai.handlers.trend_handler import handle_trend_analysis
from app.services.ai.handlers.image_handler import handle_image_generation, handle_image_modification
from app.services.ai.handlers.market_handler import handle_market_research
from app.services.ai.image_gen_service import generate_image_prompts, generate_ai_images, enhance_follow_up_prompt

logger = logging.getLogger(__name__)


async def generate_ai_response(
    user_message: str,
    chat_history: List[Dict[str, str]] = None,
    generate_images: bool = False,
    stream_callback: Any = None
) -> Dict[str, Any]:
    """
    Ana AI yanıt üretimi fonksiyonu
    Kullanıcı mesajını analiz eder ve uygun yanıtı üretir
    """
    if chat_history is None:
        chat_history = []
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
        return await handle_database_query(user_message, chat_history, stream_callback)

    # --- TREND_ANALYSIS --- (Intelligence servisinden gerçek tahmin verileri)
    if intent == "TREND_ANALYSIS":
        logger.info("📊 TREND_ANALYSIS akışı başlatıldı")

        # 1. Mesajdan detaylı üretim parametreleri çıkar
        params = await loop.run_in_executor(None, extract_production_parameters, user_message)
        user_needs_visuals = await loop.run_in_executor(None, check_visual_necessity, user_message)

        return await handle_trend_analysis(user_message, params, user_needs_visuals, stream_callback)

    # --- IMAGE_GENERATION durumu - Yeni görsel üretimi ---
    if intent == "IMAGE_GENERATION":
        return await handle_image_generation(user_message)

    # --- IMAGE_MODIFICATION durumu - Önceki görseli modifiye etme ---
    if intent == "IMAGE_MODIFICATION":
        return await handle_image_modification(user_message, chat_history)

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
    logger.info("🌍 MARKET_RESEARCH akışı başlatıldı")
    return await handle_market_research(user_message)