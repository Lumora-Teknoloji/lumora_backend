"""
Orchestrator - Ana AI yanıt üretimi orkestrasyonu
"""
import asyncio
import logging
import re
from typing import List, Dict, Any
from .clients import openai_client
from .intent import analyze_user_intent, handle_general_chat, handle_follow_up
from .research import analyze_runway_trends, deep_market_research, generate_strategic_report
from .images import (
    generate_image_prompts,
    extract_visual_style,
    generate_ai_images,
    _remove_non_http_images,
    extract_image_request,
    extract_previous_image_context,
    modify_image_prompt,
    generate_custom_images
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

    # IMAGE_GENERATION durumu - Yeni görsel üretimi
    if intent == "IMAGE_GENERATION":
        # FAL API key kontrolü
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
        
        # Görselleri üret
        generated_images = await loop.run_in_executor(None, generate_custom_images, prompts)
        
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
            "process_log": [f"{count} adet görsel üretimi tamamlandı."]
        }

    # IMAGE_MODIFICATION durumu - Önceki görseli modifiye etme
    if intent == "IMAGE_MODIFICATION":
        # FAL API key kontrolü
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
        generated_images = await loop.run_in_executor(None, generate_custom_images, prompts)
        
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
    visual_card_items = []  # BÖLÜM 4 için ekstra görseller

    if should_gen:
        # Başta üretilen görseller (genel kullanım için)
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

        # BÖLÜM 4 için ekstra görsel üretimi
        # Rapordaki BÖLÜM 4 kısmını çıkar
        section_4_start = final_report.find("## 🏆 BÖLÜM 4: TOP 5 TİCARİ MODEL")
        section_5_start = final_report.find("## 🛍️ BÖLÜM 5")
        
        if section_4_start != -1:
            section_4_text = (
                final_report[section_4_start:section_5_start] 
                if section_5_start != -1 
                else final_report[section_4_start:]
            )
            
            # BÖLÜM 4'ten 5 model için prompt üret
            visual_card_prompts = await loop.run_in_executor(
                None, 
                generate_image_prompts, 
                section_4_text
            )
            
            # Eğer prompt çıkmazsa, rapordaki model isimlerinden üret
            if not visual_card_prompts or len(visual_card_prompts) < 5:
                # Model başlıklarını bul - hem ### 1. hem de 1. formatını destekle
                model_pattern = r'(?:###\s+)?(\d+)\.\s*([^\n]+)'
                models = re.findall(model_pattern, section_4_text)
                
                logger.info(f"BÖLÜM 4'ten {len(models)} model bulundu")
                
                visual_card_prompts = []
                for idx, (num, model_name) in enumerate(models[:5], 1):
                    model_name_clean = model_name.strip()
                    visual_card_prompts.append({
                        "model_name": model_name_clean,
                        "ref_id": f"IMG_REF_{idx}",
                        "prompt": f"Professional fashion product photography of {model_name_clean}, e-commerce style, studio lighting, 8k"
                    })
                
                logger.info(f"BÖLÜM 4 için {len(visual_card_prompts)} prompt oluşturuldu")
            
            # Promptları zenginleştir
            for p in visual_card_prompts[:5]:
                p['prompt'] = f"{p.get('prompt', '')}, {style}"
            
            # BÖLÜM 4 için ekstra görselleri üret
            visual_card_items = await loop.run_in_executor(
                None, 
                generate_ai_images, 
                visual_card_prompts[:5]
            )
            logger.info(f"BÖLÜM 4 için {len(visual_card_items)} görsel üretildi")
        else:
            logger.warning("BÖLÜM 4 bulunamadı, ekstra görsel üretilmeyecek")

    # Görsel entegrasyonu
    final_content = final_report
    runway_imgs = runway_res.get("runway_images", [])

    # Defile görselleri - Minimum 2, maksimum 5 görsel göster
    # Eğer 2'den az görsel varsa, mevcut olanları göster
    # Eğer 5'ten fazla varsa, ilk 5'ini göster
    runway_count = max(2, min(len(runway_imgs), 5))  # En az 2, en fazla 5
    
    for i in range(1, runway_count + 1):
        ph = f"[[RUNWAY_VISUAL_{i}]]"
        if i <= len(runway_imgs):
            final_content = final_content.replace(ph, f"![Defile {i}]({runway_imgs[i - 1]})")
        else:
            final_content = final_content.replace(ph, "")
    
    # Kalan placeholder'ları temizle (eğer 5'ten fazla varsa veya LLM fazla placeholder eklediyse)
    for i in range(runway_count + 1, 6):
        ph = f"[[RUNWAY_VISUAL_{i}]]"
        final_content = final_content.replace(ph, "")

    # AI / Pazar görselleri - Her model için market görseli + AI görseli
    # BÖLÜM 4 için ekstra üretilen görselleri kullan
    for i in range(1, 6):
        ph = f"[[VISUAL_CARD_{i}]]"
        # Önce BÖLÜM 4 için üretilen görselleri kullan, yoksa başta üretilenleri kullan
        ai_item = visual_card_items[i - 1] if i <= len(visual_card_items) else (
            ai_generated_items[i - 1] if i <= len(ai_generated_items) else None
        )
        
        replacement = ""
        ai_url = ai_item.get("url") if ai_item else None
        
        # Market görseli bulma stratejisi:
        # 1. Önce AI item'ın ref_id'si ile eşleşen market görselini bul
        # 2. Eğer bulunamazsa, sırayla market görsellerinden birini kullan
        m_url = ""
        m_page = ""
        
        if ai_item and ai_item.get("ref_id"):
            # ref_id ile eşleşen market görselini bul
            m_url = ref_lookup.get(ai_item.get("ref_id"), "")
            if m_url:
                m_page = next((d['page'] for d in market_images if d['img'] == m_url), m_url)
        
        # Eğer ref_id ile eşleşen görsel bulunamadıysa, sırayla market görsellerinden birini kullan
        if not m_url and i <= len(market_images):
            market_item = market_images[i - 1]
            m_url = market_item.get('img', '')
            m_page = market_item.get('page', m_url)
        
        # Görsel gösterimi - Her model için mutlaka görsel göster
        # ai_url None olabilir (hata durumunda), bu yüzden kontrol et
        if m_url and ai_url:
            # Hem market hem AI görseli var - yan yana göster
            replacement = (
                f"\n| Çok Satan Ürün | AI Tasarım ({ai_item.get('model_name', 'Model') if ai_item else 'Model'}) |\n"
                f"|:---:|:---:|\n"
                f"| <a href='{m_page}' target='_blank'><img src='{m_url}' width='200'/></a> | "
                f"<img src='{ai_url}' width='200'/> |\n"
            )
        elif m_url:
            # Sadece market görseli var
            replacement = (
                f"\n| Çok Satan Ürün |\n"
                f"|:---:|\n"
                f"| <a href='{m_page}' target='_blank'><img src='{m_url}' width='200'/></a> |\n"
            )
        elif ai_url:
            # Sadece AI görseli var (ve None değil)
            replacement = (
                f"\n| AI Tasarım ({ai_item.get('model_name', 'Model') if ai_item else 'Model'}) |\n"
                f"|:---:|\n"
                f"| <img src='{ai_url}' width='200'/> |\n"
            )
        elif market_images and i <= len(market_images):
            # Hiçbiri yoksa bile, market görsellerinden birini göster
            market_item = market_images[i - 1]
            m_url = market_item.get('img', '')
            m_page = market_item.get('page', m_url)
            if m_url:
                replacement = (
                    f"\n| Çok Satan Ürün |\n"
                    f"|:---:|\n"
                    f"| <a href='{m_page}' target='_blank'><img src='{m_url}' width='200'/></a> |\n"
                )

        # Placeholder'ı değiştir
        if replacement:
            final_content = final_content.replace(ph, replacement)
        else:
            # Placeholder yoksa bile temizle
            final_content = final_content.replace(ph, "")

    # LLM placeholder'ları unuttuysa, her model başlığının altına görsel ekle
    # Model başlıklarını bul ve görselleri ekle
    for i in range(1, 6):
        model_header_pattern = f"### {i}."
        # Eğer bu model başlığının altında görsel yoksa ekle
        if model_header_pattern in final_content:
            # Model başlığının konumunu bul
            header_index = final_content.find(model_header_pattern)
            if header_index != -1:
                # Bir sonraki model başlığına kadar olan kısmı al
                next_header_index = final_content.find(f"### {i+1}.", header_index + 1)
                if next_header_index == -1:
                    next_header_index = final_content.find("## 🛍️ BÖLÜM 5", header_index + 1)
                if next_header_index == -1:
                    next_header_index = len(final_content)
                
                model_section = final_content[header_index:next_header_index]
                
                # Eğer bu bölümde görsel yoksa ekle
                if "img src" not in model_section and "VISUAL_CARD" not in model_section:
                    # Önce BÖLÜM 4 için üretilen görselleri kullan
                    ai_item = visual_card_items[i - 1] if i <= len(visual_card_items) else (
                        ai_generated_items[i - 1] if i <= len(ai_generated_items) else None
                    )
                    ai_url = ai_item.get("url") if ai_item else None
                    
                    # Market görseli bul
                    m_url = ""
                    m_page = ""
                    if ai_item and ai_item.get("ref_id"):
                        m_url = ref_lookup.get(ai_item.get("ref_id"), "")
                        if m_url:
                            m_page = next((d['page'] for d in market_images if d['img'] == m_url), m_url)
                    
                    if not m_url and i <= len(market_images):
                        market_item = market_images[i - 1]
                        m_url = market_item.get('img', '')
                        m_page = market_item.get('page', m_url)
                    
                    # Görsel ekle
                    if m_url or ai_url:
                        visual_html = ""
                        if m_url and ai_url:
                            visual_html = (
                                f"\n| Çok Satan Ürün | AI Tasarım ({ai_item.get('model_name', 'Model') if ai_item else 'Model'}) |\n"
                                f"|:---:|:---:|\n"
                                f"| <a href='{m_page}' target='_blank'><img src='{m_url}' width='200'/></a> | "
                                f"<img src='{ai_url}' width='200'/> |\n"
                            )
                        elif m_url:
                            visual_html = (
                                f"\n| Çok Satan Ürün |\n"
                                f"|:---:|\n"
                                f"| <a href='{m_page}' target='_blank'><img src='{m_url}' width='200'/></a> |\n"
                            )
                        elif ai_url:
                            visual_html = (
                                f"\n| AI Tasarım ({ai_item.get('model_name', 'Model') if ai_item else 'Model'}) |\n"
                                f"|:---:|\n"
                                f"| <img src='{ai_url}' width='200'/> |\n"
                            )
                        
                        # Model açıklamasının sonuna görsel ekle
                        # Açıklama genellikle * ile başlar ve biter
                        desc_end = model_section.rfind("*")
                        if desc_end != -1:
                            # Açıklamanın sonunu bul
                            line_end = model_section.find("\n", desc_end)
                            if line_end == -1:
                                line_end = len(model_section)
                            insert_pos = header_index + line_end + 1
                            final_content = final_content[:insert_pos] + visual_html + final_content[insert_pos:]

    final_content = _remove_non_http_images(final_content)

    combined_images = (
        [d['img'] for d in market_images] +
        [d['url'] for d in ai_generated_items] +
        [d['url'] for d in visual_card_items] +  # BÖLÜM 4 görsellerini de ekle
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

