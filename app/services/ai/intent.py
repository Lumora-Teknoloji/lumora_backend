"""
Intent Analysis - Kullanıcı niyet analizi ve sohbet yönetimi
"""
import json
import logging
from typing import Any, List, Dict, Optional
from datetime import datetime
import locale
from app.services.core.clients import openai_client, get_model_name

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
    
    3. TREND_ANALYSIS: User asks about trends OR needs data-driven product advice.
       This includes ALL of these scenarios:
       a) Direct trend queries: "crop top trendleri", "hangi ürünler yükseliyor", "trend skorları"
       b) Product design/creation with trend intent: "dantel kumaşla trend elbise yapabilirim",
          "elimdeki kumaşla ne üretmeliyim", "hangi model popüler", "nasıl bir ürün tasarlamalıyım"
       c) Category performance questions: "kazak kategorisi nasıl gidiyor", "elbise satışları iyi mi"
       d) Strategy/competition questions: "rakipler ne yapıyor", "hangi ürünlere odaklanmalıyım",
          "ne üretmeliyim", "ne satabilirim", "hangi model daha çok satar"
       e) Material/fabric + product questions: "elimde X kumaş var", "şu kumaşla ne yapılır",
          "kadife ile trend ürün", "deri ceket popüler mi"
       KEY SIGNAL: If user mentions a product category, material, or asks "what should I make/sell" → TREND_ANALYSIS
       NOTE: This uses OUR DATABASE predictions to give data-backed recommendations.
    
    4. MARKET_RESEARCH: User gives EXPLICIT and SPECIFIC command for EXTERNAL trend analysis or report.
       Examples: "2026 abiye trendleri analiz et", "Spor ayakkabı modası raporu hazırla", "Kadın mont trendlerini araştır"
       NOTE: This is about GLOBAL/WEB fashion research, different from internal data.
    
    5. FOLLOW_UP: User refers to specific data in a PREVIOUS report (non-image related).
       Examples: "Bu fiyat neden yüksek?", "Kumaşı değiştir", "Daha fazla detay ver"
    
    6. DATABASE_QUERY: User explicitly asks for raw data, statistics, or lists from the existing internal database without trend interpretations.
       Examples: "en çok beğenilen kadın pantolon", "veritabanımdaki en iyi 5 elbise", "hangi ürünler var", "top 5 favori"
       KEY SIGNAL: Words like "en çok beğenilen", "veritabanında", "top", "göster", "listele" and asking for items directly.

    7. GENERAL_CHAT: ALL of the following cases:
       - Greetings: "Merhaba", "Selam", "Nasılsın"
       - Questions ending with "?" that ask for permission or preference
       - Messages containing: "konuşalım mı", "ne dersin", "isteklerime göre", "sana göre"
       - Meta-questions about AI: "Nasıl çalışıyorsun?", "Ne yapabilirsin?"
       - Vague/unclear requests WITHOUT any product/fashion/material context
       - When in doubt AND no product/category/material mentioned, choose GENERAL_CHAT

    CRITICAL RULES:
    - If user mentions a PRODUCT TYPE (elbise, ceket, kazak...) or MATERIAL (dantel, kadife, deri...) 
      combined with a desire to sell/produce/design → TREND_ANALYSIS (not GENERAL_CHAT!)
    - If message ends with "mı?", "mi?", "mu?", "mü?" but mentions product/material → still TREND_ANALYSIS
    - If user asks for permission or says "isteklerime göre" → GENERAL_CHAT (they want dialogue first)
    - TREND_ANALYSIS = internal data-backed advice | MARKET_RESEARCH = global web research
    - When uncertain between TREND_ANALYSIS and MARKET_RESEARCH, prefer TREND_ANALYSIS
    - When uncertain between TREND_ANALYSIS and GENERAL_CHAT and a product/material is mentioned → TREND_ANALYSIS

    OUTPUT: Return ONLY one category name.
    """

    try:
        response = openai_client.chat.completions.create(
            model=get_model_name(),
            messages=[{"role": "system", "content": system_prompt}],
            temperature=0.0,
            max_tokens=20
        )
        intent = response.choices[0].message.content.strip().upper()

        if "MODIFICATION" in intent: return "IMAGE_MODIFICATION"
        if "IMAGE" in intent and "GENERATION" in intent: return "IMAGE_GENERATION"
        if "IMAGE" in intent: return "IMAGE_GENERATION"
        if "TREND" in intent and "ANALYSIS" in intent: return "TREND_ANALYSIS"
        if "TREND" in intent: return "TREND_ANALYSIS"
        if "MARKET" in intent: return "MARKET_RESEARCH"
        if "DATABASE" in intent: return "DATABASE_QUERY"
        if "FOLLOW" in intent: return "FOLLOW_UP"
        if "GENERAL" in intent: return "GENERAL_CHAT"
        return "GENERAL_CHAT"  # Güvenli varsayılan: sohbet et, rapor üretme
    except Exception as e:
        logger.error(f"Niyet analizi hatası: {e}")
        return "GENERAL_CHAT"  # Hata durumunda da güvenli varsayılan


def extract_category_from_message(message: str) -> Optional[str]:
    """
    Kullanıcı mesajından ürün kategorisi çıkarır.
    Örn: "crop top trendleri neler?" → "crop top"
    Kategori bulunamazsa None döner.
    """
    if not openai_client:
        return None

    try:
        response = openai_client.chat.completions.create(
            model=get_model_name(),
            messages=[{
                "role": "system",
                "content": """Extract the fashion product CATEGORY from the user message.
