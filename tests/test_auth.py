"""
Basic auth tests.
Run with: pytest tests/
Requires a test database — set TEST_DATABASE_URL in .env or environment.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_register_new_user():
    response = client.post("/auth/register", json={
        "email": "tester@example.com",
        "username": "tester",
        "password": "strongpassword99",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "tester@example.com"
    assert "password" not in data
    assert "password_hash" not in data


def test_login_returns_token():
    response = client.post("/auth/login", json={
        "email": "tester@example.com",
        "password": "strongpassword99",
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password():
    response = client.post("/auth/login", json={
        "email": "tester@example.com",
        "password": "wrongpassword",
    })
    assert response.status_code == 401
