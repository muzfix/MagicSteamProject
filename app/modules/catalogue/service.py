from sqlalchemy import cast, String, or_, case, func, select
from sqlalchemy.orm import Session

from app.modules.catalogue.models import Card, CardTranslation, MTGSet
from app.modules.catalogue.currency import add_local_prices
from app.modules.catalogue.search_parser import parse

# Keyword abilities that live in scryfall_data.keywords JSON array.
# Searching there is precise: a card mentioning "flying" in rules text (like
# "target creature gains flying") would be a false positive if we only checked
# oracle_text.  The JSON array contains only abilities the card actually HAS.
_KEYWORD_ABILITIES: frozenset[str] = frozenset({
    "flying", "haste", "trample", "vigilance", "deathtouch",
    "first strike", "double strike", "reach", "flash", "menace",
    "lifelink", "hexproof", "shroud", "indestructible", "ward",
    "protection", "cycling", "cascade", "kicker", "flashback", "morph",
    "madness", "convoke", "delve", "emerge", "evoke",
    "undying", "persist", "infect", "wither", "annihilator",
    "ninjutsu", "overload", "bestow", "scavenge", "prowl", "suspend",
    "threshold", "delirium", "revolt", "morbid", "ferocious",
    "foretell", "boast", "exploit", "tribute", "bolster", "constellation",
    # "devotion" deliberately excluded: Scryfall does NOT store it in the
    # keywords JSON array, so json_extract returns 0 hits. It falls through
    # to oracle_text ILIKE '%devotion%' which works correctly.
    "enrage", "explore", "raid", "ascend", "spectacle",
    "addendum", "adapt", "afterlife", "amass", "escape", "mutate",
    "companion", "learn", "coven", "decayed", "disturb", "daybound",
    "training", "blitz", "casualty", "connive", "battalion", "bloodthirst",
    "soulbond", "detain", "unleash", "inspired", "heroic", "monstrosity",
    "populate", "provoke",
})


def _enrich(card: Card) -> Card:
    card.prices = add_local_prices(card.prices)
    return card


