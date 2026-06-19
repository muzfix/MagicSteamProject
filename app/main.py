from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.database import Base, engine, SessionLocal
# Import all models so Base.metadata.create_all() registers every table
import app.modules.collections.models  # noqa: F401
from app.limiter import limiter
from app.modules.auth.router import router as auth_router
from app.modules.catalogue.router import router as catalogue_router
from app.modules.marketplace.router import router as marketplace_router
from app.modules.collections.router import router as collections_router
from app.modules.pages import router as pages_router
from app.modules.scanner.router import router as scanner_router
from app.modules.payments.router import router as payments_router
from app.modules.catalogue import service
from app.modules.catalogue.cache import make_cache_key, search_cache
from app.modules.catalogue.router import group_picker_cards
from app.modules.catalogue.search_parser import parse
from app.config import settings
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app = FastAPI(
    title="MagicSteam",
    description="Local Magic: The Gathering card marketplace",
    version="0.1.0",
)

# ── Rate limiter ──────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Security headers middleware ───────────────────────────────────────────────
# Applied to every response.  CSP is tight:
#   - Scripts only from 'self' + two pinned CDNs (Tailwind play CDN, HTMX unpkg).
#     No 'unsafe-inline' on scripts — lightbox.js is a static file now.
#   - Images from 'self' + Scryfall (card art CDN).
#   - frame-ancestors 'none' prevents clickjacking (also covered by X-Frame-Options
#     for older browsers).
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    _CSP = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.tailwindcss.com https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
        "img-src 'self' data: https://*.scryfall.io; "
        "connect-src 'self'; "
        "font-src 'self' data:; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none';"
    )

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"]   = self._CSP
        response.headers["X-Content-Type-Options"]    = "nosniff"
        response.headers["X-Frame-Options"]           = "DENY"
        response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"]        = "geolocation=(), microphone=(), camera=()"
        # Set HSTS only when nginx terminates TLS (nginx adds it on HTTPS responses;
        # setting it here on HTTP would break plain-HTTP dev mode).
        if request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# HTML page routes (no prefix — serves /, /marketplace, /store, /sell, /auth/login, /auth/register)
app.include_router(pages_router, tags=["Pages"])

# API routes
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(catalogue_router, prefix="/api/catalogue", tags=["Catalogue"])
app.include_router(marketplace_router, prefix="/api/marketplace", tags=["Marketplace"])
app.include_router(scanner_router, prefix="/api/scanner", tags=["Scanner"])
app.include_router(payments_router, prefix="/api/payments", tags=["Payments"])
app.include_router(collections_router, prefix="/api/collections", tags=["Collections"])

# ---------------------------------------------------------------------------
# Cache warm-up: queries that cover the majority of real-world MTG searches.
# Runs at startup — each query hits the DB once, then lives in cache for 5 min.
# Subsequent identical (or order-permuted) queries are served from memory (<1ms).
# ---------------------------------------------------------------------------

_WARM_QUERIES = [
    # Single most-searched card names
    "lightning bolt", "counterspell", "dark ritual", "sol ring",
    "black lotus", "swords to plowshares", "brainstorm",
    # Color archetypes
    "white removal", "blue counter", "black removal", "red burn", "green ramp",
    "white board wipe", "blue card draw", "black recursion",
    # Abilities
    "flying creature", "haste creature", "deathtouch", "lifelink",
    "trample", "vigilance", "first strike", "double strike",
    # Strategy words
    "board wipe", "tutor", "draw", "mill", "tokens",
    # Format
    "modern", "commander", "pauper",
    # Rarity + color
    "white mythic", "blue rare", "black uncommon", "red common", "green rare",
]

_templates = Jinja2Templates(directory="app/templates")


def _fmt_omr(prices: dict | None) -> str:
    if not prices:
        return "—"
    omr = prices.get("omr")
    if omr is None or omr <= 0:
        return "—"
    if omr >= 1:
        return f"{omr:.3f} OMR"
    baisa = round(omr * 1000)
    return f"{baisa} bz" if baisa > 0 else "—"


_templates.env.filters["fmt_omr"] = _fmt_omr


@app.on_event("startup")
def startup():
    import threading
    _check_secrets()
    Base.metadata.create_all(bind=engine)
    _ensure_schema()
    # Run cache warm-up in a background thread so the server starts immediately.
    # First few requests on a cold start may miss the cache — that's fine.
    t = threading.Thread(target=_warm_cache, daemon=True)
    t.start()
    print("[MagicSteam] Cache warm-up started in background", flush=True)


def _check_secrets() -> None:
    """Refuse to start in production with placeholder secrets."""
    if settings.ENVIRONMENT == "production":
        if settings.SECRET_KEY == "CHANGE_THIS_IN_PRODUCTION":
            raise RuntimeError(
                "SECRET_KEY is still the default placeholder. "
                "Generate one with:  python -c \"import secrets; print(secrets.token_hex(32))\""
                "  and set it in your .env file."
            )


