from fastapi import status

from fastapi import status
from sqlalchemy import text

# --- Database Connection Test ---
def test_database_connection(db_session):
    """Veritabanı bağlantısını test et (SELECT 1)"""
    try:
        result = db_session.execute(text("SELECT 1"))
        assert result.scalar() == 1
    except Exception as e:
        pytest.fail(f"Database connection failed: {e}")

# --- Auth Tests ---
def test_register_user(client, db_session):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "email": "new@example.com",
            "full_name": "New User",
            "password": "password123"
        }
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"
    # DB kontrolü
    from app.models import User
    user = db_session.query(User).filter(User.username == "newuser").first()
    assert user is not None

def test_login_user(client, db_session):
    # Register first (using API or fixture, here simplified manual insert is tricky due to hashing)
    # Let's use the API to register so password hash is correct
    client.post(
        "/api/auth/register",
        json={
            "username": "loginuser",
            "email": "login@example.com",
            "full_name": "Login User",
            "password": "password123"
        }
    )
    
    response = client.post(
        "/api/auth/login",
        json={"username": "loginuser", "password": "password123"}
    )
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.cookies  # Token cookie'de olmalı

# --- Conversation Tests ---
def test_create_conversation(client, auth_headers):
    response = client.post(
        "/api/conversations/",
        json={"title": "My Test Chat"},
        cookies=auth_headers
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["title"] == "My Test Chat"
    assert "id" in data

def test_list_conversations(client, auth_headers):
    # Önce bir tane oluştur
    client.post("/api/conversations/", json={"title": "Chat 1"}, cookies=auth_headers)
    client.post("/api/conversations/", json={"title": "Chat 2"}, cookies=auth_headers)

    response = client.get("/api/conversations/", cookies=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) >= 2

def test_delete_conversation(client, auth_headers):
    # Oluştur
    create_res = client.post("/api/conversations/", json={"title": "Delete Me"}, cookies=auth_headers)
    convo_id = create_res.json()["id"]

    # Sil
    del_res = client.delete(f"/api/conversations/{convo_id}", cookies=auth_headers)
    assert del_res.status_code == status.HTTP_200_OK

    # Tekrar silmeye çalış (404 dönmeli)
    del_res_2 = client.delete(f"/api/conversations/{convo_id}", cookies=auth_headers)
    assert del_res_2.status_code == status.HTTP_404_NOT_FOUND

def test_update_conversation(client, auth_headers):
    create_res = client.post("/api/conversations/", json={"title": "Old Title"}, cookies=auth_headers)
    convo_id = create_res.json()["id"]

    update_res = client.put(
        f"/api/conversations/{convo_id}",
        json={"title": "New Title", "alias": "New Alias"},
        cookies=auth_headers
    )
    assert update_res.status_code == status.HTTP_200_OK
    assert update_res.json()["title"] == "New Title"

# --- Message Tests ---
def test_create_message(client, auth_headers):
    # Konuşma oluştur
    convo_res = client.post("/api/conversations/", json={"title": "Msg Chat"}, cookies=auth_headers)
    convo_id = convo_res.json()["id"]

    # Mesaj at
    msg_res = client.post(
        "/api/messages/",
        json={
            "conversation_id": convo_id,
            "sender": "user",
            "content": "Hello AI"
        },
        cookies=auth_headers
    )
    assert msg_res.status_code == status.HTTP_201_CREATED
    data = msg_res.json()
    assert data["content"] == "Hello AI"
    
    # Conversatin history güncellendi mi?
    from app.models import Conversation
    # Not: Fixture db_session ayrı, burada API üzerinden kontrol edebiliriz ya da tekrar fetch
    # API üzerinden mesajları çekelim
    list_res = client.get(f"/api/conversations/{convo_id}/messages", cookies=auth_headers)
    assert list_res.status_code == status.HTTP_200_OK
    messages = list_res.json()
    assert len(messages) == 1
    assert messages[0]["content"] == "Hello AI"

# --- User Tests ---
def test_change_password(client, db_session):
    # Manuel user oluştur çünkü şifresini biliyoruz
    from app.core.security import hash_password, create_access_token
    from app.models import User
    
    user = User(
        username="pwuser",
        email="pw@test.com",
        full_name="Pw User",
        hashed_password=hash_password("oldpass")
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    token = create_access_token({"sub": str(user.id)})
    cookies = {"access_token": token}

    res = client.post(
        "/api/users/change-password",
        json={"current_password": "oldpass", "new_password": "newpass"},
        cookies=cookies
    )
    assert res.status_code == status.HTTP_200_OK

    # Eski şifreyle login dene (fail olmalı)
    login_fail = client.post(
        "/api/auth/login",
        json={"username": "pwuser", "password": "oldpass"}
    )
    assert login_fail.status_code == status.HTTP_401_UNAUTHORIZED

    # Yeni şifreyle login dene
    login_ok = client.post(
        "/api/auth/login",
        json={"username": "pwuser", "password": "newpass"}
    )
    assert login_ok.status_code == status.HTTP_200_OK
