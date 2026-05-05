"""
Title Generator Unit Tests
"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_title_generator_success():
    """AI başarıyla kısa başlık üretmeli"""
    with patch("app.services.ai.title_generator.openai_client") as mock_openai:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Crop Top Trendleri"
        mock_openai.chat.completions.create.return_value = mock_response
        
        from app.services.ai.title_generator import generate_conversation_title
        result = await generate_conversation_title("crop top trendleri neler?")
        assert result == "Crop Top Trendleri"


@pytest.mark.asyncio
async def test_title_generator_long_title_truncation():
    """50 karakterden uzun başlıklar kısaltılmalı"""
    with patch("app.services.ai.title_generator.openai_client") as mock_openai:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "A" * 60  # 60 karakter
        mock_openai.chat.completions.create.return_value = mock_response
        
        from app.services.ai.title_generator import generate_conversation_title
        result = await generate_conversation_title("test")
        assert len(result) <= 53  # 50 + "..."


@pytest.mark.asyncio
async def test_title_generator_empty_response_fallback():
    """Boş yanıt gelirse 'Yeni Konuşma' dönmeli"""
    with patch("app.services.ai.title_generator.openai_client") as mock_openai:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = ""
        mock_openai.chat.completions.create.return_value = mock_response
        
        from app.services.ai.title_generator import generate_conversation_title
        result = await generate_conversation_title("test")
        assert result == "Yeni Konuşma"


@pytest.mark.asyncio
async def test_title_generator_api_error_fallback():
    """API hatası olursa ilk 40 karakter fallback kullanılmalı"""
    with patch("app.services.ai.title_generator.openai_client") as mock_openai:
        mock_openai.chat.completions.create.side_effect = Exception("API Error")
        
        from app.services.ai.title_generator import generate_conversation_title
        result = await generate_conversation_title("Bu bir uzun mesaj denemesidir merhaba nasılsınız bugün hava çok güzel")
        assert len(result) <= 43  # 40 + "..."
        assert result.endswith("...")


@pytest.mark.asyncio
async def test_title_generator_no_client_fallback():
    """openai_client None ise fallback kullanılmalı"""
    with patch("app.services.ai.title_generator.openai_client", None):
        from app.services.ai.title_generator import generate_conversation_title
        result = await generate_conversation_title("merhaba")
        assert result == "merhaba"  # 40 karakter altı → direkt dön


@pytest.mark.asyncio
async def test_title_generator_no_client_empty_message():
    """openai_client None ve mesaj boş ise 'Yeni Konuşma' dönmeli"""
    with patch("app.services.ai.title_generator.openai_client", None):
        from app.services.ai.title_generator import generate_conversation_title
        result = await generate_conversation_title("")
        assert result == "Yeni Konuşma"