def _ensure_schema() -> None:
    """
    Apply incremental schema changes that create_all() misses on existing databases.
    Safe to run every startup — all statements use IF NOT EXISTS / column-exists checks.
    For the full PostgreSQL GIN index build, run scripts/optimize_db.py separately
    (it uses CONCURRENTLY and may take several minutes).
    """
    from sqlalchemy import inspect as sa_inspect, text

    with engine.connect() as conn:
        # ── users.username_changed_at column ──────────────────────────────
        inspector = sa_inspect(engine)
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        if "username_changed_at" not in user_cols:
            print("[MagicSteam] Adding users.username_changed_at column …", flush=True)
            conn.execute(text("ALTER TABLE users ADD COLUMN username_changed_at TIMESTAMP"))
            conn.commit()

        # ── keywords column ────────────────────────────────────────────────
        existing_cols = {c["name"] for c in inspector.get_columns("cards")}

        if "keywords" not in existing_cols:
            print("[MagicSteam] Adding keywords column …", flush=True)
            conn.execute(text("ALTER TABLE cards ADD COLUMN keywords TEXT"))
            conn.commit()
            if engine.dialect.name == "sqlite":
                conn.execute(text(
                    "UPDATE cards SET keywords = json_extract(scryfall_data, '$.keywords')"
                ))
            else:
                conn.execute(text(
                    "UPDATE cards SET keywords = scryfall_data->>'keywords'"
                ))
            conn.commit()
            print("[MagicSteam] keywords column populated", flush=True)

        # ── DFC image_uri backfill ────────────────────────────────────────
        # Double-faced cards store front-face art under card_faces[0].image_uris.
        # Guard with EXISTS so this is a single fast lookup on already-fixed DBs
        # instead of a full json_extract scan on every startup.
        if engine.dialect.name == "sqlite":
            needs_backfill = conn.execute(text(
                "SELECT EXISTS("
                "  SELECT 1 FROM cards WHERE (image_uri IS NULL OR image_uri = '') "
                "  AND json_extract(scryfall_data, '$.card_faces[0].image_uris.normal') IS NOT NULL"
                ")"
            )).scalar()
            if needs_backfill:
                print("[MagicSteam] Backfilling DFC card images …", flush=True)
                conn.execute(text(
                    "UPDATE cards "
                    "SET image_uri = json_extract(scryfall_data, '$.card_faces[0].image_uris.normal') "
                    "WHERE (image_uri IS NULL OR image_uri = '') "
                    "AND json_extract(scryfall_data, '$.card_faces[0].image_uris.normal') IS NOT NULL"
                ))
                conn.commit()
        else:
            needs_backfill = conn.execute(text(
                "SELECT EXISTS("
                "  SELECT 1 FROM cards WHERE (image_uri IS NULL OR image_uri = '') "
                "  AND scryfall_data->'card_faces'->0->'image_uris'->>'normal' IS NOT NULL"
                ")"
            )).scalar()
            if needs_backfill:
                print("[MagicSteam] Backfilling DFC card images …", flush=True)
                conn.execute(text(
                    "UPDATE cards "
                    "SET image_uri = scryfall_data->'card_faces'->0->'image_uris'->>'normal' "
                    "WHERE (image_uri IS NULL OR image_uri = '') "
                    "AND scryfall_data->'card_faces'->0->'image_uris'->>'normal' IS NOT NULL"
                ))
                conn.commit()

        # ── orders new columns ────────────────────────────────────────────
        order_cols = {c["name"] for c in inspector.get_columns("orders")}
        if "payment_method" not in order_cols:
            print("[MagicSteam] Adding orders.payment_method column …", flush=True)
            conn.execute(text("ALTER TABLE orders ADD COLUMN payment_method VARCHAR(20) DEFAULT 'cod'"))
            conn.commit()
        if "pickup_location" not in order_cols:
            print("[MagicSteam] Adding orders.pickup_location column …", flush=True)
            conn.execute(text("ALTER TABLE orders ADD COLUMN pickup_location VARCHAR(200)"))
            conn.commit()
        if "bundle_listing_id" not in order_cols:
            print("[MagicSteam] Adding orders.bundle_listing_id column …", flush=True)
            conn.execute(text("ALTER TABLE orders ADD COLUMN bundle_listing_id INTEGER"))
            conn.commit()
        # listing_id was NOT NULL before — make it nullable for bundle orders
        # SQLite does not support ALTER COLUMN, so we leave the constraint as-is;
        # the ORM will pass NULL for listing_id on bundle orders and SQLite
        # accepts NULL in NOT NULL columns created before this change in WAL mode.
        # On PostgreSQL this is handled by create_all on the updated model.

        # ── cards indexes ──────────────────────────────────────────────────
        # Check both "idx_" (our names) and "ix_" (SQLAlchemy auto-generated names)
        # so we never create a duplicate index on the same column.
        existing_indexes = {ix["name"] for ix in inspector.get_indexes("cards")}

        _cards_idx = [
            ("idx_cards_rarity",    "ix_cards_rarity",    "CREATE INDEX IF NOT EXISTS idx_cards_rarity    ON cards(rarity)"),
            ("idx_cards_keywords",  "ix_cards_keywords",  "CREATE INDEX IF NOT EXISTS idx_cards_keywords  ON cards(keywords)"),
            ("idx_cards_cmc",       "ix_cards_cmc",       "CREATE INDEX IF NOT EXISTS idx_cards_cmc       ON cards(cmc)"),
            ("idx_cards_oracle_id", "ix_cards_oracle_id", "CREATE INDEX IF NOT EXISTS idx_cards_oracle_id ON cards(oracle_id)"),
        ]
        for our_name, sa_name, sql in _cards_idx:
            if our_name not in existing_indexes and sa_name not in existing_indexes:
                conn.execute(text(sql))
                conn.commit()
                print(f"[MagicSteam] {our_name} created", flush=True)

        # ── card_translations indexes ──────────────────────────────────────
        trans_indexes = {ix["name"] for ix in inspector.get_indexes("card_translations")}

        if ("idx_translations_oracle_id" not in trans_indexes
                and "ix_card_translations_oracle_id" not in trans_indexes):
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_translations_oracle_id "
                "ON card_translations(oracle_id)"
            ))
            conn.commit()
            print("[MagicSteam] idx_translations_oracle_id created", flush=True)

        if ("idx_translations_printed_name" not in trans_indexes
                and "ix_card_translations_printed_name" not in trans_indexes):
            if engine.dialect.name == "sqlite":
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_translations_printed_name "
                    "ON card_translations(printed_name COLLATE NOCASE)"
                ))
            else:
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_translations_printed_name "
                    "ON card_translations(printed_name)"
                ))
            conn.commit()
            print("[MagicSteam] idx_translations_printed_name created", flush=True)


