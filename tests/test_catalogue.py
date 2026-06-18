"""
Catalogue endpoint tests.
These test your local database — run sync/scryfall_sync.py first.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_list_sets_returns_list():
    response = client.get("/api/catalogue/sets")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_card_search_requires_query():
    response = client.get("/api/catalogue/cards/search")
    assert response.status_code == 422  # missing required 'q' param


def test_card_search_returns_results():
    response = client.get("/api/catalogue/cards/search?q=lightning+bolt")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "cards" in data
