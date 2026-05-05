"""
Semantic Matcher Unit Tests — Ağırlık hesaplaması, normalizasyon ve edge case'ler
"""
import pytest
from app.services.ai.semantic_matcher import (
    semantic_match_and_rank,
    _normalize_string,
    _calculate_color_match,
    _calculate_material_match,
    _calculate_season_match,
)


# ─── Yardımcı fonksiyon testleri ──────────────────────────────────────────

class TestNormalizeString:
    def test_normal(self):
        assert _normalize_string("  Kırmızı  ") == "kırmızı"

    def test_empty(self):
        assert _normalize_string("") == ""

    def test_none(self):
        assert _normalize_string(None) == ""


class TestColorMatch:
    def test_exact_match(self):
        assert _calculate_color_match("kırmızı", "kırmızı") == 1.0

    def test_substring_match(self):
        assert _calculate_color_match("açık kırmızı", "kırmızı") == 1.0

    def test_no_match(self):
        assert _calculate_color_match("mavi", "kırmızı") == 0.0

    def test_empty_user(self):
        assert _calculate_color_match("kırmızı", "") == 0.0

    def test_empty_pred(self):
        assert _calculate_color_match("", "kırmızı") == 0.0

    def test_both_none(self):
        assert _calculate_color_match(None, None) == 0.0


class TestMaterialMatch:
    def test_exact_match(self):
        assert _calculate_material_match("pamuk", "pamuk") == 1.0

    def test_substring_match(self):
        assert _calculate_material_match("organik pamuk", "pamuk") == 1.0

    def test_no_match(self):
        assert _calculate_material_match("deri", "pamuk") == 0.0


class TestSeasonMatch:
    def test_exact_match(self):
        assert _calculate_season_match("yaz", "yaz") == 1.0

    def test_no_match(self):
        assert _calculate_season_match("kış", "yaz") == 0.0

    def test_genel_user_season(self):
        """Genel sezon seçilmişse eşleşme yapılmamalı"""
        assert _calculate_season_match("yaz", "Genel") == 0.0

    def test_empty_pred(self):
        assert _calculate_season_match("", "yaz") == 0.0


# ─── Ana fonksiyon testleri ───────────────────────────────────────────────

class TestSemanticMatchAndRank:
    def _make_prediction(self, color="", material="", season="", score=50.0):
        return {
            "product_id": 1,
            "name": "Test Ürün",
            "ensemble_demand": score,
            "product_details": {
                "color": color,
                "fabric": material,
                "season": season
            }
        }

    def test_empty_predictions(self):
        results, confidence = semantic_match_and_rank([], {"dominant_color": "kırmızı"})
        assert results == []
        assert confidence == 0.0

    def test_no_params_full_confidence(self):
        """Parametre aranmıyorsa ve tahmin varsa, confidence %100 olmalı"""
        preds = [self._make_prediction()]
        results, confidence = semantic_match_and_rank(preds, {})
        assert confidence == 100.0
        assert len(results) == 1

    def test_single_color_param_full_match(self):
        """Sadece renk arıyorsa ve tam eşleşme varsa, normalized_score 1.0 olmalı"""
        preds = [self._make_prediction(color="kırmızı")]
        params = {"dominant_color": "kırmızı"}
        results, confidence = semantic_match_and_rank(preds, params)
        assert results[0]["semantic_match_score"] == 1.0

    def test_single_color_param_no_match(self):
        """Sadece renk arıyorsa ve eşleşme yoksa, normalized_score 0.0 olmalı"""
        preds = [self._make_prediction(color="mavi")]
        params = {"dominant_color": "kırmızı"}
        results, confidence = semantic_match_and_rank(preds, params)
        assert results[0]["semantic_match_score"] == 0.0

    def test_multiple_params_partial_match(self):
        """İki parametre arıyorsa, sadece birisi eşleşiyorsa kısmi skor"""
        preds = [self._make_prediction(color="kırmızı", material="deri")]
        params = {"dominant_color": "kırmızı", "material": "pamuk"}
        results, confidence = semantic_match_and_rank(preds, params)
        score = results[0]["semantic_match_score"]
        assert 0.0 < score < 1.0  # Kısmi eşleşme

    def test_ranking_order(self):
        """Daha yüksek eşleşme skoru olan ürün üstte olmalı"""
        preds = [
            self._make_prediction(color="mavi", score=90.0),
            self._make_prediction(color="kırmızı", score=50.0),
        ]
        params = {"dominant_color": "kırmızı"}
        results, _ = semantic_match_and_rank(preds, params)
        # kırmızı eşleşen ürün üstte olmalı
        assert results[0]["semantic_match_score"] > results[1]["semantic_match_score"]

    def test_fallback_confidence_when_no_detail_match(self):
        """Tahminler var ama hiçbiri spesifik parametreye uymuyorsa, 
        confidence 30 (fallback) olmalı, 0 değil"""
        preds = [self._make_prediction()]  # Boş renk/kumaş
        params = {"dominant_color": "kırmızı"}
        _, confidence = semantic_match_and_rank(preds, params)
        assert confidence >= 30.0  # Fallback score, Intelligence verisini hala döndürür

    def test_string_product_details_handling(self):
        """product_details string gelirse crash olmamalı"""
        pred = {
            "product_id": 1,
            "name": "Test",
            "ensemble_demand": 50.0,
            "product_details": "kırmızı pamuklu ürün"
        }
        params = {"dominant_color": "kırmızı"}
        results, _ = semantic_match_and_rank([pred], params)
        assert len(results) == 1
        assert results[0]["semantic_match_score"] == 1.0
