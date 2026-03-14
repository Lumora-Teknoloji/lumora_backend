"""
Intelligence Formatter — Intelligence servis verilerini chatbot yanıtına uygun Markdown'a çevirir.

Kullanım:
    from .intelligence_formatter import get_intelligence_context
    context = await get_intelligence_context(category="crop top")
"""
import logging
from typing import Optional, List, Dict, Any

from app.services.intelligence_client import intelligence_client

logger = logging.getLogger(__name__)


# ─── Formatlayıcılar ──────────────────────────────────────────────────────────

def format_predictions_for_chat(predictions: List[Dict], category: Optional[str] = None) -> str:
    """Intelligence predict sonuçlarını zengin Markdown formatına çevirir."""
    if not predictions:
        return ""

    header = f"### 📊 Intelligence Trend Tahminleri"
    if category:
        header += f" — *{category}*"
    header += f"\n\n**{len(predictions)} ürün analiz edildi**\n\n"

    # Her ürün için detaylı kart
    items = []
    for i, p in enumerate(predictions, 1):
        label = p.get("trend_label", "—")
        emoji = {"TREND": "🔥", "POTANSIYEL": "📈", "STABIL": "➡️", "DUSEN": "📉"}.get(label, "❓")
        score = p.get("trend_score", 0)
        conf = p.get("confidence", 0)

        name = p.get("name") or f"Ürün #{p.get('product_id', '?')}"
        brand = p.get("brand") or "—"

        # Fiyat bilgisi
        price = p.get("price") or p.get("discounted_price")
        price_str = f"{price:.0f} TL" if price else "—"
        discount = p.get("discount_rate")
        if discount and discount > 0:
            price_str += f" (-%{discount:.0f})"

        # Stil özellikleri
        style_parts = []
        if p.get("dominant_color"):
            style_parts.append(f"Renk: {p['dominant_color']}")
        if p.get("fabric_type"):
            style_parts.append(f"Kumaş: {p['fabric_type']}")
        if p.get("fit_type"):
            style_parts.append(f"Kalıp: {p['fit_type']}")
        style_str = " | ".join(style_parts) if style_parts else ""

        # Performans metrikleri
        fav = p.get("favorite_count", 0)
        cart = p.get("cart_count", 0)
        view = p.get("view_count", 0)
        rating = p.get("avg_rating")
        rating_str = f"⭐ {rating:.1f}" if rating else ""
        rank = p.get("search_rank")

        item = f"**{i}. {name}** — {emoji} {label} (Skor: {score:.1f}, Güven: %{conf:.0f})\n"
        item += f"   Marka: **{brand}** | Fiyat: **{price_str}**\n"
        if style_str:
            item += f"   {style_str}\n"
        
        perf_parts = []
        if fav:
            perf_parts.append(f"❤️ {fav:,} favori")
        if cart:
            perf_parts.append(f"🛒 {cart:,} sepet")
        if view:
            perf_parts.append(f"👁️ {view:,} görüntülenme")
        if rating_str:
            perf_parts.append(rating_str)
        if rank:
            perf_parts.append(f"📍 Sıra: {rank}")
        if perf_parts:
            item += f"   {' | '.join(perf_parts)}\n"
        
        url = p.get("url")
        if url:
            item += f"   🔗 {url}\n"

        items.append(item)

    # Özet istatistikler
    trend_count = sum(1 for p in predictions if p.get("trend_label") == "TREND")
    pot_count = sum(1 for p in predictions if p.get("trend_label") == "POTANSIYEL")
    falling_count = sum(1 for p in predictions if p.get("trend_label") == "DUSEN")
    avg_score = sum(p.get("trend_score", 0) for p in predictions) / max(len(predictions), 1)

    # Fiyat aralığı
    prices = [p.get("price") or p.get("discounted_price") for p in predictions if p.get("price") or p.get("discounted_price")]
    price_range = f" | Fiyat: {min(prices):.0f}–{max(prices):.0f} TL" if prices else ""

    # Popüler renkler
    colors = [p.get("dominant_color") for p in predictions if p.get("dominant_color")]
    color_summary = ""
    if colors:
        from collections import Counter
        top_colors = Counter(colors).most_common(3)
        color_summary = f" | Popüler renkler: {', '.join(c[0] for c in top_colors)}"

    summary = f"\n**Özet:** 🔥 {trend_count} trend, 📈 {pot_count} potansiyel, 📉 {falling_count} düşen"
    summary += f" | Ort. skor: {avg_score:.1f}{price_range}{color_summary}\n"

    return header + "\n".join(items) + summary


