"""
Intent Analysis - Kullanıcı niyet analizi ve sohbet yönetimi
"""
import json
import logging
from typing import List, Dict
from datetime import datetime
import locale
from .clients import openai_client

logger = logging.getLogger(__name__)

try:
    locale.setlocale(locale.LC_ALL, 'tr_TR.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'tr_TR')
    except Exception as e:
        logger.warning(f"Locale setting error: {e}")

def analyze_user_intent(message: str, chat_history: List[Dict[str, str]] = []) -> str:
    """Kullanıcı mesajının niyetini analiz eder"""
    if not openai_client:
        return "MARKET_RESEARCH"

    recent_history = chat_history[-3:] if chat_history else []
    history_text = json.dumps(recent_history, ensure_ascii=False)

    # --- GÜNCELLEME: IMAGE_GENERATION ve IMAGE_MODIFICATION kategorileri eklendi ---
    system_prompt = f"""
    You are an intent classifier for a Fashion AI.
    HISTORY: {history_text}
    CURRENT USER MESSAGE: "{message}"

    CATEGORIES:
    1. IMAGE_MODIFICATION: User wants to MODIFY/CHANGE a PREVIOUS generated image (e.g., "aynısından bir daha", "farklı açıdan", "bunu kırmızı yap", "daha koyu olsun", "bu görseli tekrar üret", "bir tane daha").
    2. IMAGE_GENERATION: User asks to GENERATE/CREATE/DRAW NEW images from scratch (e.g., "v yaka çiz", "3 tane elbise göster", "kırmızı ceket üret", "bana bir gömlek tasarla", "5 adet polo yaka").
    3. MARKET_RESEARCH: User explicitly asks for a NEW trend analysis, fashion report, or market research (e.g., "Abiye trendleri", "Spor ayakkabı modası").
    4. FOLLOW_UP: User refers to specific data in the PREVIOUS report (non-image related, e.g., "Why is this price high?", "Change the fabric").
    5. GENERAL_CHAT: 
       - Greetings, Identity, Time/Date.
       - METHODOLOGY: "How do you work?", "How do you find trends?".
       - META-QUESTIONS: Questions about the AI itself, its accuracy, opinions, or abstract requests.

    IMPORTANT: If user refers to a previous image (uses words like "aynı", "bu", "bunu", "tekrar", "farklı açı", "değiştir", "bir daha", "bir tane daha"), choose IMAGE_MODIFICATION.

    OUTPUT: Return ONLY one of the category names above.
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0.0,
            max_tokens=20
        )
        intent = response.choices[0].message.content.strip().upper()

        if "MODIFICATION" in intent: return "IMAGE_MODIFICATION"
        if "IMAGE" in intent and "GENERATION" in intent: return "IMAGE_GENERATION"
        if "IMAGE" in intent: return "IMAGE_GENERATION"
        if "MARKET" in intent: return "MARKET_RESEARCH"
        if "FOLLOW" in intent: return "FOLLOW_UP"
        if "GENERAL" in intent: return "GENERAL_CHAT"
        return "MARKET_RESEARCH"
    except Exception as e:
        logger.error(f"Niyet analizi hatası: {e}")
        return "MARKET_RESEARCH"


async def handle_general_chat(message: str, stream_callback=None) -> str:
    """Genel sohbet mesajlarını işler (Streaming desteği ile)"""
    if not openai_client:
        return "Üzgünüm, şu an yanıt veremiyorum."

    current_time = datetime.now().strftime("%d %B %Y, %A - Saat: %H:%M")

    # --- GÜNCELLEME: Botun karakteri ve cevap yeteneği güçlendirildi ---
    system_prompt = f"""
    Sen Kıdemli Moda Stratejisi Asistanısın.
    
    SİSTEM BİLGİSİ:
    - ŞU ANKİ TARİH VE SAAT: {current_time}
    
    YETENEKLERİN:
    1. Global Tarama (Tavily), Pazar Analizi, Görsel Zeka (Vision) ve AI Tasarım (Flux) kullanırsın.
    
    GÖREVİN: 
    Kullanıcının sorusuna samimi, profesyonel ve yardımsever bir dille cevap ver.
    - Eğer "nasıl çalıştığını" sorarsa yöntemlerini anlat.
    - Eğer "oran ver", "doğruluk payı" gibi soyut sorular sorarsa: Kendine güvenen ama mütevazı bir tahmin yap (Örn: "Moda sübjektiftir ama verilerim %90+ isabetlidir" gibi).
    - Sohbet et, rapor formatı kullanma.
    """

    try:
        # Eğer callback varsa streaming yap
        if stream_callback:
            response_stream = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.7,
                stream=True
            )
            
            full_content = ""
            for chunk in response_stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    await stream_callback(content)
            return full_content
            
        else:
            # Normal (non-streaming)
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
        logger.error(f"Genel sohbet hatası: {e}")
        return "Üzgünüm, şu an yanıt veremiyorum."


async def handle_follow_up(message: str, chat_history: List[Dict[str, str]]) -> str:
    """Takip mesajlarını işler"""
    if not openai_client:
        return "Sistem hatası."

    current_year = datetime.now().year

    # --- GÜNCELLEME: Sadece rapor verisine sıkışıp kalmaması sağlandı ---
    system_msg = f"""
    Sen Kıdemli Moda Stratejistisin. (Güncel Yıl: {current_year})
    GÖREVİN: Sohbet geçmişindeki konularla ilgili kullanıcının sorusunu yanıtla.
    Eğer kullanıcı raporda olmayan bir şey sorarsa (fikir, yorum vb.), moda bilginle mantıklı bir cevap uydur. "Veri yok" deyip kestirip atma.
    """

    messages = [{"role": "system", "content": system_msg}]
    for msg in chat_history[-6:]:
        if msg.get("role") in ["user", "assistant"]:
            messages.append({"role": msg.get("role"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": message})

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Follow-up hatası: {e}")
        return f"Cevap üretilemedi: {e}"