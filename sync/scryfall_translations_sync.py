"""
Download Scryfall's all_cards bulk file and populate card_translations
with every non-English printed card name.

Requirements:  pip install ijson
Run from project root:  python sync/scryfall_translations_sync.py

Download size: ~1.5 GB. Takes 15-30 minutes depending on connection.
Only cards already in your local DB (matched by oracle_id) are stored.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx

try:
    import ijson
except ImportError:
    print("ERROR: ijson is required.  Run:  pip install ijson")
    sys.exit(1)

from sqlalchemy import text
from app.database import SessionLocal, engine
from app.modules.catalogue.models import Base, CardTranslation


def download(url: str, dest: str):
    print(f"Downloading to {dest} ...")
    with httpx.stream("GET", url, timeout=600, follow_redirects=True) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        t0 = time.time()
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes(chunk_size=256 * 1024):
                f.write(chunk)
                done += len(chunk)
                if total:
                    pct = done * 100 // total
                    mb_done = done // 1024 // 1024
                    mb_total = total // 1024 // 1024
                    elapsed = time.time() - t0
                    speed = done / elapsed / 1024 / 1024 if elapsed else 0
                    print(f"\r  {pct}%  {mb_done}/{mb_total} MB  {speed:.1f} MB/s   ", end="", flush=True)
    print()


def run():
    # Make sure tables exist
    Base.metadata.create_all(bind=engine)

    # Load oracle_ids present in our local cards table
    db = SessionLocal()
    print("Loading local oracle_ids...")
    rows = db.execute(text("SELECT oracle_id FROM cards WHERE oracle_id IS NOT NULL")).fetchall()
    local_oracle_ids = {r[0] for r in rows}
    print(f"  {len(local_oracle_ids)} unique oracle_ids in local DB.")

    if not local_oracle_ids:
        print("No oracle_ids found. Run scripts/migrate_v2.py first.")
        db.close()
        return

    # Fetch bulk data download URL
    print("Fetching Scryfall bulk data index...")
    r = httpx.get("https://api.scryfall.com/bulk-data", timeout=30)
    r.raise_for_status()
    all_cards_url = next(
        b["download_uri"] for b in r.json()["data"] if b["type"] == "all_cards"
    )

    # Save alongside the project on D: — not the Windows temp folder on C:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(project_root, "data")
    os.makedirs(data_dir, exist_ok=True)
    tmp_path = os.path.join(data_dir, "scryfall_all_cards.json")
    download(all_cards_url, tmp_path)

    print("Parsing and importing translations...")
    batch = []
    seen: set[tuple[str, str]] = set()
    imported = 0
    skipped = 0

    with open(tmp_path, "rb") as f:
        for card in ijson.items(f, "item"):
            lang = card.get("lang", "en")
            if lang == "en":
                continue
            oracle_id = card.get("oracle_id")
            printed_name = card.get("printed_name")
            if not oracle_id or not printed_name:
                continue
            if oracle_id not in local_oracle_ids:
                skipped += 1
                continue
            key = (oracle_id, lang)
            if key in seen:
                continue
            seen.add(key)
            batch.append({"oracle_id": oracle_id, "lang": lang, "printed_name": printed_name})

            if len(batch) >= 2000:
                db.bulk_insert_mappings(CardTranslation, batch)
                db.commit()
                imported += len(batch)
                batch = []
                print(f"\r  {imported:,} translations imported...", end="", flush=True)

    if batch:
        db.bulk_insert_mappings(CardTranslation, batch)
        db.commit()
        imported += len(batch)

    db.close()
    print(f"\n\nDone! {imported:,} translations imported ({skipped:,} skipped — card not in local DB).")
    print(f"Bulk file saved at: {tmp_path}")
    print("You can delete it once done — it's only needed for the initial sync.")


if __name__ == "__main__":
    run()
