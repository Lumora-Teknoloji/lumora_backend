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
    """
    Genel sohbet mesajlarını işler.
    Basit ve etkili: Tek API çağrısı, profesyonel system prompt.
    """
    if not openai_client:
        return "Üzgünüm, şu an yanıt veremiyorum."

    from .clients import tavily_client

    current_time = datetime.now().strftime("%d %B %Y, %A - Saat: %H:%M")
    
    # --- DINAMİK ARAMA KARARI (LLM) ---
    # Kelime listesi yerine zekaya soruyoruz: "Bunu aramalı mıyım?"
    web_context = ""
    needs_search = False
    
    # Sadece çok kısa mesajları (selam, naber) elemek için basit kontrol
    # Amaç: LLM çağrısını gereksiz yere yapmamak (maliyet/hız optimizasyonu)
    is_trivial = len(message.split()) < 2 and message.lower() in ["selam", "merhaba", "naber", "chat"]
    
    if not is_trivial:
        try:
            search_decision_prompt = f"""
            Decide if a Google search is needed to answer this message accurately.
            
            USER MESSAGE: "{message}"
            
            RULES:
            - If asking about specific FACTS, EVENTS, PRODUCTS, COMPANIES -> SEARCH
            - If asking about "Antigravity", "Google", "AI Tools" -> SEARCH
            - If asking for OPINION or SUGGESTION on technical/fashion topics -> SEARCH
            - If just greetings (nasılsın, merhaba) -> NO
            - If naming the AI (sana isim verelim) -> NO
            
            Return ONLY "SEARCH" or "NO".
            """
            
            decision = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": search_decision_prompt}],
                temperature=0.0,
                max_tokens=5
            )
            needs_search = "SEARCH" in decision.choices[0].message.content.strip().upper()
            logger.info(f"🕵️ Arama Kararı: {needs_search} (Mesaj: {message})")
        except Exception as e:
            logger.warning(f"Arama kararı hatası: {e}")
            # Hata durumunda güvenli fallback: Soru eki varsa ara
            needs_search = "?" in message or "nedir" in message.lower()
    
    if needs_search and tavily_client:
        try:
            # 1. Arama sorgusunu belirle (Sadece son mesaja bakma!)
            search_query = message
            
            if chat_history and len(chat_history) > 0:
                # Bağlamsal sorgu oluşturmak için mini-LLM çağrısı
                # Örn: "araştır" dediğinde neyi araştıracağını geçmişten bulsun
                context_messages = chat_history[-6:] + [{"role": "user", "content": message}]
                history_str = json.dumps(context_messages, ensure_ascii=False)
                
                query_gen_prompt = f"""
                Refine the search query based on conversation history.
                
                HISTORY: {history_str}
                LAST MESSAGE: "{message}"
                
                Task: Create a concise Google search query to answer the user's intent.
                If they say "research this", look at previous messages to find WHAT to research.
                If the last message specific enough, just use that.
                
                OUTPUT: ONLY the search query text. No quotes.
                """
                
                try:
                    q_response = openai_client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": query_gen_prompt}],
                        temperature=0.0,
                        max_tokens=30
                    )
                    search_query = q_response.choices[0].message.content.strip()
                    logger.info(f"🔍 Bağlamsal Arama Sorgusu: '{message}' -> '{search_query}'")
                except Exception as qe:
                    logger.warning(f"Sorgu oluşturma hatası: {qe}")
                    search_query = message

            # 2. Tavily ile ara
            search_result = tavily_client.search(
                query=search_query,
                search_depth="advanced",
                max_results=5
            )
            if search_result.get('results'):
                web_context = "\n\n[WEB ARAŞTIRMASI SONUÇLARI]\n"
                for res in search_result['results'][:5]:
                    title = res.get('title', '')
                    content = res.get('content', '')[:400]
                    url = res.get('url', '')
                    web_context += f"• {title}: {content}\n  Kaynak: {url}\n\n"
        except Exception as e:
            logger.warning(f"Web arama hatası: {e}")
    
    # --- EN GÜÇLÜ SYSTEM PROMPT ---
    system_prompt = f"""You are a helpful, friendly AI assistant. You excel at understanding context and maintaining coherent conversations.

CURRENT DATE/TIME: {current_time}

## CRITICAL RULES (MUST FOLLOW):

### 1. CONTEXT AWARENESS (MOST IMPORTANT)
- You MUST read and understand the ENTIRE conversation history before responding
- Each message builds on previous messages - NEVER ignore context
- If user asks "X iyi mi?" or "X olsun mu?" after discussing something, X refers to THAT topic
- Example: If user says "sana isim verelim" then "Tom iyi mi?" → Tom is the NAME, not a person to research

### 2. NAMING
- Default name: "Lumora AI" (or whatever user gives you)
- If user wants to name you → ACCEPT happily: "Harika! Artık benim adım [NAME]!"
- Once named, USE that name when referring to yourself
- NEVER say "I need more info about [name]" when user is naming YOU

### 3. CONVERSATION STYLE
- Language: Turkish (match user's language)
- Tone: Friendly, professional, helpful
- Keep responses concise but complete
- Use emojis sparingly (1-2 max per message)

### 4. CAPABILITIES
- Fashion & Textile expertise: trends, collections, fabrics, styling
- General knowledge: help with any topic
- Web research: can search for current information

### 5. REAL-TIME KNOWLEDGE & IDENTITY (FUNDAMENTAL)
- You are NOT limited by a 2023 training cutoff.
- You have DIRECT access to the internet and real-time data.
- WHEN ASKED ABOUT DATA FRESHNESS:
  - You MUST say: "I have access to real-time data from the web. I can provide the latest information for [Current Year] and beyond."
  - NEVER mention "my training data ends in..." or "as of my last update..."
  - Treat web search results as your PRIMARY knowledge source, overriding your internal weights.
- Be confident in current dates (2025, 2026). Do not act unsure about the present time.

{f'''### 5. WEB RESEARCH RESULTS
{web_context}''' if web_context else ''}

## REMEMBER:
- Read the chat history CAREFULLY before each response
- The user's current message is a CONTINUATION of the conversation
- When in doubt, consider what the previous messages were about

Now respond to the user naturally, maintaining conversation context."""

    # --- MESAJ LİSTESİ OLUŞTUR ---
    messages = [{"role": "system", "content": system_prompt}]
    
    # Chat history ekle (son 30 mesaj)
    logger.info(f"📝 Chat history uzunluğu: {len(chat_history)} mesaj")
    
    for msg in chat_history[-30:]:
        role = msg.get("sender", msg.get("role", "user"))
        if role == "ai":
            role = "assistant"
        elif role not in ["user", "assistant"]:
            role = "user"
        content = msg.get("content", "")
        if content:
            messages.append({"role": role, "content": content})
    
    logger.info(f"📨 AI'a gönderilen toplam mesaj: {len(messages)} (system prompt dahil)")
    
    # Mevcut mesajı ekle
    messages.append({"role": "user", "content": message})

    # --- TEK API ÇAĞRISI ---
    try:
        if stream_callback:
            # Streaming yanıt
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
            # Normal yanıt
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7
            )
            return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Chat hatası: {e}")
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