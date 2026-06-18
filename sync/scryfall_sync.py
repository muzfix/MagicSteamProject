"""
Scryfall Bulk Sync
==================
Downloads the full MTG card catalogue and populates your local database.

Usage:
    python sync/scryfall_sync.py

Run once to seed the database, then once daily to pick up new releases.
Expected duration: 10-30 minutes on first run (~130MB download + 100k+ inserts).
Subsequent runs are fast — only new/changed cards are inserted.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.modules.catalogue.models import Card, MTGSet
from app.modules.catalogue.scryfall_client import get_all_sets, get_bulk_data_url


def sync_sets(db: Session) -> None:
    print("Step 1/3 — Syncing sets from Scryfall...")
    sets_data = get_all_sets()
    new_count = 0
    for s in sets_data:
        existing = db.query(MTGSet).filter(MTGSet.code == s["code"]).first()
        if not existing:
            db.add(MTGSet(
                code=s["code"],
                name=s["name"],
                released_at=s.get("released_at"),
                set_type=s.get("set_type"),
                card_count=s.get("card_count"),
                icon_svg_uri=s.get("icon_svg_uri"),
                scryfall_id=s.get("id"),
            ))
            new_count += 1
    db.commit()
    print(f"  {len(sets_data)} sets total — {new_count} new.")


def sync_cards(db: Session) -> None:
    print("Step 2/3 — Downloading bulk card data from Scryfall...")
    bulk_url = get_bulk_data_url()
    print(f"  URL: {bulk_url}")
    print("  Downloading (~130MB)...")

    content = b""
    with httpx.stream("GET", bulk_url, follow_redirects=True, timeout=120) as r:
        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        for chunk in r.iter_bytes(chunk_size=65536):
            content += chunk
            downloaded += len(chunk)
            if total:
                pct = downloaded * 100 // total
                print(f"\r  {pct}% ({downloaded // 1_000_000}MB / {total // 1_000_000}MB)", end="", flush=True)
    print()

    cards_data = json.loads(content)
    print(f"Step 3/3 — Inserting {len(cards_data)} cards into database...")

    batch_size = 500
    new_count = 0
    for i in range(0, len(cards_data), batch_size):
        batch = cards_data[i : i + batch_size]
        for c in batch:
            if db.query(Card).filter(Card.scryfall_id == c["id"]).first():
                continue
            image_uri = None
            if "image_uris" in c:
                image_uri = c["image_uris"].get("normal")
            db.add(Card(
                scryfall_id=c["id"],
                name=c["name"],
                set_code=c.get("set"),
                set_name=c.get("set_name"),
                collector_number=c.get("collector_number"),
                mana_cost=c.get("mana_cost"),
                type_line=c.get("type_line"),
                oracle_text=c.get("oracle_text"),
                rarity=c.get("rarity"),
                image_uri=image_uri,
                colors=c.get("colors"),
                color_identity=c.get("color_identity"),
                legalities=c.get("legalities"),
                prices=c.get("prices"),
                scryfall_data=c,
            ))
            new_count += 1
        db.commit()
        done = min(i + batch_size, len(cards_data))
        print(f"  {done}/{len(cards_data)} processed...", end="\r")

    print(f"\n  Done. {new_count} new cards inserted.")


if __name__ == "__main__":
    print("MagicSteam — Scryfall Sync")
    print("=" * 40)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        sync_sets(db)
        sync_cards(db)
    finally:
        db.close()
    print("\nSync complete. Your database is ready.")