def _warm_cache() -> None:
    """Pre-populate the search cache with the most common queries."""
    from urllib.parse import quote as _url_quote
    BROWSE_LIMIT = 48
    PICKER_LIMIT = 24
    PICKER_FETCH = 400  # must match router.PICKER_FETCH

    db = SessionLocal()
    warmed = 0
    try:
        for raw_q in _WARM_QUERIES:
            try:
                parsed = parse(raw_q)
                key_browse = make_cache_key(parsed) + ":browse:0"
                key_picker = make_cache_key(parsed) + ":picker:0"
                if search_cache.get(key_browse) is not None:
                    continue

                q_enc = _url_quote(raw_q, safe="")

                # Browse: first 48 cards, with total for "Load more"
                total, cards_48 = service.search_cards(db, raw_q, limit=BROWSE_LIMIT, offset=0)

                # Picker: fetch a large batch so all printings of each unique
                # name land in one group tile; paginate by groups, not printings.
                _, cards_picker = service.search_cards(db, raw_q, limit=PICKER_FETCH, offset=0)
                all_picker_groups = group_picker_cards(cards_picker, {})
                page_groups      = all_picker_groups[:PICKER_LIMIT]
                total_groups     = len(all_picker_groups)

                html_browse = _templates.env.get_template(
                    "catalogue/card_browse_results.html"
                ).render({
                    "cards":          cards_48,
                    "request":        None,
                    "q_enc":          q_enc,
                    "offset":         0,
                    "total":          total,
                    "has_more":       total > BROWSE_LIMIT,
                    "next_offset":    BROWSE_LIMIT,
                    "remaining":      max(0, total - BROWSE_LIMIT),
                    "listing_counts": {},
                })
                html_picker = _templates.env.get_template(
                    "catalogue/card_picker_results.html"
                ).render({
                    "card_groups":    page_groups,
                    "request":        None,
                    "name_enc":       q_enc,
                    "offset":         0,
                    "total":          total_groups,
                    "has_more":       total_groups > PICKER_LIMIT,
                    "next_offset":    PICKER_LIMIT,
                    "remaining":      max(0, total_groups - len(page_groups)),
                    "listing_counts": {},
                })

                search_cache.set(key_browse, html_browse)
                search_cache.set(key_picker, html_picker)
                warmed += 1
            except Exception:
                pass
    finally:
        db.close()

    print(f"[MagicSteam] Search cache warmed: {warmed}/{len(_WARM_QUERIES)} queries, "
          f"{search_cache.stats()['size']} entries")
