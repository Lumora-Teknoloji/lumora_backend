"""
Intent Analysis - Kullanıcı niyet analizi ve sohbet yönetimi
"""
import json
import logging
from typing import List, Dict
from .clients import openai_client

logger = logging.getLogger(__name__)


def analyze_user_intent(message: str, chat_history: List[Dict[str, str]] = []) -> str:
    """Kullanıcı mesajının niyetini analiz eder"""
    if not openai_client:
        return "MARKET_RESEARCH"

    recent_history = chat_history[-3:] if chat_history else []
    history_text = json.dumps(recent_history, ensure_ascii=False)

    system_prompt = f"""
    You are an intent classifier for a Fashion AI.
    HISTORY: {history_text}
    CURRENT USER MESSAGE: "{message}"

    CATEGORIES:
    1. MARKET_RESEARCH: User asks for a NEW topic analysis (e.g., "Abiye trendleri", "Spor ayakkabı modası").
    2. FOLLOW_UP: User refers to the previous topic/report OR asks about the results (e.g., "Why this price?", "Change color", "Draw this").
    3. GENERAL_CHAT: Greetings, "Who are you?", or general fashion knowledge.

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
        if "MARKET" in intent:
            return "MARKET_RESEARCH"
        if "FOLLOW" in intent:
            return "FOLLOW_UP"
        if "GENERAL" in intent:
            return "GENERAL_CHAT"
        return "MARKET_RESEARCH"
    except Exception as e:
        logger.error(f"Niyet analizi hatası: {e}")
        return "MARKET_RESEARCH"


def handle_general_chat(message: str) -> str:
    """Genel sohbet mesajlarını işler"""
    if not openai_client:
        return "Üzgünüm, şu an yanıt veremiyorum."
    
    system_prompt = "Sen Kıdemli Moda Stratejisisin. Kullanıcının sorularına profesyonel ve samimi cevap ver."
    try:
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
    """Takip mesajlarını işler (önceki konuya referans)"""
    if not openai_client:
        return "Sistem hatası."

    system_msg = """
    Sen Kıdemli Moda Stratejistisin.
    GÖREVİN: Sohbet geçmişindeki (History) rapor verilerine dayanarak kullanıcının sorusunu yanıtla.
    Yeni görsel istenirse onayla.
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

