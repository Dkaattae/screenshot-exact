from datetime import UTC, datetime, timedelta

import jwt

from tests.conftest import register


def test_register_returns_token_and_user(client):
    response = client.post(
        "/auth/register", json={"email": "New@Example.com", "password": "long-enough"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "new@example.com"
    assert "password" not in str(body["user"])


def test_register_rejects_duplicate_email_case_insensitively(client):
    register(client, "dup@example.com")
    response = client.post(
        "/auth/register", json={"email": "DUP@example.com", "password": "long-enough"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONFLICT"


def test_register_rejects_short_password(client):
    response = client.post("/auth/register", json={"email": "a@example.com", "password": "short"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_register_rejects_invalid_email(client):
    response = client.post("/auth/register", json={"email": "not-an-email", "password": "x" * 10})
    assert response.status_code == 400


def test_login_with_correct_password(client):
    register(client, "login@example.com")
    response = client.post(
        "/auth/login", json={"email": "login@example.com", "password": "correct-horse"}
    )
    assert response.status_code == 200
    me = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"}
    )
    assert me.json()["email"] == "login@example.com"


def test_login_with_wrong_password_or_unknown_email_gives_same_error(client):
    register(client, "login@example.com")
    wrong = client.post("/auth/login", json={"email": "login@example.com", "password": "nope-nope"})
    unknown = client.post("/auth/login", json={"email": "who@example.com", "password": "nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_user_endpoints_require_a_token(client):
    response = client.get("/users/me/items")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.headers["www-authenticate"] == "Bearer"


def test_garbage_token_is_rejected(client):
    response = client.get("/users/me/items", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_expired_token_is_rejected(client, settings):
    headers = register(client)
    user_id = client.get("/auth/me", headers=headers).json()["id"]
    past = datetime.now(UTC) - timedelta(hours=1)
    token = jwt.encode({"sub": user_id, "exp": past}, settings.secret_key, algorithm="HS256")
    response = client.get("/users/me/items", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "expired" in response.json()["error"]["message"]


def test_token_signed_with_another_key_is_rejected(client):
    headers = register(client)
    user_id = client.get("/auth/me", headers=headers).json()["id"]
    other_key = "another-secret-that-is-also-32-bytes-long"
    token = jwt.encode({"sub": user_id}, other_key, algorithm="HS256")
    response = client.get("/users/me/items", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_own_user_id_works_like_me(client, auth):
    user_id = client.get("/auth/me", headers=auth).json()["id"]
    assert client.get(f"/users/{user_id}/items", headers=auth).status_code == 200


def test_another_users_id_is_forbidden(client, auth):
    other = register(client, "other@example.com")
    other_id = client.get("/auth/me", headers=other).json()["id"]
    response = client.get(f"/users/{other_id}/items", headers=auth)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_default_bodies_are_public(client):
    response = client.get("/bodies/defaults")
    assert response.status_code == 200
    assert [b["name"] for b in response.json()] == ["Default A", "Default B"]