def format_analysis_for_chat(analysis: Dict) -> str:
    """Tekil ürün analizini Markdown'a çevirir."""
    if not analysis or analysis.get("error"):
        return ""

    pid = analysis.get("product_id", "?")
    label = analysis.get("trend_label", "UNKNOWN")
    score = analysis.get("trend_score")
    conf = analysis.get("confidence")
    signals = analysis.get("signals", {})
    data_pts = analysis.get("data_points", 0)

    emoji = {"TREND": "🔥", "POTANSIYEL": "📈", "STABIL": "➡️", "DUSEN": "📉"}.get(label, "❓")

    text = f"### 🔍 Ürün #{pid} — Detaylı Analiz\n\n"
    text += f"- **Trend Etiketi:** {emoji} {label}\n"
    if score is not None:
        text += f"- **Trend Skoru:** {score:.1f}/100\n"
    if conf is not None:
        text += f"- **Güven:** %{conf:.0f}\n"
    text += f"- **Veri Noktası:** {data_pts} gün\n"

    if signals:
        cat = signals.get("category", "")
        demand = signals.get("ensemble_demand", 0)
        if cat:
            text += f"- **Kategori:** {cat}\n"
        if demand:
            text += f"- **Tahmini Talep:** {demand:.1f}\n"

    return text


def format_alerts_for_chat(alerts: List[Dict]) -> str:
    """Aktif alertleri Markdown'a çevirir."""
    if not alerts:
        return ""

    text = "### ⚠️ Aktif Uyarılar\n\n"
    for a in alerts[:5]:
        atype = a.get("type", "unknown")
        msg = a.get("message", "")
        cat = a.get("category", "")
        emoji = "🚨" if atype == "rank_spike" else "⚡"
        text += f"- {emoji} **{cat}**: {msg}\n"

    return text


# ─── Ana Fonksiyon ─────────────────────────────────────────────────────────────

async def get_intelligence_context(
    category: Optional[str] = None,
    top_n: int = 20,
    include_alerts: bool = True,
) -> str:
    """
    Intelligence servisinden veri çekip chatbot'a uygun Markdown context üretir.
    Intelligence kapalıysa boş string döner (graceful fallback).
    """
    parts = []

    try:
        # 1. Trend tahminleri
        predictions = await intelligence_client.predict(category=category, top_n=top_n)
        if predictions:
            parts.append(format_predictions_for_chat(predictions, category))
            logger.info(f"📊 Intelligence context: {len(predictions)} tahmin alındı (category={category})")

        # 2. Alertler
        if include_alerts:
            alerts = await intelligence_client.get_alerts(unread_only=True)
            if alerts:
                parts.append(format_alerts_for_chat(alerts))

    except Exception as e:
        logger.warning(f"Intelligence context alınamadı (normal — servis kapalı olabilir): {e}")
        return ""

    return "\n\n".join(parts)


async def get_intelligence_product_context(product_id: int) -> str:
    """Tekil ürün analizi için Intelligence context üretir."""
    try:
        analysis = await intelligence_client.analyze(product_id)
        if analysis and not analysis.get("error"):
            return format_analysis_for_chat(analysis)
    except Exception as e:
        logger.warning(f"Intelligence ürün analizi alınamadı: {e}")
    return ""
