import time
import httpx
from app.config import settings

BASE_URL = settings.SCRYFALL_BASE_URL
_DELAY = 0.1  # 100ms between requests — Scryfall enforces 10 req/sec


def get_all_sets() -> list[dict]:
    with httpx.Client(timeout=30) as client:
        r = client.get(f"{BASE_URL}/sets")
        r.raise_for_status()
        return r.json()["data"]


def search_cards(query: str, page: int = 1) -> dict:
    with httpx.Client(timeout=30) as client:
        r = client.get(f"{BASE_URL}/cards/search", params={"q": query, "page": page})
        r.raise_for_status()
        time.sleep(_DELAY)
        return r.json()


def get_card_by_name(name: str) -> dict | None:
    with httpx.Client(timeout=30) as client:
        r = client.get(f"{BASE_URL}/cards/named", params={"exact": name})
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


def get_bulk_data_url() -> str:
    """Returns the download URL for Scryfall's default_cards bulk JSON (~130MB)."""
    with httpx.Client(timeout=30) as client:
        r = client.get(f"{BASE_URL}/bulk-data")
        r.raise_for_status()
        for item in r.json()["data"]:
            if item["type"] == "default_cards":
                return item["download_uri"]
    raise ValueError("Could not find default_cards bulk data endpoint")
