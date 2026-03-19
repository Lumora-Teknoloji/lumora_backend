import logging
from typing import List, Dict, Any, Tuple
import re

logger = logging.getLogger(__name__)

def _normalize_string(s: str) -> str:
    if not s:
        return ""
    # Basit bir normalize işlemi (küçük harf, türkçe karakter vb. handle edilebilir)
    return s.lower().strip()

def _calculate_color_match(pred_color: str, user_color: str) -> float:
    if not user_color or not pred_color:
        return 0.0
        
    u_c = _normalize_string(user_color)
    p_c = _normalize_string(pred_color)
    
    if u_c in p_c or p_c in u_c:
        return 1.0
    return 0.0

def _calculate_material_match(pred_material: str, user_material: str) -> float:
    if not user_material or not pred_material:
        return 0.0
        
    u_m = _normalize_string(user_material)
    p_m = _normalize_string(pred_material)
    
    if u_m in p_m or p_m in u_m:
        return 1.0
    return 0.0

def _calculate_season_match(pred_season: str, user_season: str) -> float:
    if not user_season or user_season == "Genel" or not pred_season:
        return 0.0
        
    u_s = _normalize_string(user_season)
    p_s = _normalize_string(pred_season)
    
    # Basit exact match (yaz, kış vs.)
    if u_s in p_s or p_s in u_s:
        return 1.0
    return 0.0

def semantic_match_and_rank(predictions: List[Dict[str, Any]], params: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], float]:
    """
    Intelligence servisinden gelen tahminleri (CatBoost sonuçları), kullanıcının 
    aradığı spesifik parametrelere (renk, kumaş, sezon vb.) göre eşleştirir, puanlar
    ve sıralar. Son olarak genel bir "Güven Skoru" (Confidence) döndürür.
    
    Args:
        predictions: CatBoost model sonuçları listesi
        params: extract_production_parameters çıktısı
        
    Returns:
        (Sıralanmış sonuçlar listesi, Güven Skoru 0-100)
    """
    if not predictions:
        return [], 0.0
        
    user_color = params.get("dominant_color")
    user_material = params.get("material")
    user_season = params.get("seasonality")
    
    # Parametre ağırlıkları 
    # (Örnek: Renk belirtilmişse ve uyuyorsa %25 katkı, Kumaş %15 vb.)
    WEIGHTS = {
        "color": 0.40,
        "material": 0.30,
        "season": 0.30
    }
    
    # Kullanıcının kaç spesifik parametre aradığına bakalım (Genel/None olmayanlar)
    active_params = 0
    if user_color: active_params += 1
    if user_material: active_params += 1
    if user_season and user_season.lower() != "genel": active_params += 1
    
    ranked_results = []
    total_match_score = 0.0
    matched_product_count = 0
    
    for pred in predictions:
        score = 0.0
        details = pred.get("product_details", {})
        if not details:
            details = {} # fallback in case product details is a string or empty
            
        if isinstance(details, str):
            # Nadir durum: details string gelmişse JSON parse girmemek için basite indirge
            details_str = details.lower()
            pred_color = details_str
            pred_material = details_str
            pred_season = details_str
        else:
            pred_color = details.get("color") or details.get("dominant_color", "")
            pred_material = details.get("fabric") or details.get("material", "")
            pred_season = details.get("season", "") 
            
            # Ürün özelliklerinde de arayalım (attributes)
            if not pred_color or not pred_material:
                attrs = details.get("attributes", {})
                if isinstance(attrs, dict):
                    if not pred_color: pred_color = attrs.get("Renk", "")
                    if not pred_material: pred_material = attrs.get("Materyal", "") or attrs.get("Kumaş Tipi", "")
        
        # 1. Renk Uyumu
        if user_color:
            color_match = _calculate_color_match(str(pred_color), user_color)
            score += color_match * WEIGHTS["color"]
            
        # 2. Kumaş/Materyal Uyumu
        if user_material:
            material_match = _calculate_material_match(str(pred_material), user_material)
            score += material_match * WEIGHTS["material"]
            
        # 3. Sezon Uyumu
        if user_season and user_season.lower() != "genel":
            season_match = _calculate_season_match(str(pred_season), user_season)
            score += season_match * WEIGHTS["season"]
            
        # Toplam skoru hesapla (aktif parametrelere oranla 0-1 arası)
        normalized_score = score / sum(WEIGHTS.values()) if active_params > 0 else 0.5 # Parametre aranmıyorsa hepsine eşit davran
        
        # Eğer aktif parametreler varsa ve en az biraz (ör %20) eşleştiyse, eşleşmiş say
        if active_params == 0 or normalized_score >= 0.2:
            matched_product_count += 1
            total_match_score += normalized_score
            
        # Yeni sıralama için pred dict'ini genişlet (mutasyona uğratmaktan çekinmiyoruz çünki local copy)
        pred_copy = pred.copy()
        pred_copy["semantic_match_score"] = normalized_score
        ranked_results.append(pred_copy)
        
    # Sırala (Önce semantic match score, sonra original ensemble_demand/trend_score)
    ranked_results.sort(key=lambda x: (x.get("semantic_match_score", 0), x.get("ensemble_demand", 0)), reverse=True)
    
    # GÜVEN SKORU (CONFIDENCE ROUTER) HESAPLAMA
    
    coverage_score = 1.0  
    if active_params > 0 and matched_product_count > 0:
        avg_match_quality = total_match_score / matched_product_count
        coverage_score = avg_match_quality
    elif active_params > 0 and matched_product_count == 0:
        coverage_score = 0.0
        
    # Eğer parametre aranıyor ama HİÇ bulunamıyorsa, güven 0 yerine base bir güven verelim (eğer ürün var ise)
    if active_params > 0 and matched_product_count == 0:
        # Ürünler kategori bazında CatBoost'tan başarıyla gelmiş. 
        # Sadece rank edilemedi (DB'de sezon/renk eksikliği vb.)
        if len(predictions) > 0:
            confidence = 30.0  # Fallback'e gitmemesi için 20'nin üstünde base score
        else:
            confidence = 0.0
    else:
        confidence = (min(matched_product_count, 5) / 5) * 50.0 + (coverage_score * 50.0)
        
    if active_params == 0 and len(predictions) > 0:
        confidence = 100.0
        
    logger.info(f"🧩 Semantic Match: active_params={active_params}, matched={matched_product_count}/{len(predictions)}, confidence={confidence:.1f}")
    
    return ranked_results, confidence
