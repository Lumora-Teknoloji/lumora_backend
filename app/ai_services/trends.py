"""
Google Trends Service - SerpApi ile trend analizi
"""
import logging
from typing import Dict, Any, List, Optional
from ..config import settings

logger = logging.getLogger(__name__)


def get_google_trends(keyword: str, timeframe: str = "today 3-m", geo: str = "TR") -> Dict[str, Any]:
    """
    Google Trends verisi çeker.
    
    Args:
        keyword: Aranacak kelime (örn: "abiye elbise")
        timeframe: Zaman aralığı ("today 3-m", "today 12-m", "today 5-y")
        geo: Ülke kodu ("TR", "US", vb.)
    
    Returns:
        {
            "interest_over_time": [...],  # Zaman serisi
            "rising_queries": [...],       # Yükselen aramalar
            "top_queries": [...],          # En popüler aramalar
            "interest_by_region": [...]    # Bölgesel ilgi
        }
    """
    if not settings.serpapi_api_key:
        logger.warning("⚠️ SERPAPI_API_KEY bulunamadı")
        return {"error": "SerpApi API key not configured"}
    
    try:
        from serpapi import GoogleSearch
    except ImportError:
        logger.error("❌ serpapi paketi yüklü değil. 'pip install google-search-results' çalıştırın.")
        return {"error": "serpapi package not installed"}
    
    result = {
        "keyword": keyword,
        "interest_over_time": [],
        "rising_queries": [],
        "top_queries": [],
        "interest_by_region": [],
        "summary": ""
    }
    
    try:
        # 1. Interest Over Time (Zaman Serisi)
        params = {
            "engine": "google_trends",
            "q": keyword,
            "data_type": "TIMESERIES",
            "date": timeframe,
            "geo": geo,
            "api_key": settings.serpapi_api_key
        }
        
        search = GoogleSearch(params)
        data = search.get_dict()
        
        if "interest_over_time" in data:
            timeline = data["interest_over_time"].get("timeline_data", [])
            for point in timeline:
                raw_value = point.get("values", [{}])[0].get("value", 0) if point.get("values") else 0
                result["interest_over_time"].append({
                    "date": point.get("date", ""),
                    "value": int(raw_value) if str(raw_value).isdigit() else 0
                })
        
        # 2. Related Queries (İlgili Aramalar)
        params["data_type"] = "RELATED_QUERIES"
        search = GoogleSearch(params)
        data = search.get_dict()
        
        if "related_queries" in data:
            queries = data["related_queries"]
            if queries.get("rising"):
                result["rising_queries"] = [
                    {"query": q.get("query", ""), "value": str(q.get("value", ""))} 
                    for q in queries["rising"][:10]
                ]
            if queries.get("top"):
                result["top_queries"] = [
                    {"query": q.get("query", ""), "value": int(q.get("value", 0)) if str(q.get("value", 0)).isdigit() else 0} 
                    for q in queries["top"][:10]
                ]
        
        # 3. Interest by Region (Bölgesel İlgi)
        params["data_type"] = "GEO_MAP"
        search = GoogleSearch(params)
        data = search.get_dict()
        
        if "interest_by_region" in data:
            regions = data["interest_by_region"]
            result["interest_by_region"] = [
                {"location": r.get("location", ""), "value": r.get("value", 0)}
                for r in regions[:10]
            ]
        
        # Özet oluştur
        if result["interest_over_time"]:
            values = [p["value"] for p in result["interest_over_time"] if p["value"]]
            if len(values) >= 2:
                first_half = sum(values[:len(values)//2]) / max(len(values)//2, 1)
                second_half = sum(values[len(values)//2:]) / max(len(values)//2, 1)
                if second_half > first_half:
                    change = ((second_half - first_half) / max(first_half, 1)) * 100
                    result["summary"] = f"📈 '{keyword}' aramaları son dönemde %{change:.0f} arttı."
                else:
                    change = ((first_half - second_half) / max(first_half, 1)) * 100
                    result["summary"] = f"📉 '{keyword}' aramaları son dönemde %{change:.0f} azaldı."
        
        logger.info(f"✅ Google Trends verisi alındı: {keyword}")
        return result
        
    except Exception as e:
        logger.error(f"❌ Google Trends hatası: {e}")
        return {"error": str(e)}


def format_trends_for_report(trends_data: Dict[str, Any]) -> str:
    """
    Trend verisini rapor formatına çevirir.
    """
    if "error" in trends_data:
        return ""
    
    output = []
    
    # Özet
    if trends_data.get("summary"):
        output.append(trends_data["summary"])
    
    # Yükselen aramalar
    if trends_data.get("rising_queries"):
        output.append("\n**🚀 Yükselen Aramalar:**")
        for q in trends_data["rising_queries"][:5]:
            output.append(f"- {q['query']} ({q['value']})")
    
    # Bölgesel ilgi
    if trends_data.get("interest_by_region"):
        output.append("\n**📍 Bölgesel İlgi:**")
        for r in trends_data["interest_by_region"][:5]:
            output.append(f"- {r['location']}: {r['value']}%")
    
    return "\n".join(output)
