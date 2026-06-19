import json
from urllib.parse import quote as _url_quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.dependencies import get_current_admin
from app.modules.auth.models import User
from app.modules.catalogue import service
from app.modules.catalogue.cache import make_cache_key, search_cache
from app.modules.catalogue.schemas import CardOut, CardSearchResult, SetOut
from app.modules.catalogue.search_parser import parse
from app.modules.marketplace.models import Listing

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

BROWSE_LIMIT = 48
PICKER_LIMIT = 24   # unique card names (groups) shown per page
PICKER_FETCH = 400  # individual printings fetched to build all groups


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


templates.env.filters["fmt_omr"] = _fmt_omr


def _foil_label(scryfall_data: dict) -> str:
    """Return 'Foil', 'Etched', or '' based on the card's finishes array."""
    finishes = scryfall_data.get("finishes", [])
    if not finishes:
        return ""
    non_foil = "nonfoil" in finishes
    foil     = "foil" in finishes
    etched   = "etched" in finishes
    if foil and not non_foil:
        return "Foil"
    if etched and not non_foil:
        return "Etched"
    return ""


# ---------------------------------------------------------------------------
# Card grouping for the picker (one tile per unique card name)
# ---------------------------------------------------------------------------

def group_picker_cards(cards: list, listing_counts: dict | None = None) -> list[dict]:
    """
    Deduplicate cards by name.  Returns a list of groups, preserving the
    ordering of first occurrence (i.e. priority-sorted from search_cards).

    Each group is:
        {
          "rep":            Card,           # representative (first/best) printing
          "variant_count":  int,            # total number of printings
          "total_listings": int,            # active community listings across all printings
          "variants_json":  str,            # JSON string for data-variants attribute
        }
    """
    lc = listing_counts or {}
    seen: dict[str, list] = {}
    order: list[str] = []

    for card in cards:
        if card.name not in seen:
            seen[card.name] = []
            order.append(card.name)
        seen[card.name].append(card)

    groups = []
    for name in order:
        variants = seen[name]
        rep = variants[0]

        variant_dicts = []
        for v in variants:
            sd = v.scryfall_data or {}
            iuris = sd.get("image_uris") or {}
            # DFC cards store images under card_faces[0] — fall back if top-level is absent
            if not iuris:
                faces = sd.get("card_faces") or []
                if faces:
                    iuris = faces[0].get("image_uris") or {}
            img    = v.image_uri or iuris.get("normal") or ""
            img_hd = iuris.get("large") or iuris.get("normal") or img
            # Back face image for DFC cards (transform, modal_dfc, etc.)
            back_faces = sd.get("card_faces") or []
            img_back = ""
            if len(back_faces) > 1:
                back_iuris = back_faces[1].get("image_uris") or {}
                img_back = back_iuris.get("large") or back_iuris.get("normal") or ""
            variant_dicts.append({
                "id":          v.scryfall_id,
                "name":        v.name,
                "set":         v.set_name or "",
                "released_at": (sd.get("released_at") or "")[:4],
                "img":         img,
                "img_hd":      img_hd,
                "img_back":    img_back,
                "price":       _fmt_omr(v.prices),
                "foil_label":  _foil_label(sd),
                "listing_cnt": lc.get(v.id, 0),
            })

        groups.append({
            "rep":            rep,
            "variant_count":  len(variants),
            "total_listings": sum(lc.get(v.id, 0) for v in variants),
            "variants_json":  json.dumps(variant_dicts, ensure_ascii=False),
        })

    return groups


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_listing_counts(db: Session, card_ids: list[int]) -> dict[int, int]:
    if not card_ids or db is None:
        return {}
    rows = (
        db.query(Listing.card_id, func.count(Listing.id).label("cnt"))
        .filter(Listing.card_id.in_(card_ids), Listing.is_active == 1)
        .group_by(Listing.card_id)
        .all()
    )
    return {r.card_id: r.cnt for r in rows}


def _render_browse(
    cards: list, request, *, q: str = "", offset: int = 0,
    total: int = 0, listing_counts: dict | None = None,
) -> str:
    shown = offset + len(cards)
    return templates.env.get_template("catalogue/card_browse_results.html").render({
        "cards":          cards,
        "request":        request,
        "q_enc":          _url_quote(q, safe=""),
        "offset":         offset,
        "total":          total,
        "has_more":       shown < total,
        "next_offset":    offset + BROWSE_LIMIT,
        "remaining":      max(0, total - shown),
        "listing_counts": listing_counts or {},
    })


