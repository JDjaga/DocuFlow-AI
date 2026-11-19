"""Authentication tests: registration, login and protected routes."""
from fastapi.testclient import TestClient


def test_register_returns_token_and_safe_user(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Asha Rao",
            "email": "asha@example.com",
            "password": "Secret123!",
            "confirm_password": "Secret123!",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "asha@example.com"
    # A password hash must never appear in an API response.
    assert "hashed_password" not in response.text
    assert "password" not in body["user"]


def test_register_rejects_duplicate_email(client: TestClient):
    payload = {
        "full_name": "Asha Rao",
        "email": "duplicate@example.com",
        "password": "Secret123!",
        "confirm_password": "Secret123!",
    }
    assert client.post("/api/auth/register", json=payload).status_code == 201

    second = client.post("/api/auth/register", json=payload)
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]


def test_register_rejects_mismatched_passwords(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Asha Rao",
            "email": "mismatch@example.com",
            "password": "Secret123!",
            "confirm_password": "Different123!",
        },
    )
    assert response.status_code == 422
    assert "do not match" in response.json()["detail"]


def test_register_rejects_short_password(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Asha Rao",
            "email": "short@example.com",
            "password": "123",
            "confirm_password": "123",
        },
    )
    assert response.status_code == 422


def test_register_rejects_invalid_email(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Asha Rao",
            "email": "not-an-email",
            "password": "Secret123!",
            "confirm_password": "Secret123!",
        },
    )
    assert response.status_code == 422


def test_login_success_and_wrong_password(client: TestClient):
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Asha Rao",
            "email": "login@example.com",
            "password": "Secret123!",
            "confirm_password": "Secret123!",
        },
    )

    ok = client.post("/api/auth/login", json={"email": "login@example.com", "password": "Secret123!"})
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    wrong = client.post("/api/auth/login", json={"email": "login@example.com", "password": "Nope12345!"})
    assert wrong.status_code == 401


def test_login_unknown_email_returns_401_not_404(client: TestClient):
    """The API must not reveal whether an email is registered."""
    response = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "Whatever1!"})
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_me_requires_valid_token(client: TestClient, register_user):
    headers = register_user(client, email="me@example.com")["headers"]

    ok = client.get("/api/auth/me", headers=headers)
    assert ok.status_code == 200
    assert ok.json()["email"] == "me@example.com"

    assert client.get("/api/auth/me").status_code == 401
    assert client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    ).status_code == 401
