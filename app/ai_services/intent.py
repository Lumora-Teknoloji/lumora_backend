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

    recent_history = chat_history[-10:] if chat_history else []  # 10 mesaj bağlam
    history_text = json.dumps(recent_history, ensure_ascii=False)

    # --- GÜNCELLEME: Daha akıllı niyet sınıflandırma ---
    system_prompt = f"""
    You are an intent classifier for a Fashion AI assistant.
    
    CONVERSATION HISTORY: {history_text}
    CURRENT USER MESSAGE: "{message}"

    CATEGORIES (choose ONE):
    
    1. IMAGE_MODIFICATION: User wants to MODIFY/CHANGE a PREVIOUS generated image.
       Examples: "aynısından bir daha", "farklı açıdan", "bunu kırmızı yap", "daha koyu olsun", "tekrar üret"
    
    2. IMAGE_GENERATION: User gives EXPLICIT command to CREATE/DRAW NEW images.
       Examples: "v yaka çiz", "3 tane elbise göster", "kırmızı ceket üret", "bana bir gömlek tasarla"
    
    3. MARKET_RESEARCH: User gives EXPLICIT and SPECIFIC command for trend analysis or report.
       Examples: "2026 abiye trendleri analiz et", "Spor ayakkabı modası raporu hazırla", "Kadın mont trendlerini araştır"
       NOTE: User must give a SPECIFIC topic. Vague requests are NOT market research.
    
    4. FOLLOW_UP: User refers to specific data in a PREVIOUS report (non-image related).
       Examples: "Bu fiyat neden yüksek?", "Kumaşı değiştir", "Daha fazla detay ver"
    
    5. GENERAL_CHAT: ALL of the following cases:
       - Greetings: "Merhaba", "Selam", "Nasılsın"
       - Questions ending with "?" that ask for permission or preference
       - Messages containing: "konuşalım mı", "ne dersin", "isteklerime göre", "sana göre"
       - Meta-questions about AI: "Nasıl çalışıyorsun?", "Ne yapabilirsin?"
       - Vague/unclear requests that need clarification
       - When in doubt, choose GENERAL_CHAT

    CRITICAL RULES:
    - If message ends with "mı?", "mi?", "mu?", "mü?" (Turkish question suffix) → likely GENERAL_CHAT
    - If user asks for permission or says "isteklerime göre" → GENERAL_CHAT (they want dialogue first)
    - MARKET_RESEARCH requires a SPECIFIC product/topic command, not just mentioning "trend"
    - When uncertain, prefer GENERAL_CHAT over MARKET_RESEARCH (ask for clarification)

    OUTPUT: Return ONLY one category name.
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
        return "GENERAL_CHAT"  # Güvenli varsayılan: sohbet et, rapor üretme
    except Exception as e:
        logger.error(f"Niyet analizi hatası: {e}")
        return "GENERAL_CHAT"  # Hata durumunda da güvenli varsayılan


async def handle_general_chat(message: str, chat_history: List[Dict[str, str]] = [], stream_callback=None) -> str:
    """Genel sohbet mesajlarını işler (Streaming + Tavily desteği ile)"""
    if not openai_client:
        return "Üzgünüm, şu an yanıt veremiyorum."

    from .clients import tavily_client  # Tavily import

    current_time = datetime.now().strftime("%d %B %Y, %A - Saat: %H:%M")
    
    # Bilgi araması gerekip gerekmediğini kontrol et
    web_context = ""
    needs_search_keywords = [
        "var mı", "nedir", "nasıl", "ne demek", "örnek", "hangi", 
        "kim", "ne zaman", "nerede", "sistem", "platform", "uygulama",
        "şirket", "marka", "rakip", "alternatif", "fark", "karşılaştır"
    ]
    
    message_lower = message.lower()
    needs_web_search = any(kw in message_lower for kw in needs_search_keywords)
    
    # Tavily ile web araması yap (eğer gerekiyorsa)
    if needs_web_search and tavily_client:
        try:
            # Sohbet bağlamından konu çıkar
            context_text = " ".join([m.get("content", "")[:100] for m in chat_history[-3:]])
            search_query = f"{message} {context_text[:100]}"
            
            search_result = tavily_client.search(
                query=search_query,
                search_depth="basic",
                max_results=3
            )
            
            if search_result.get('results'):
                web_context = "\n\n📌 WEB ARAŞTIRMASI SONUÇLARI:\n"
                for res in search_result['results'][:3]:
                    title = res.get('title', 'Kaynak')
                    content = res.get('content', '')[:300]
                    url = res.get('url', '')
                    web_context += f"• {title}: {content}...\n  Kaynak: {url}\n\n"
        except Exception as e:
            logger.warning(f"Tavily arama hatası: {e}")
            web_context = ""

    # System prompt (web context ile zenginleştirilmiş)
    system_prompt = f"""
    Sen Lumora AI, Kıdemli Moda Stratejisi Asistanısın.
    
    SİSTEM BİLGİSİ:
    - ŞU ANKİ TARİH VE SAAT: {current_time}
    
    YETENEKLERİN:
    1. Web araması ile güncel bilgi sağlama
    2. Moda ve trend analizi
    3. Görsel tasarım önerileri
    
    {f"WEB ARAŞTIRMASI VERİSİ (Bu bilgileri kullanarak cevap ver):{web_context}" if web_context else ""}
    
    GÖREVİN: 
    Kullanıcının sorusuna samimi, profesyonel ve yardımsever bir dille cevap ver.
    - ÖNCEKİ SOHBET BAĞLAMINI MUTLAKA DİKKATE AL.
    - Web araştırması verisi varsa, bu bilgileri kullanarak GERÇEK ve DOĞRU bilgi ver.
    - Kaynak gösterirken "[Kaynak](URL)" formatında link ver.
    - Eğer "nasıl çalıştığını" sorarsa yöntemlerini anlat.
    - Sohbet et, rapor formatı kullanma.
    """

    # Chat history'den son 20 mesajı al (genişletilmiş hafıza)
    messages = [{"role": "system", "content": system_prompt}]
    for msg in chat_history[-20:]:
        role = msg.get("sender", msg.get("role", "user"))
        # 'ai' -> 'assistant' dönüşümü
        if role == "ai":
            role = "assistant"
        elif role not in ["user", "assistant"]:
            role = "user"
        content = msg.get("content", "")
        if content:
            messages.append({"role": role, "content": content})
    
    # Mevcut mesajı ekle
    messages.append({"role": "user", "content": message})

    try:
        # Eğer callback varsa streaming yap
        if stream_callback:
            response_stream = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
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
                messages=messages,
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
    for msg in chat_history[-20:]:  # Son 20 mesaj bağlam
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