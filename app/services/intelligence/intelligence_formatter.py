"""
Intelligence Formatter — Intelligence servis verilerini chatbot yanıtına uygun Markdown'a çevirir.

Kullanım:
    from app.services.intelligence.intelligence_formatter import get_intelligence_context
    context = await get_intelligence_context(category="crop top")
"""
import logging
from collections import Counter
from typing import Optional, List, Dict, Any

from app.services.intelligence.intelligence_client import intelligence_client

logger = logging.getLogger(__name__)


# ─── Yapılandırılmış Rapor Şablonu ──────────────────────────────────────────

def format_structured_report(
    predictions: List[Dict],
    category: Optional[str] = None,
    params: Optional[Dict] = None,
) -> str:
    """
    Intelligence tahmin verilerini yapılandırılmış analitik rapora dönüştürür.
    GPT'ye ham ürün kartları yerine hazır istatistikler verir.

    Args:
        predictions: Intelligence /predict sonuçları
        category: Kategori adı
        params: extract_production_parameters() çıktısı
    """
    if not predictions:
        return ""

    params = params or {}
    cat_display = (category or "Genel Moda").upper()
    n = len(predictions)

    # ── 1. Trend Dağılımı ─────────────────────────────────────────────────
    labels = Counter(p.get("trend_label", "UNKNOWN") for p in predictions)
    trend_ct = labels.get("TREND", 0)
    pot_ct = labels.get("POTANSIYEL", 0)
    stab_ct = labels.get("STABIL", 0)
    fall_ct = labels.get("DUSEN", 0)

    scores = [p.get("trend_score", 0) for p in predictions]
    avg_score = sum(scores) / max(len(scores), 1)
    max_score = max(scores) if scores else 0

    # ── 2. Fiyat Analizi ──────────────────────────────────────────────────
    prices = [p.get("price") or p.get("discounted_price") or 0 for p in predictions]
    prices = [pr for pr in prices if pr > 0]
    if prices:
        min_p, max_p, avg_p = min(prices), max(prices), sum(prices) / len(prices)
        # Segment dağılımı
        low = sum(1 for p in prices if p < avg_p * 0.7)
        mid = sum(1 for p in prices if avg_p * 0.7 <= p <= avg_p * 1.3)
        high = sum(1 for p in prices if p > avg_p * 1.3)
        price_section = (
            f"| Min | Max | Ort | Uygun Fiyat | Orta | Premium |\n"
            f"|:---:|:---:|:---:|:---:|:---:|:---:|\n"
            f"| {min_p:.0f} TL | {max_p:.0f} TL | {avg_p:.0f} TL | {low} ürün | {mid} ürün | {high} ürün |"
        )
    else:
        price_section = "*Fiyat verisi bulunamadı*"

    # ── 3. Renk Analizi ───────────────────────────────────────────────────
    colors = [p.get("dominant_color") for p in predictions if p.get("dominant_color")]
    if colors:
        top_colors = Counter(colors).most_common(5)
        color_lines = " | ".join(f"**{c}** ({n})" for c, n in top_colors)
    else:
        color_lines = "*Renk verisi yok*"

    # ── 4. Kumaş/Materyal ────────────────────────────────────────────────
    fabrics = [p.get("fabric_type") for p in predictions if p.get("fabric_type")]
    if fabrics:
        top_fabrics = Counter(fabrics).most_common(4)
        fabric_lines = " | ".join(f"**{f}** ({n})" for f, n in top_fabrics)
    else:
        fabric_lines = "*Kumaş verisi yok*"

    # ── 5. Performans Liderleri ───────────────────────────────────────────
    # Trend skoru + engagement bazlı top 5
    top_products = sorted(predictions, key=lambda p: p.get("trend_score", 0), reverse=True)[:5]
    product_table = "| # | Ürün | Skor | Fav | Sepet | Fiyat |\n|:---:|------|:---:|:---:|:---:|:---:|\n"
    for i, p in enumerate(top_products, 1):
        name = (p.get("name") or f"#{p.get('product_id', '?')}")[:35]
        score = p.get("trend_score") or 0
        fav = p.get("favorite_count") or 0
        cart = p.get("cart_count") or 0
        price = p.get("price") or p.get("discounted_price") or 0
        label = p.get("trend_label", "")
        emoji = {"TREND": "🔥", "POTANSIYEL": "📈"}.get(label, "")
        product_table += f"| {i} | {emoji} {name} | {score:.0f} | {fav:,} | {cart:,} | {price:.0f} TL |\n"

    # ── 6. Engagement Metrikleri ──────────────────────────────────────────
    total_fav = sum((p.get("favorite_count") or 0) for p in predictions)
    total_cart = sum((p.get("cart_count") or 0) for p in predictions)
    total_view = sum((p.get("view_count") or 0) for p in predictions)
    avg_eng = sum((p.get("engagement_score") or 0) for p in predictions) / max(n, 1)

    # ── 7. Yeni Giriş ────────────────────────────────────────────────────
    new_entrants = [p for p in predictions if p.get("is_new_entrant")]
    new_section = ""
    if new_entrants:
        new_names = ", ".join((p.get("name") or f"#{p.get('product_id')}")[:25] for p in new_entrants[:3])
        new_section = f"\n🆕 **Yeni Girişler ({len(new_entrants)}):** {new_names}"

    # ── RAPOR BİRLEŞTİR ──────────────────────────────────────────────────
    report = f"""## 📊 {cat_display} — Veri Özeti ({n} ürün analiz edildi)

### Trend Dağılımı
🔥 **TREND:** {trend_ct} | 📈 **POTANSIYEL:** {pot_ct} | ➡️ **STABİL:** {stab_ct} | 📉 **DÜŞEN:** {fall_ct}
**Ort. Trend Skoru:** {avg_score:.1f}/100 | **Max:** {max_score:.0f}/100

### Fiyat Dağılımı
{price_section}

### Öne Çıkan Renkler
{color_lines}

### Kumaş Trendleri
{fabric_lines}

### 🏆 Top 5 Ürün
{product_table}

### Engagement Metrikleri
❤️ Toplam Favori: **{total_fav:,}** | 🛒 Toplam Sepet: **{total_cart:,}** | 👁️ Toplam Görüntülenme: **{total_view:,}**
📊 Ort. Etkileşim Skoru: **{avg_eng:.1f}**{new_section}"""

    return report