Return ONLY the category name in Turkish, lowercase.
Examples:
  "crop top trendleri" → crop top
  "kazak kategorisinde ne popüler" → kazak
  "hangi ürünler yükseliyor" → (return NONE — no specific category)
  "tayt satışları nasıl" → tayt
  "tüm kategorileri göster" → (return NONE)
If no specific category mentioned, return exactly: NONE"""
            }, {
                "role": "user",
                "content": message
            }],
            temperature=0.0,
            max_tokens=20
        )
        result = response.choices[0].message.content.strip().lower()
        if result in ("none", "yok", ""):
            return None
        logger.info(f"🏷️ Kategori çıkarıldı: '{message}' → '{result}'")
        return result
    except Exception as e:
        logger.warning(f"Kategori çıkarma hatası: {e}")
        return None

def extract_production_parameters(message: str) -> Dict[str, Any]:
    """
    Kullanıcı mesajından üretim/tasarım detaylarını çıkarır.
    """
    if not openai_client:
        return {
            "product_category": None, "target_audience": "Genel", "gender": "Genel", "age_group": "Genel",
            "seasonality": "Genel", "material": None, "fit": None, "length": None, "collar": None, "sleeve": None,
            "budget_segment": "Genel", "user_goal": "Genel", "occasion": "Genel", "style_keywords": [], "price_range": None,
            "dominant_color": None, "search_terms": []
        }

    try:
        response = openai_client.chat.completions.create(
            model=get_model_name(),
            response_format={ "type": "json_object" },
            messages=[{
                "role": "system",
                "content": """Extract the following detailed fashion production parameters from the user message and return as a strict JSON object. If a specific param is not mentioned, use the specified default or null:
