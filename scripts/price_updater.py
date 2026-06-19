"""
MagicSteam — Scryfall price updater
====================================
Downloads Scryfall's default_cards bulk data and refreshes the `prices` column
for every card in the local database.

Scryfall publishes new price data once daily (they pull from TCGPlayer /
CardMarket overnight UTC).  This script checks the `updated_at` timestamp on
Scryfall's bulk-data manifest before downloading; if the data hasn't changed
since the last successful run it exits immediately (cheap HEAD-equivalent).

Usage:
    python scripts/price_updater.py          # run once, exits when done
    (also called automatically by app/main.py every hour on startup)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow running directly: python scripts/price_updater.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

_BULK_META_URL = "https://api.scryfall.com/bulk-data"
_STATE_FILE    = Path(__file__).resolve().parent.parent / "data" / "price_state.json"
_BATCH_SIZE    = 500

_USD_TO_OMR = 0.38450
_USD_TO_AED = 3.67250


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Currency conversion (inline copy so script works standalone without FastAPI)
# ---------------------------------------------------------------------------

_eur_to_usd: float = 1.08   # fallback if frankfurter.app is unreachable


def _fetch_eur_usd() -> float:
    global _eur_to_usd
    try:
        r = httpx.get("https://api.frankfurter.app/latest?from=EUR&to=USD", timeout=6)
        r.raise_for_status()
        _eur_to_usd = float(r.json()["rates"]["USD"])
    except Exception:
        pass
    return _eur_to_usd


def _enrich_prices(raw: dict | None, eur_rate: float) -> dict | None:
    """Add omr/aed keys to a Scryfall prices dict."""
    if not raw:
        return raw
    result = dict(raw)
    usd = None
    try:
        if raw.get("usd"):
            usd = float(raw["usd"])
    except (ValueError, TypeError):
        pass
    if usd is None:
        try:
            if raw.get("eur"):
                usd = float(raw["eur"]) * eur_rate
        except (ValueError, TypeError):
            pass
    if usd is not None and usd > 0:
        result["omr"] = round(usd * _USD_TO_OMR, 3)
        result["aed"] = round(usd * _USD_TO_AED, 3)
    else:
        result["omr"] = None
        result["aed"] = None
    return result


# ---------------------------------------------------------------------------
# Main update logic
# ---------------------------------------------------------------------------

def run_if_stale() -> bool:
    """
    Check Scryfall for new price data.  If newer than our last run, download
    the bulk dataset, enrich prices with OMR/AED, and apply to the database.

    Returns True when the DB was updated, False when already current.
    """
    print(f"[PriceUpdater] Checking Scryfall bulk-data manifest…", flush=True)

    # 1. Fetch manifest
    try:
        resp = httpx.get(_BULK_META_URL, timeout=12)
        resp.raise_for_status()
        meta = resp.json()
    except Exception as exc:
        print(f"[PriceUpdater] Manifest fetch failed: {exc}", flush=True)
        return False

    dataset = next(
        (d for d in meta.get("data", []) if d.get("type") == "default_cards"),
        None,
    )
    if not dataset:
        print("[PriceUpdater] default_cards dataset not found in manifest", flush=True)
        return False

    scryfall_ts  = dataset.get("updated_at", "")
    download_uri = dataset.get("download_uri", "")

    state = _load_state()
    if state.get("last_scryfall_ts") == scryfall_ts:
        print(f"[PriceUpdater] Prices already current (Scryfall: {scryfall_ts})", flush=True)
        return False

    # 2. Fetch EUR/USD rate once for this run
    eur_rate = _fetch_eur_usd()
    print(f"[PriceUpdater] EUR/USD rate: {eur_rate:.4f}", flush=True)

    # 3. Download bulk data
    print(f"[PriceUpdater] Downloading bulk data…", flush=True)
    t0 = time.time()
    chunks: list[bytes] = []
    try:
        with httpx.stream("GET", download_uri, follow_redirects=True, timeout=300) as r:
            total = int(r.headers.get("content-length", 0))
            done  = 0
            for chunk in r.iter_bytes(chunk_size=65536):
                chunks.append(chunk)
                done += len(chunk)
                if total and done % (10 * 1024 * 1024) < 65536:
                    pct = done * 100 // total
                    print(f"  {pct}%  {done // 1_000_000}MB / {total // 1_000_000}MB",
                          flush=True)
    except Exception as exc:
        print(f"[PriceUpdater] Download failed: {exc}", flush=True)
        return False

    try:
        cards_data = json.loads(b"".join(chunks))
    except Exception as exc:
        print(f"[PriceUpdater] JSON parse failed: {exc}", flush=True)
        return False

    dl_secs = time.time() - t0
    print(f"[PriceUpdater] {len(cards_data):,} cards parsed in {dl_secs:.1f}s", flush=True)

    # 4. Build {scryfall_id → enriched_prices} map
    price_map: dict[str, str] = {}  # scryfall_id → JSON-serialised enriched prices
    for card in cards_data:
        sid    = card.get("id")
        prices = card.get("prices")
        if sid and prices:
            enriched = _enrich_prices(prices, eur_rate)
            price_map[sid] = json.dumps(enriched)

    print(f"[PriceUpdater] {len(price_map):,} price entries built. Applying to DB…",
          flush=True)

    # 5. Apply to DB
    from sqlalchemy import text
    from app.database import engine

    t1 = time.time()
    updated = 0
    try:
        with engine.connect() as conn:
            # Fetch our card IDs once so we only touch rows that exist
            rows = conn.execute(
                text("SELECT id, scryfall_id FROM cards")
            ).fetchall()

            batch: list[dict] = []
            for row in rows:
                sid = row[1]
                if sid in price_map:
                    batch.append({"prices": price_map[sid], "card_id": row[0]})

                if len(batch) >= _BATCH_SIZE:
                    conn.execute(
                        text("UPDATE cards SET prices = :prices WHERE id = :card_id"),
                        batch,
                    )
                    updated += len(batch)
                    batch = []

            if batch:
                conn.execute(
                    text("UPDATE cards SET prices = :prices WHERE id = :card_id"),
                    batch,
                )
                updated += len(batch)

            conn.commit()

    except Exception as exc:
        print(f"[PriceUpdater] DB update failed: {exc}", flush=True)
        return False

    db_secs = time.time() - t1
    total_secs = time.time() - t0
    print(
        f"[PriceUpdater] Done. {updated:,} rows updated in {db_secs:.1f}s "
        f"(total {total_secs:.1f}s)",
        flush=True,
    )

    # 6. Persist state so next check is a no-op if Scryfall hasn't changed
    _save_state({
        "last_scryfall_ts": scryfall_ts,
        "last_run_utc":     datetime.now(timezone.utc).isoformat(),
        "rows_updated":     updated,
    })

    # 7. Invalidate in-process search cache (stale HTML has old prices)
    try:
        from app.modules.catalogue.cache import search_cache
        search_cache.clear()
        print("[PriceUpdater] In-process search cache cleared", flush=True)
    except Exception:
        pass

    return True


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Refresh card prices from Scryfall")
    ap.add_argument("--force", action="store_true",
                    help="Ignore state file and re-download even if already current")
    args = ap.parse_args()

    if args.force and _STATE_FILE.exists():
        _STATE_FILE.unlink()
        print("[PriceUpdater] State cleared — forcing full download", flush=True)

    updated = run_if_stale()
    sys.exit(0 if updated else 0)
