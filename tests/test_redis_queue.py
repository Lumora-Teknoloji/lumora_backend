import pytest
from unittest.mock import patch, AsyncMock
from app.core.config import settings

def test_redis_pop_unauthorized(client):
    response = client.post(
        "/api/redis/queue/pop",
        headers={"X-Agent-Secret": "WRONG_SECRET", "X-Bot-Id": "123"},
        json={"timeout": 1}
    )
    assert response.status_code == 401
    assert "Geçersiz agent anahtarı" in response.json()["detail"]

def test_redis_pop_missing_auth(client):
    response = client.post("/api/redis/queue/pop", headers={"X-Bot-Id": "123"}, json={"timeout": 1})
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_redis_pop_authorized_empty(client):
    # Test valid auth, but mock the redis pool to return None (empty queue)
    with patch("app.routers.redis_queue.get_redis") as mock_get_redis:
        mock_conn = AsyncMock()
        mock_conn.rpoplpush.return_value = None
        mock_get_redis.return_value = mock_conn
        
        response = client.post(
            "/api/redis/queue/pop",
            headers={"X-Agent-Secret": settings.agent_secret, "X-Bot-Id": "123"},
            json={"timeout": 1}
        )
        # We expect a 204 No Content when queue is empty, to prevent blocking
        assert response.status_code == 204

@pytest.mark.asyncio
async def test_redis_push_result_unauthorized(client):
    response = client.post(
        "/api/redis/queue/push_result",
        headers={"X-Agent-Secret": "WRONG_SECRET"},
        json={"url": "http://test.com", "data": {"name": "test"}}
    )
    assert response.status_code == 401
