import logging
import secrets
from typing import Dict, Any, List

from app.services.ai.image_gen_service import (
    generate_custom_images,
    extract_image_request,
    extract_previous_image_context,
    modify_image_prompt
)
from app.core.config import settings

logger = logging.getLogger(__name__)

async def handle_image_generation(
    user_message: str
) -> Dict[str, Any]:
    """
    IMAGE_GENERATION niyetini işler.
    Kullanıcının isteğine göre tamamen yeni görsel(ler) üretir.
    """
    if not settings.fal_api_key:
        return {
            "content": "Görsel üretimi için FAL API anahtarı yapılandırılmamış.",
            "image_urls": [],
            "image_links": {},
            "process_log": ["Görsel üretimi başarısız - API key eksik."]
        }

    # Kullanıcı isteğini analiz et (sayı ve açıklama çıkar)
    import asyncio
    image_request = await asyncio.get_event_loop().run_in_executor(None, extract_image_request, user_message)
    count = image_request["count"]
    description = image_request["description"]
    prompts = image_request["prompts"]

    logger.info(f"🎨 Görsel üretimi: {count} adet - {description}")

    # TUTARLILIK İÇİN MASTER SEED
    master_seed = secrets.randbelow(100_000_000)

    # Görselleri üret
    generated_images = await asyncio.get_event_loop().run_in_executor(None, generate_custom_images, prompts, master_seed)

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
        "image_urls": [],  # Sadece markdown görseli gösterilsin diye boş bırakılır
        "image_links": {},
        "process_log": [f"{count} adet görsel üretimi tamamlandı (Seed: {master_seed})."]
    }

async def handle_image_modification(
    user_message: str,
    chat_history: List[Dict[str, str]]
) -> Dict[str, Any]:
    """
    IMAGE_MODIFICATION niyetini işler.
    Kullanıcının önceki görsel talebini baz alarak yeni bir görsel üretir (modifiye eder).
    """
    if not settings.fal_api_key:
        return {
            "content": "Görsel üretimi için FAL API anahtarı yapılandırılmamış.",
            "image_urls": [],
            "image_links": {},
            "process_log": ["API key eksik."]
        }

    import asyncio
    loop = asyncio.get_event_loop()

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
        "image_urls": [],  
        "image_links": {},
        "process_log": [f"Görsel modifikasyonu ({mod_type}) tamamlandı."]
    }