def search_cards(db: Session, query: str, limit: int = 20, offset: int = 0):
    parsed = parse(query)
    # Preserve raw query for name-based bypasses and ordering.
    raw = query.strip()

    q = db.query(Card)

    # ── Colors (AND: card must contain ALL requested colors) ──────────────
    for color in parsed.colors:
        color_cond = cast(Card.color_identity, String).contains(f'"{color}"')
        if parsed.text_tokens and raw:
            # When free-text tokens are present the user may be typing a card
            # name that starts with a color word (e.g. "Black Lotus", "White
            # Sun's Zenith").  Black Lotus has color_identity=[] so it would be
            # filtered out by the strict color check.  Bypass the color filter
            # for any card whose name matches the full raw query so those cards
            # still surface — they'll naturally float to the top of the ordering.
            color_cond = or_(color_cond, Card.name.ilike(f"%{raw}%"))
        q = q.filter(color_cond)

    if parsed.colorless:
        q = q.filter(cast(Card.color_identity, String) == "[]")

    # ── Multicolor / monocolor ────────────────────────────────────────────
    if parsed.multicolor:
        q = q.filter(func.json_array_length(Card.color_identity) >= 2)

    if parsed.monocolor:
        q = q.filter(func.json_array_length(Card.color_identity) == 1)

    # ── Rarity (OR across requested rarities) ─────────────────────────────
    if parsed.rarities:
        q = q.filter(Card.rarity.in_(parsed.rarities))

    # ── Format legality (AND: must be legal in every requested format) ────
    for fmt in parsed.formats:
        q = q.filter(cast(Card.legalities, String).contains(f'"{fmt}": "legal"'))

    # ── CMC / mana value ─────────────────────────────────────────────────
    if parsed.cmc_exact is not None:
        q = q.filter(Card.cmc == int(parsed.cmc_exact))
    if parsed.cmc_max is not None:
        q = q.filter(Card.cmc <= int(parsed.cmc_max))
    if parsed.cmc_min is not None:
        q = q.filter(Card.cmc >= int(parsed.cmc_min))

    # ── Oracle text / keyword tokens ──────────────────────────────────────
    # When free-text tokens are also present, apply the same name-bypass used
    # for colors (Black Lotus pattern): a card whose name matches the full raw
    # query passes the oracle filter regardless.  This prevents oracle synonyms
    # from accidentally hiding exact card-name matches (e.g. if a future synonym
    # were to re-introduce the "bolt" → "deals 3 damage" mapping, Lightning Bolt
    # would still surface for "lightning bolt" searches).
    for token in parsed.oracle_tokens:
        if token in _KEYWORD_ABILITIES:
            proper = token.title()
            q = q.filter(Card.keywords.ilike(f'%"{proper}"%'))
        elif "|" in token:
            oracle_cond = or_(*[Card.oracle_text.ilike(f"%{p}%") for p in token.split("|")])
            if parsed.text_tokens and raw:
                oracle_cond = or_(oracle_cond, Card.name.ilike(f"%{raw}%"))
            q = q.filter(oracle_cond)
        else:
            oracle_cond = Card.oracle_text.ilike(f"%{token}%")
            if parsed.text_tokens and raw:
                oracle_cond = or_(oracle_cond, Card.name.ilike(f"%{raw}%"))
            q = q.filter(oracle_cond)

    # ── Type line tokens (word-boundary match) ────────────────────────────
    # Use OR of positional ILIKE patterns so "Rat" never matches "Pirate"
    # (substring "rat" inside the word "Pirate" would otherwise be a hit).
    for t in parsed.type_tokens:
        q = q.filter(
            or_(
                Card.type_line.ilike(f"% {t} %"),   # interior word
                Card.type_line.ilike(f"% {t}"),      # final word
                Card.type_line.ilike(f"{t} %"),      # first word
                Card.type_line.ilike(t),              # sole word
            )
        )

    # ── Free text tokens (OR across name / type_line / oracle / translations) ─
    for token in parsed.text_tokens:
        translation_subq = (
            select(CardTranslation.oracle_id)
            .where(CardTranslation.printed_name.ilike(f"%{token}%"))
        )
        q = q.filter(
            Card.name.ilike(f"%{token}%")
            | Card.type_line.ilike(f"%{token}%")
            | Card.oracle_text.ilike(f"%{token}%")
            | Card.oracle_id.in_(translation_subq)
        )

    # ── Ordering ──────────────────────────────────────────────────────────
    # Priority tiers (lower = better):
    #   0 — name exactly equals the full raw query   (e.g. "Black Lotus")
    #   1 — name starts with the full raw query      (e.g. "Black Lotus Petal")
    #   2 — name exactly equals the first name word  (e.g. "Counterspell")
    #   3 — name starts with the first name word     (e.g. "Counterspell Trap")
    #   4 — everything else (oracle / type match)
    #
    # We derive a name word from the raw query even when text_tokens is empty.
    # That happens when every word was consumed by oracle/color/keyword synonyms
    # (e.g. "counterspell blue" → oracle:"counter target spell" + color:U, leaving
    # text_tokens=[]).  Without this, the result would be purely alphabetical and
    # the card literally named "Counterspell" would never rise to the top.
    if parsed.text_tokens:
        first = parsed.text_tokens[0]
    else:
        # Fall back to the first sufficiently long word in the raw query
        raw_words = [w for w in raw.split() if len(w) >= 3]
        first = raw_words[0] if raw_words else None

    if first:
        priority = case(
            (Card.name.ilike(raw), 0),
            (Card.name.ilike(f"{raw}%"), 1),
            # Tier 2: name contains full raw query — catches DFC cards whose stored
            # name is "Front // Back" (e.g. "Delver of Secrets // Insectile Aberration")
            # which never match the starts-with tier above.
            (Card.name.ilike(f"%{raw}%"), 2),
            (Card.name.ilike(first), 3),
            (Card.name.ilike(f"{first}%"), 4),
            else_=5,
        )
        q = q.order_by(priority, Card.name)
    else:
        q = q.order_by(Card.name)

    # ── Single query: COUNT(*) OVER() window function avoids double WHERE scan ──
    # Previously: q.count() + q.all() executed the full WHERE clause TWICE.
    # Now: one query, the window function computes the total over the full result
    # set while LIMIT/OFFSET restrict the returned rows.  2× speedup for free.
    q_with_total = q.add_columns(func.count(Card.id).over().label("_total"))
    rows = q_with_total.offset(offset).limit(limit).all()

    total = rows[0]._total if rows else 0
    cards = [_enrich(r[0]) for r in rows]
    return total, cards


def get_card_by_scryfall_id(db: Session, scryfall_id: str) -> Card | None:
    card = db.query(Card).filter(Card.scryfall_id == scryfall_id).first()
    return _enrich(card) if card else None


def get_all_sets(db: Session) -> list[MTGSet]:
    return db.query(MTGSet).order_by(MTGSet.released_at.desc()).all()


def get_set_by_code(db: Session, code: str) -> MTGSet | None:
    return db.query(MTGSet).filter(MTGSet.code == code.lower()).first()