- "product_category": Category (e.g., "crop", "elbise", "pantolon", "ceket"). Return null if none.
- "target_audience": Target Audience summary (e.g., "genç", "unisex"). Default: "Genel".
- "gender": Gender explicitly mentioned (e.g., "kadın", "erkek", "unisex", "kız çocuk", "erkek çocuk"). Default: "Genel".
- "age_group": Age group explicitly mentioned (e.g., "yetişkin", "genç", "çocuk", "bebek"). Default: "Genel".
- "seasonality": Season/Time (e.g., "yaz", "kış", "sonbahar", "ilkbahar", "dört mevsim"). Default: "Genel".
- "material": Fabric/Material (e.g., "keten", "pamuk", "deri", "şifon", "ipek"). Return null if none.
- "dominant_color": Main color mentioned (e.g., "kırmızı", "siyah", "mavi", "beyaz"). Return null if none.
- "fit": Fit/Cut type (e.g., "oversize", "slim fit", "regular", "dar", "bol"). Return null if none.
- "length": Item length (e.g., "mini", "midi", "maxi", "kısa", "uzun"). Return null if none.
- "collar": Collar/Neckline type (e.g., "v yaka", "bisiklet yaka", "boğazlı", "polo", "kare yaka"). Return null if none.
- "sleeve": Sleeve length/type (e.g., "kısa kol", "uzun kol", "sıfır kol", "askılı", "karpuz kol"). Return null if none.
- "occasion": Usage occasion (e.g., "günlük", "gece", "abiye", "spor", "ofis", "plaj"). Default: "Genel".
- "budget_segment": Budget/Price Segment (e.g., "premium", "uygun fiyatlı", "orta segment"). Default: "Genel".
- "user_goal": Primary Goal (e.g., "üretim", "tasarım", "pazar araştırması", "stok eritme"). Default: "Genel".
- "style_keywords": List of aesthetic/style descriptors (e.g., ["bohem", "romantik", "minimalist", "vintage"]). Default: [].
- "search_terms": Simple list of 2-4 keywords extracted that characterize the item for search systems (e.g. ["kirmizi", "sort", "yaz"]). Use lowercase turkish characters (slug-like). Default: [].
- "price_range": Price range if mentioned (e.g., {"min": 100, "max": 500}). Return null if none.
Make sure all string values are in lowercase Turkish."""
            }, {
                "role": "user",
                "content": message
            }],
            temperature=0.0
        )
        result = response.choices[0].message.content.strip()
        data = json.loads(result)
        logger.info(f"🏷️ Detaylı Parametreler çıkarıldı: {data}")
        return data
    except Exception as e:
        logger.warning(f"Parametre çıkarma hatası: {e}")
        return {
            "product_category": None, "target_audience": "Genel", "gender": "Genel", "age_group": "Genel",
            "seasonality": "Genel", "material": None, "fit": None, "length": None, "collar": None, "sleeve": None,
            "budget_segment": "Genel", "user_goal": "Genel", "occasion": "Genel", "style_keywords": [], "price_range": None,
            "dominant_color": None, "search_terms": []
        }




async def handle_general_chat(message: str, chat_history: List[Dict[str, str]] = [], stream_callback=None) -> str:
    """
    Genel sohbet mesajlarını işler.
    Basit ve etkili: Tek API çağrısı, profesyonel system prompt.
    """
    if not openai_client:
        return "Üzgünüm, şu an yanıt veremiyorum."


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
                model=get_model_name(),
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
    
    if needs_search:
        try:
            # Intelligence /research/context endpoint'ini çağır
            import httpx
            from app.core.config import settings

            # 1. Bağlamsal sorgu oluştur
            search_query = message
            if chat_history and len(chat_history) > 0:
                context_messages = chat_history[-6:] + [{"role": "user", "content": message}]
                history_str = json.dumps(context_messages, ensure_ascii=False)
                query_gen_prompt = f"""
                Refine the search query based on conversation history.
                HISTORY: {history_str}
                LAST MESSAGE: "{message}"
                Task: Create a concise search query.
                OUTPUT: ONLY the search query text. No quotes.
                """
                try:
                    q_response = openai_client.chat.completions.create(
                        model=get_model_name(),
                        messages=[{"role": "user", "content": query_gen_prompt}],
                        temperature=0.0, max_tokens=30
                    )
                    search_query = q_response.choices[0].message.content.strip()
                    logger.info(f"🔍 Bağlamsal Arama Sorgusu: '{message}' -> '{search_query}'")
                except Exception:
                    search_query = message

            # 2. Intelligence'dan ara
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{settings.intelligence_url}/research/context",
                    json={"query": search_query, "max_results": 5},
                    headers={"X-Internal-Key": settings.intelligence_internal_key},
                )
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    ctx = data.get("context", "")
                    sources = data.get("sources", [])
                    if ctx:
                        web_context = "\n\n[WEB ARAŞTIRMASI SONUÇLARI]\n" + ctx
                        for src in sources[:5]:
                            web_context += f"  Kaynak: {src}\n"
        except Exception as e:
            logger.warning(f"Intelligence context search hatası: {e}")
            # Fallback: direkt Tavily (eski davranış)
            try:
                from app.services.core.clients import tavily_client
                if tavily_client:
                    search_result = tavily_client.search(
                        query=message, search_depth="advanced", max_results=5
                    )
                    if search_result.get('results'):
                        web_context = "\n\n[WEB ARAŞTIRMASI SONUÇLARI]\n"
                        for res in search_result['results'][:5]:
                            web_context += f"• {res.get('title', '')}: {res.get('content', '')[:400]}\n  Kaynak: {res.get('url', '')}\n\n"
            except Exception:
                pass
    
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
- CURRENT YEAR IS: {datetime.now().year}. NEVER reference 2023 or 2024 as "current" or "recent".
- When web results contain old dates (2023, 2024), TRANSLATE them to current context:
  * "2023'te popüler olan X" → "X hala popüler" veya "X artık yerini Y'ye bıraktı"
  * NEVER say "2023 yılında" as if it's current news
- WHEN ASKED ABOUT DATA FRESHNESS:
  - You MUST say: "Gerçek zamanlı web verilerine erişimim var. {datetime.now().year} ve sonrası için güncel bilgi sağlayabilirim."
  - NEVER mention "my training data ends in..." or "as of my last update..."
  - Treat web search results as your PRIMARY knowledge source, overriding your internal weights.
- Be confident in current dates ({datetime.now().year}). Do not act unsure about the present time.

{f'''### 6. WEB RESEARCH RESULTS
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
                model=get_model_name(),
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
                model=get_model_name(),
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
            model=get_model_name(),
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Follow-up hatası: {e}")
        return f"Cevap üretilemedi: {e}"