import pytest
from app.main import fastapi_app as app
from app.api.deps import get_current_user
from app.models.user import User
from app.models.conversation import Conversation
from datetime import datetime, timezone

# Dummy user for auth override
dummy_user = User(id=1, username="testuser", email="test@test.com")

def override_get_current_user():
    return dummy_user



def test_create_message_conversation_not_found(client, db_session):
    app.dependency_overrides[get_current_user] = override_get_current_user
    db_session.query.return_value.filter.return_value.first.return_value = None
    response = client.post(
        "/api/messages",
        json={"conversation_id": 999, "sender": "user", "content": "Hello"}
    )
    assert response.status_code == 404

def test_create_message_success(client, db_session):
    app.dependency_overrides[get_current_user] = override_get_current_user
    conv = Conversation(id=1, user_id=1, title="Test", created_at=datetime.now(timezone.utc), history_json=[])
    db_session.query.return_value.filter.return_value.first.return_value = conv
    
    def mock_add(obj):
        if hasattr(obj, 'id') and getattr(obj, 'id', None) is None:
            obj.id = 1
        if hasattr(obj, 'created_at') and getattr(obj, 'created_at', None) is None:
            obj.created_at = datetime.now(timezone.utc)
            
    db_session.add.side_effect = mock_add
    
    response = client.post(
        "/api/messages",
        json={"conversation_id": 1, "sender": "user", "content": "Hello AI"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["content"] == "Hello AI"
    assert data["sender"] == "user"
    assert data["conversation_id"] == 1
    
    # Check if history update was committed
    db_session.commit.assert_called()
    
def test_create_message_auto_alias(client, db_session):
    app.dependency_overrides[get_current_user] = override_get_current_user
    conv = Conversation(id=2, user_id=1, title="Test 2", created_at=datetime.now(timezone.utc), history_json=[])
    db_session.query.return_value.filter.return_value.first.return_value = conv
    
    def mock_add(obj):
        if hasattr(obj, 'id') and getattr(obj, 'id', None) is None:
            obj.id = 2
        if hasattr(obj, 'created_at') and getattr(obj, 'created_at', None) is None:
            obj.created_at = datetime.now(timezone.utc)
            
    db_session.add.side_effect = mock_add
    
    client.post(
        "/api/messages",
        json={"conversation_id": 2, "sender": "user", "content": "A very long message that should be truncated to become a suitable alias for the conversation"}
    )
    
    db_session.commit.assert_called()
    # The endpoint updates the conv object in memory before commit
    assert conv.alias is not None
    assert conv.alias.startswith("A very long message")
    assert len(conv.alias) <= 43 # 40 + "..."
