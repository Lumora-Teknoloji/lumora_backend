import logging
import json
from typing import Dict, Any, AnyStr

from app.services.core.clients import openai_client, get_model_name
from app.services.intelligence.intelligence_client import intelligence_client
from app.services.ai.semantic_matcher import semantic_match_and_rank
from app.services.intelligence.intelligence_formatter import format_structured_report
from app.services.ai.image_gen_service import generate_ai_images, enhance_follow_up_prompt
from app.core.config import settings

logger = logging.getLogger(__name__)

async def handle_trend_analysis(
    user_message: str, 
    params: Dict[str, Any], 
    user_needs_visuals: bool,
    stream_callback: Any = None
) -> Dict[str, Any]:
    """
    TREND_ANALYSIS niyetini işler.
    Intelligence servisinden veri çeker, GPT ile raporlar ve Fal.ai ile görsel üretir.
    """
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

    # 1. Intelligence servisinden raw tahminleri çek ve Semantic Matcher ile filtrele/sırala
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

    # 2. Intelligence verileri + GPT-4o = zengin trend raporu
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

## 3. Fiyatlandırma ve Maliyet Tahmini ({budget_segment})
- Yukarıdaki fiyat dağılımını yorumla
- Hedef kitle ({target_audience}) için fiyatlandırma stratejisi
- **Üretim Maliyeti Tahmini:** Kumaş tipi ({material}), işçilik ve güncel piyasa koşullarını dikkate alarak ürün başına yaklaşık üretim maliyetini TL (Türk Lirası) cinsinden belirt (örn: "Ortalama 150 - 250 TL arası").

## 4. Aksiyon Maddeleri
1. [Veri destekli somut tavsiye]
2. [Veri destekli somut tavsiye]
3. [Opsiyonel 3. tavsiye]

KRİTİK KURALLAR:
- Her iddiayı yukarıdaki verilerle destekle (skor, fiyat, renk istatistikleri)
- Top 5 ürün tablosunu doğrudan dahil et
- Kullanıcı eğer 2 ay sonrası veya gelecek ile ilgili soruyorsa, öngörülerini bu yönde vurgula.
- Hayali ürün verisi UYDURMA, sadece verilen istatistikleri kullan"""

    try:
        if stream_callback:
            response_stream = openai_client.chat.completions.create(
                model=get_model_name(),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.5,
                stream=True
            )
            content = ""
            for chunk in response_stream:
                if chunk.choices[0].delta.content:
                    content_chunk = chunk.choices[0].delta.content
                    content += content_chunk
                    import asyncio
                    if asyncio.iscoroutinefunction(stream_callback):
                        await stream_callback(content_chunk)
                    else:
                        stream_callback(content_chunk)
        else:
            response = openai_client.chat.completions.create(
                model=get_model_name(),
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
        if stream_callback:
            import asyncio
            if asyncio.iscoroutinefunction(stream_callback):
                await stream_callback(content)
            else:
                stream_callback(content)

    # --- FAL.AI GÖRSEL ENTEGRASYONU ---
    image_urls = []
    
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
            
        ai_generated = generate_ai_images(prompt_items)
        import asyncio
        if asyncio.iscoroutinefunction(generate_ai_images):
            ai_generated = await generate_ai_images(prompt_items)
        else:
            ai_generated = generate_ai_images(prompt_items)
            
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