# ─── Formatlayıcılar ──────────────────────────────────────────────────────────

def format_predictions_for_chat(predictions: List[Dict], category: Optional[str] = None) -> str:
    """Intelligence predict sonuçlarını zengin ürün kartı Markdown formatına çevirir."""
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
        seller = p.get("seller") or ""
        product_code = p.get("product_code") or ""

        # ── Başlık + Ana Etiket ──
        item = f"---\n**{i}. {name}** — {emoji} {label}\n\n"
        item += f"| Skor | Güven | Talep Tahmini |\n"
        item += f"|:---:|:---:|:---:|\n"
        item += f"| **{score:.1f}**/100 | %{conf:.0f} | {p.get('ensemble_demand', 0):.1f} |\n\n"

        # ── Ürün Kimlik ──
        item += f"**Marka:** {brand}"
        if seller and seller != brand:
            item += f" | **Satıcı:** {seller}"
        if product_code:
            item += f" | **Kod:** {product_code}"
        item += "\n"

        # ── Fiyat Bilgileri ──
        price = p.get("price") or p.get("discounted_price")
        discounted = p.get("discounted_price")
        discount = p.get("discount_rate")
        if price:
            if discounted and discount and discount > 0:
                item += f"**Fiyat:** ~~{price:.0f} TL~~ → **{discounted:.0f} TL** (-%{discount:.0f})\n"
            else:
                item += f"**Fiyat:** {price:.0f} TL\n"

        # ── Görsel ──
        image_url = p.get("image_url")
        if image_url:
            item += f"\n![{name}]({image_url})\n\n"

        # ── Stil Özellikleri ──
        style_parts = []
        if p.get("dominant_color"):
            style_parts.append(f"🎨 {p['dominant_color']}")
        if p.get("fabric_type"):
            style_parts.append(f"🧵 {p['fabric_type']}")
        if p.get("fit_type"):
            style_parts.append(f"✂️ {p['fit_type']}")
        if p.get("sizes"):
            sizes = p["sizes"]
            if isinstance(sizes, list):
                style_parts.append(f"📏 {', '.join(str(s) for s in sizes[:6])}")
            elif isinstance(sizes, str):
                style_parts.append(f"📏 {sizes}")
        if style_parts:
            item += " | ".join(style_parts) + "\n"

        # ── JSONB Attributes (detaylı özellikler) ──
        attrs = p.get("attributes") or {}
        if isinstance(attrs, dict) and attrs:
            # En önemli attribute'ları göster (max 6)
            important_keys = [
                "Renk", "renk", "Color", "Kumaş Tipi", "Kumaş", "Materyal",
                "Kalıp", "Kesim", "Desen", "desen", "Pattern",
                "Yaka Tipi", "Kol Boyu", "Boy", "Mevsim", "Stil",
                "Astar", "Kapama", "Cep"
            ]
            shown = {}
            for key in important_keys:
                if key in attrs and len(shown) < 6:
                    val = attrs[key]
                    if isinstance(val, list):
                        val = ", ".join(str(v) for v in val)
                    shown[key] = str(val)
            # Diğer attribute'lar
            for k, v in attrs.items():
                if k not in shown and len(shown) < 6:
                    if isinstance(v, list):
                        v = ", ".join(str(x) for x in v)
                    shown[k] = str(v)

            if shown:
                item += "\n| Özellik | Değer |\n|---------|-------|\n"
                for k, v in shown.items():
                    item += f"| {k} | {v} |\n"
                item += "\n"

        # ── Performans Metrikleri ──
        perf_parts = []
        fav = p.get("favorite_count") or 0
        cart = p.get("cart_count") or 0
        view = p.get("view_count") or 0
        rating = p.get("avg_rating")
        rating_count = p.get("rating_count") or 0
        rank = p.get("search_rank")

        if fav:
            perf_parts.append(f"❤️ {fav:,}")
        if cart:
            perf_parts.append(f"🛒 {cart:,}")
        if view:
            perf_parts.append(f"👁️ {view:,}")
        if rating:
            perf_parts.append(f"⭐ {rating:.1f} ({rating_count:,})")
        if rank:
            perf_parts.append(f"📍 #{rank}")
        if perf_parts:
            item += " | ".join(perf_parts) + "\n"

        # ── Rank Momentum ──
        rank_1d = p.get("rank_change_1d")
        rank_3d = p.get("rank_change_3d")
        momentum = p.get("momentum_score")
        if rank_1d is not None or rank_3d is not None or momentum is not None:
            momentum_parts = []
            if rank_1d is not None:
                arrow = "⬆️" if rank_1d < 0 else ("⬇️" if rank_1d > 0 else "➡️")
                momentum_parts.append(f"1G: {arrow}{abs(rank_1d)}")
            if rank_3d is not None:
                arrow = "⬆️" if rank_3d < 0 else ("⬇️" if rank_3d > 0 else "➡️")
                momentum_parts.append(f"3G: {arrow}{abs(rank_3d)}")
            if momentum is not None:
                m_emoji = "🟢" if momentum > 0.3 else ("🔴" if momentum < -0.3 else "🟡")
                momentum_parts.append(f"{m_emoji} momentum={momentum:.2f}")
            item += f"**Sıralama Hareketi:** {' | '.join(momentum_parts)}\n"

        # ── Satış/Engagement Metrikleri ──
        eng = p.get("engagement_score")
        pop = p.get("popularity_score")
        vel = p.get("sales_velocity")
        if eng or pop or vel:
            business_parts = []
            if eng:
                business_parts.append(f"Etkileşim: {eng:.1f}")
            if pop:
                business_parts.append(f"Popülerlik: {pop:.1f}")
            if vel:
                business_parts.append(f"Satış Hızı: {vel:.1f}")
            item += f"**📊 {' | '.join(business_parts)}**\n"

        # ── Yorum Özeti ──
        review = p.get("review_summary")
        if review and review.strip():
            item += f"**💬 Yorum Özeti:** {review[:200]}\n"

        # ── Yeni Giriş Rozeti ──
        if p.get("is_new_entrant"):
            item += "**🆕 YENİ GİRİŞ** — İlk kez Top100'de!\n"

        # ── Ürün Linki ──
        url = p.get("url")
        if url:
            item += f"🔗 [Ürünü İncele]({url})\n"

        items.append(item)

    # Özet istatistikler
    trend_count = sum(1 for p in predictions if p.get("trend_label") == "TREND")
    pot_count = sum(1 for p in predictions if p.get("trend_label") == "POTANSIYEL")
    falling_count = sum(1 for p in predictions if p.get("trend_label") == "DUSEN")
    new_count = sum(1 for p in predictions if p.get("is_new_entrant"))
    avg_score = sum(p.get("trend_score", 0) for p in predictions) / max(len(predictions), 1)

    # Fiyat aralığı
    prices = [p.get("price") or p.get("discounted_price") for p in predictions if p.get("price") or p.get("discounted_price")]
    price_range = f" | 💰 {min(prices):.0f}–{max(prices):.0f} TL" if prices else ""

    # Popüler renkler
    colors = [p.get("dominant_color") for p in predictions if p.get("dominant_color")]
    color_summary = ""
    if colors:
        from collections import Counter
        top_colors = Counter(colors).most_common(3)
        color_summary = f" | 🎨 {', '.join(c[0] for c in top_colors)}"

    summary = f"\n---\n### 📊 Özet\n"
    summary += f"🔥 **{trend_count}** trend | 📈 **{pot_count}** potansiyel | 📉 **{falling_count}** düşen"
    if new_count:
        summary += f" | 🆕 **{new_count}** yeni giriş"
    summary += f"\n**Ort. skor:** {avg_score:.1f}{price_range}{color_summary}\n"

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


async def get_structured_intelligence_context(
    category: Optional[str] = None,
    top_n: int = 20,
    params: Optional[Dict] = None,
) -> str:
    """
    Intelligence servisinden veri çekip yapılandırılmış analitik rapor üretir.
    TREND_ANALYSIS intent'i için kullanılır (GPT'ye özet istatistikler verir).
    """
    try:
        predictions = await intelligence_client.predict(category=category, top_n=top_n)
        if not predictions:
            return ""
        logger.info(f"📊 Structured context: {len(predictions)} tahmin (category={category})")
        return format_structured_report(predictions, category=category, params=params)
    except Exception as e:
        logger.warning(f"Intelligence structured context alınamadı: {e}")
        return ""


async def get_intelligence_product_context(product_id: int) -> str:
    """Tekil ürün analizi için Intelligence context üretir."""
    try:
        analysis = await intelligence_client.analyze(product_id)
        if analysis and not analysis.get("error"):
            return format_analysis_for_chat(analysis)
    except Exception as e:
        logger.warning(f"Intelligence ürün analizi alınamadı: {e}")
    return ""