def _render_picker(
    groups: list[dict], request, *, name: str = "", offset: int = 0,
    total: int = 0, listing_counts: dict | None = None,
) -> str:
    """Render picker HTML.  `groups` is a pre-built slice; `total` is the
    total number of unique-name groups (NOT individual printings)."""
    lc = listing_counts or {}
    shown = offset + len(groups)
    return templates.env.get_template("catalogue/card_picker_results.html").render({
        "card_groups":    groups,
        "request":        request,
        "name_enc":       _url_quote(name, safe=""),
        "offset":         offset,
        "total":          total,
        "has_more":       shown < total,
        "next_offset":    offset + PICKER_LIMIT,
        "remaining":      max(0, total - shown),
        "listing_counts": lc,
    })


# ---------------------------------------------------------------------------
# Standard catalogue API
# ---------------------------------------------------------------------------

@router.get("/sets", response_model=list[SetOut])
def list_sets(db: Session = Depends(get_db)):
    return service.get_all_sets(db)


@router.get("/sets/{code}", response_model=SetOut)
def get_set(code: str, db: Session = Depends(get_db)):
    mtg_set = service.get_set_by_code(db, code)
    if not mtg_set:
        raise HTTPException(404, "Set not found")
    return mtg_set


@router.get("/cards/search", response_model=CardSearchResult)
def search_cards(
    q: str = Query(..., min_length=1, description="Card name to search"),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    total, cards = service.search_cards(db, q, limit, offset)
    return {"total": total, "cards": cards}


# ---------------------------------------------------------------------------
# HTMX fragments — with TTL+LRU in-process cache
# ---------------------------------------------------------------------------

@router.get("/cards/picker", response_class=HTMLResponse)
def card_picker_htmx(
    request: Request,
    name: str = Query(default=""),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    name = name.strip()
    if len(name) < 2:
        return HTMLResponse("")

    parsed = parse(name)
    # `offset` here is a GROUP offset (unique card names), not a card-printing offset.
    cache_key = make_cache_key(parsed) + f":picker:{offset}"

    cached = search_cache.get(cache_key)
    if cached is not None:
        return HTMLResponse(cached)

    # Fetch a generous batch of printings so that all variants of every
    # top-priority card name land in the same group tile.  Pagination is then
    # over unique card names, not individual printings — eliminating the
    # "Load more shows another Lightning Bolt tile" problem.
    _, cards = service.search_cards(db, name, limit=PICKER_FETCH, offset=0)
    lc = _get_listing_counts(db, [c.id for c in cards])
    all_groups = group_picker_cards(cards, lc)
    total_groups = len(all_groups)
    page_groups = all_groups[offset : offset + PICKER_LIMIT]

    html = _render_picker(page_groups, request, name=name, offset=offset,
                          total=total_groups, listing_counts=lc)
    search_cache.set(cache_key, html)
    return HTMLResponse(html)


@router.get("/cards/browse", response_class=HTMLResponse)
def card_browse_htmx(
    request: Request,
    q: str = Query(default=""),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    q = q.strip()
    if len(q) < 2:
        return HTMLResponse(
            '<p class="col-span-full text-sm text-gray-400 py-10 text-center">'
            "Type at least 2 characters to search.</p>"
        )

    parsed = parse(q)
    cache_key = make_cache_key(parsed) + f":browse:{offset}"

    cached = search_cache.get(cache_key)
    if cached is not None:
        return HTMLResponse(cached)

    total, cards = service.search_cards(db, q, limit=BROWSE_LIMIT, offset=offset)
    listing_counts = _get_listing_counts(db, [c.id for c in cards])
    html = _render_browse(cards, request, q=q, offset=offset, total=total,
                          listing_counts=listing_counts)
    search_cache.set(cache_key, html)
    return HTMLResponse(html)


@router.get("/cards/{scryfall_id}", response_model=CardOut)
def get_card(scryfall_id: str, db: Session = Depends(get_db)):
    card = service.get_card_by_scryfall_id(db, scryfall_id)
    if not card:
        raise HTTPException(404, "Card not found")
    return card


# ---------------------------------------------------------------------------
# Cache management (admin only)
# ---------------------------------------------------------------------------

@router.get("/cache/stats")
def cache_stats(_: User = Depends(get_current_admin)):
    return search_cache.stats()


@router.post("/cache/clear")
def cache_clear(_: User = Depends(get_current_admin)):
    search_cache.clear()
    return {"status": "cleared", "size": 0}


@router.post("/cache/evict-expired")
def cache_evict_expired(_: User = Depends(get_current_admin)):
    removed = search_cache.evict_expired()
    return {"removed": removed, **search_cache.stats()}
