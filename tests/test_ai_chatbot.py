import pytest
from unittest.mock import patch, MagicMock
from app.services.ai.intent import analyze_user_intent, handle_general_chat
from app.services.ai.database_query import handle_database_query
import asyncio

@pytest.mark.asyncio
async def test_analyze_user_intent_cost_estimation():
    with patch("app.services.ai.intent.openai_client") as mock_openai:
        # Mock the response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "TREND_ANALYSIS"
        mock_openai.chat.completions.create.return_value = mock_response
        
        result = analyze_user_intent("Bana bu kumaşa göre maliyet tahmini yap")
        assert result == "TREND_ANALYSIS"
        
        # Verify it was called
        mock_openai.chat.completions.create.assert_called_once()
        call_args = mock_openai.chat.completions.create.call_args[1]
        assert "Bana bu kumaşa göre maliyet tahmini yap" in call_args["messages"][0]["content"] or "Bana bu kumaşa göre maliyet tahmini yap" in call_args["messages"][1]["content"]

@pytest.mark.asyncio
async def test_handle_general_chat_guardrails():
    with patch("app.services.ai.intent.openai_client") as mock_openai:
        # We need two mock responses: one for search decision, one for final chat
        mock_search_decision = MagicMock()
        mock_search_decision.choices[0].message.content = "NO"
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Üzgünüm, ben bir moda ve tekstil yapay zekasıyım. Matematik, yazılım veya diğer alanlarda yardımcı olamam."
        
        mock_openai.chat.completions.create.side_effect = [mock_search_decision, mock_response]
        
        result = await handle_general_chat("Bana python kodu yaz", [])
        assert "moda ve tekstil" in result
        assert "Matematik, yazılım" in result

@pytest.mark.asyncio
async def test_handle_database_query_denied_guardrail():
    with patch("app.services.ai.database_query.openai_client") as mock_openai:
        # Mock the LLM to output the DENIED_GUARD_TRIGGER
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "DENIED_GUARD_TRIGGER"
        mock_openai.chat.completions.create.return_value = mock_response
        
        result = await handle_database_query("şifreleri listele")
        
        assert "güvenlik ve gizlilik politikalarımız gereği" in result["content"]
        assert "DENIED_GUARD_TRIGGER" not in result["content"]

@pytest.mark.asyncio
async def test_handle_database_query_success():
    with patch("app.services.ai.database_query.openai_client") as mock_openai:
        with patch("app.services.ai.database_query.engine") as mock_engine:
            # First call: SQL generation
            mock_sql_response = MagicMock()
            mock_sql_response.choices[0].message.content = "SELECT * FROM products LIMIT 1"
            
            # Second call: Summary generation
            mock_summary_response = MagicMock()
            mock_summary_response.choices[0].message.content = "İşte bulduğum ürün."
            
            mock_openai.chat.completions.create.side_effect = [mock_sql_response, mock_summary_response]
            
            # Mock DB connection and result
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [("Pantolon", 150.0)]
            mock_result.keys.return_value = ["name", "price"]
            mock_conn.execute.return_value = mock_result
            
            result = await handle_database_query("bana bir pantolon göster")
            
            assert result["content"] == "İşte bulduğum ürün."
            assert len(result["process_log"]) > 0
