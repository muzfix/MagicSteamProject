import re
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from app.modules.catalogue.models import Card, MTGSet
from app.modules.catalogue.currency import add_local_prices
from app.modules.auth.models import User
from app.modules.collections.models import (
    BundleListing, CardCategory, Collection, CollectionCard,
    CollectionType, DeckFormat, FORMAT_LIMITS,
    MAX_COLLECTIONS_PER_USER, MAX_COLLECTION_CARDS,
)
from app.modules.collections.schemas import (
    BundleListingCreate, CollectionCardAdd, CollectionCreate, CollectionUpdate,
)


def _omr(card: Card) -> Optional[float]:
    if not card.prices or not isinstance(card.prices, dict):
        return None
    enriched = add_local_prices(card.prices)
    if not enriched:
        return None
    omr = enriched.get("omr")
    if omr is None:
        return None
    try:
        v = float(omr)
        return v if v > 0 else None
    except (ValueError, TypeError):
        return None


def _set_year(card: Card, db: Session) -> Optional[str]:
    s = db.query(MTGSet).filter(MTGSet.code == card.set_code).first()
    if s and s.released_at:
        return s.released_at[:4]
    return None


def _card_out(cc: CollectionCard, card: Card, db: Session) -> dict:
    return {
        "id": cc.id,
        "collection_id": cc.collection_id,
        "card_id": card.id,
        "scryfall_id": card.scryfall_id,
        "name": card.name,
        "set_name": card.set_name,
        "set_code": card.set_code,
        "released_at": _set_year(card, db),
        "image_uri": card.image_uri,
        "quantity": cc.quantity,
        "category": cc.category,
        "price_omr": _omr(card),
        "type_line": card.type_line,
        "mana_cost": card.mana_cost,
        "cmc": float(card.cmc) if card.cmc is not None else None,
        "layout": card.scryfall_data.get("layout", "normal") if card.scryfall_data else "normal",
        "oracle_text": card.oracle_text,
    }


def _can_partner(card: Card) -> bool:
    """True if this card is eligible to share the command zone with another commander."""
    oracle = (card.oracle_text or "").lower()
    tl = (card.type_line or "").lower()
    return (
        "partner" in oracle or
        "choose a background" in oracle or
        "friends forever" in oracle or
        "doctor's companion" in oracle or
        ("background" in tl and "enchantment" in tl)  # Background enchantment subtype
    )


def _collection_summary(col: Collection, db: Session) -> dict:
    rows = (
        db.query(CollectionCard, Card)
        .join(Card, CollectionCard.card_id == Card.id)
        .filter(CollectionCard.collection_id == col.id)
        .all()
    )
    card_count = sum(cc.quantity for cc, _ in rows)
    total_value = 0.0
    for cc, card in rows:
        p = _omr(card)
        if p:
            total_value += p * cc.quantity

    bundle = (
        db.query(BundleListing)
        .filter(BundleListing.collection_id == col.id, BundleListing.is_active == 1)
        .first()
    )

    return {
        "id": col.id,
        "user_id": col.user_id,
        "name": col.name,
        "type": col.type,
        "format": col.format,
        "cover_image_uri": col.cover_image_uri,
        "card_count": card_count,
        "total_value_omr": round(total_value, 3) if total_value else None,
        "is_listed_for_sale": bundle is not None,
        "bundle_listing_id": bundle.id if bundle else None,
        "bundle_price": bundle.price if bundle else None,
        "created_at": col.created_at,
        "updated_at": col.updated_at,
    }


def get_user_collections(db: Session, user_id: int) -> list[dict]:
    cols = (
        db.query(Collection)
        .filter(Collection.user_id == user_id, Collection.is_active == 1)
        .order_by(Collection.updated_at.desc())
        .all()
    )
    return [_collection_summary(c, db) for c in cols]


def get_collection(db: Session, collection_id: int, user_id: int) -> Optional[dict]:
    col = db.query(Collection).filter(
        Collection.id == collection_id,
        Collection.is_active == 1,
    ).first()
    if not col:
        return None
    # Allow owner or anyone for public view — caller enforces ownership if needed
    summary = _collection_summary(col, db)
    rows = (
        db.query(CollectionCard, Card)
        .join(Card, CollectionCard.card_id == Card.id)
        .filter(CollectionCard.collection_id == collection_id)
        .order_by(CollectionCard.category, CollectionCard.added_at)
        .all()
    )
    summary["cards"] = [_card_out(cc, card, db) for cc, card in rows]
    return summary


def create_collection(db: Session, user_id: int, data: CollectionCreate) -> dict:
    count = db.query(sqlfunc.count(Collection.id)).filter(
        Collection.user_id == user_id, Collection.is_active == 1
    ).scalar()
    if count >= MAX_COLLECTIONS_PER_USER:
        raise ValueError(f"Maximum {MAX_COLLECTIONS_PER_USER} collections per user")

    if data.type == CollectionType.deck and data.format is None:
        data = data.model_copy(update={"format": DeckFormat.custom})

    col = Collection(
        user_id=user_id,
        name=data.name,
        type=data.type,
        format=data.format,
    )
    db.add(col)
    db.commit()
    db.refresh(col)
    return _collection_summary(col, db)


def update_collection(db: Session, collection_id: int, user_id: int, data: CollectionUpdate) -> dict:
    col = _own(db, collection_id, user_id)
    if data.name is not None:
        col.name = data.name
    if data.format is not None:
        col.format = data.format
    if data.cover_image_uri is not None:
        col.cover_image_uri = data.cover_image_uri
    col.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(col)
    return _collection_summary(col, db)


def delete_collection(db: Session, collection_id: int, user_id: int) -> None:
    col = _own(db, collection_id, user_id)
    col.is_active = 0
    db.commit()


def add_card(db: Session, collection_id: int, user_id: int, data: CollectionCardAdd) -> dict:
    col = _own(db, collection_id, user_id)

    card = db.query(Card).filter(Card.scryfall_id == data.scryfall_id).first()
    if not card:
        raise ValueError("Card not found")

    _check_limits(db, col, data.category, data.quantity)

    # Commander slot partnership validation
    if (col.type == CollectionType.deck and
            col.format in (DeckFormat.commander, DeckFormat.brawl) and
            data.category == CardCategory.commander):
        existing_cmds = (
            db.query(CollectionCard)
            .filter(
                CollectionCard.collection_id == collection_id,
                CollectionCard.category == CardCategory.commander,
            )
            .all()
        )
        if len(existing_cmds) >= 1:
            if not _can_partner(card):
                raise ValueError(
                    "Commander slot is full. Add a second commander only if both cards "
                    "have Partner, 'Choose a Background', 'Friends forever', or a similar "
                    "dual-commander ability."
                )
            existing_cards = [
                db.query(Card).filter(Card.id == ec.card_id).first()
                for ec in existing_cmds
            ]
            if not any(_can_partner(ec) for ec in existing_cards if ec):
                raise ValueError(
                    "Your existing commander doesn't support a partner. "
                    "Both commanders need a compatible dual-commander ability."
                )

    existing = db.query(CollectionCard).filter(
        CollectionCard.collection_id == collection_id,
        CollectionCard.card_id == card.id,
        CollectionCard.category == data.category,
    ).first()

    if existing:
        existing.quantity += data.quantity
        cc = existing
    else:
        cc = CollectionCard(
            collection_id=collection_id,
            card_id=card.id,
            quantity=data.quantity,
            category=data.category,
        )
        db.add(cc)

    # Commander always becomes the cover; otherwise use first card added
    if data.category == CardCategory.commander and card.image_uri:
        col.cover_image_uri = card.image_uri
    elif not col.cover_image_uri and card.image_uri:
        col.cover_image_uri = card.image_uri

    col.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cc)
    return _card_out(cc, card, db)


def update_card(
    db: Session, collection_id: int, user_id: int,
    collection_card_id: int, data
) -> dict:
    _own(db, collection_id, user_id)
    cc = db.query(CollectionCard).filter(
        CollectionCard.id == collection_card_id,
        CollectionCard.collection_id == collection_id,
    ).first()
    if not cc:
        raise ValueError("Card entry not found")

    if data.quantity is not None:
        cc.quantity = data.quantity
    if data.category is not None:
        cc.category = data.category

    db.commit()
    db.refresh(cc)
    card = db.query(Card).filter(Card.id == cc.card_id).first()
    return _card_out(cc, card, db)


def remove_card(db: Session, collection_id: int, user_id: int, collection_card_id: int) -> None:
    _own(db, collection_id, user_id)
    cc = db.query(CollectionCard).filter(
        CollectionCard.id == collection_card_id,
        CollectionCard.collection_id == collection_id,
    ).first()
    if not cc:
        raise ValueError("Card entry not found")
    db.delete(cc)
    db.commit()


def create_bundle_listing(
    db: Session, collection_id: int, user_id: int, data: BundleListingCreate
) -> dict:
    col = _own(db, collection_id, user_id)

    # Deactivate any previous bundle listing for this collection
    db.query(BundleListing).filter(
        BundleListing.collection_id == collection_id,
        BundleListing.is_active == 1,
    ).update({"is_active": 0})

    bundle = BundleListing(
        user_id=user_id,
        collection_id=collection_id,
        price=round(data.price, 3),
        description=data.description,
    )
    db.add(bundle)
    db.commit()
    db.refresh(bundle)
    return get_bundle_listing(db, bundle.id)


def remove_bundle_listing(db: Session, collection_id: int, user_id: int) -> None:
    _own(db, collection_id, user_id)
    db.query(BundleListing).filter(
        BundleListing.collection_id == collection_id,
        BundleListing.user_id == user_id,
        BundleListing.is_active == 1,
    ).update({"is_active": 0})
    db.commit()


def get_bundle_listing(db: Session, bundle_id: int) -> Optional[dict]:
    row = (
        db.query(BundleListing, Collection, User)
        .join(Collection, BundleListing.collection_id == Collection.id)
        .join(User, BundleListing.user_id == User.id)
        .filter(BundleListing.id == bundle_id)
        .first()
    )
    if not row:
        return None
    bundle, col, user = row
    rows = db.query(CollectionCard).filter(CollectionCard.collection_id == col.id).all()
    card_count = sum(cc.quantity for cc in rows)

    cards = (
        db.query(CollectionCard, Card)
        .join(Card, CollectionCard.card_id == Card.id)
        .filter(CollectionCard.collection_id == col.id)
        .all()
    )
    total_value = sum((_omr(card) or 0) * cc.quantity for cc, card in cards)

    return {
        "id": bundle.id,
        "collection_id": col.id,
        "collection_name": col.name,
        "collection_type": col.type,
        "price": bundle.price,
        "description": bundle.description,
        "card_count": card_count,
        "total_value_omr": round(total_value, 3) if total_value else None,
        "cover_image_uri": col.cover_image_uri,
        "seller_id": user.id,
        "seller_username": user.username,
        "seller_guild_tag": user.guild_tag,
        "created_at": bundle.created_at,
    }


def get_all_bundle_listings(db: Session, limit: int = 20, offset: int = 0) -> tuple[int, list[dict]]:
    q = (
        db.query(BundleListing)
        .filter(BundleListing.is_active == 1)
        .order_by(BundleListing.created_at.desc())
    )
    total = q.count()
    bundles = q.offset(offset).limit(limit).all()
    results = []
    for b in bundles:
        row = get_bundle_listing(db, b.id)
        if row:
            results.append(row)
    return total, results


def export_collection(
    db: Session, collection_id: int, user_id: int, fmt: str = "arena"
) -> str:
    col = _own(db, collection_id, user_id)
    user = db.query(User).filter(User.id == user_id).first()

    rows = (
        db.query(CollectionCard, Card)
        .join(Card, CollectionCard.card_id == Card.id)
        .filter(CollectionCard.collection_id == collection_id)
        .order_by(CollectionCard.category, CollectionCard.added_at)
        .all()
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    guild = f" [{user.guild_tag}]" if user.guild_tag else ""
    total_cards = sum(cc.quantity for cc, _ in rows)
    total_value = sum((_omr(card) or 0) * cc.quantity for cc, card in rows)

    lines = [
        f"// MagicSteam Export",
        f"// User: {user.username}{guild}",
        f"// Date: {now}",
        f'// {col.type.value.capitalize()}: "{col.name}"',
    ]
    if col.format:
        lines.append(f"// Format: {col.format.value.capitalize()}")
    lines.append(f"// Total cards: {total_cards}")
    if total_value:
        lines.append(f"// Estimated value: {total_value:.3f} OMR")
    lines.append("//")

    if fmt == "csv":
        return _export_csv(lines, rows, col)

    categories = {}
    for cc, card in rows:
        cat = cc.category.value
        categories.setdefault(cat, []).append((cc, card))

    cat_order = ["commander", "mainboard", "sideboard"]
    for cat in cat_order:
        if cat not in categories:
            continue
        entries = categories[cat]
        total_cat = sum(cc.quantity for cc, _ in entries)
        lines.append(f"// {cat.capitalize()} ({total_cat}):")
        for cc, card in entries:
            if fmt == "mtgo":
                lines.append(f"{cc.quantity} {card.name}")
            else:
                lines.append(f"{cc.quantity} {card.name} ({card.set_code.upper()}) {card.collector_number}")
        lines.append("")

    return "\n".join(lines)


def _export_csv(header_lines: list, rows, col) -> str:
    import csv, io
    buf = io.StringIO()
    comment = "\n".join(header_lines) + "\n"
    w = csv.writer(buf)
    w.writerow(["Count", "Name", "Set Name", "Set Code", "Collector Number", "Category", "Price (OMR)"])
    for cc, card in rows:
        w.writerow([
            cc.quantity,
            card.name,
            card.set_name,
            card.set_code.upper(),
            card.collector_number or "",
            cc.category.value,
            f"{_omr(card):.3f}" if _omr(card) else "",
        ])
    return comment + buf.getvalue()


def import_cards(db: Session, collection_id: int, user_id: int, text: str) -> dict:
    col = _own(db, collection_id, user_id)

    added = 0
    skipped = 0
    errors = []

    # Patterns: "4 Lightning Bolt", "4x Lightning Bolt", "4 Lightning Bolt (M10) 145"
    line_re = re.compile(
        r"^(\d+)[x ]?\s+(.+?)(?:\s+\(([A-Z0-9]{2,6})\)\s*(\S+))?$",
        re.IGNORECASE,
    )

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue

        # Section headers like "Commander:", "Sideboard:"
        if line.lower().rstrip(":") in ("commander", "mainboard", "sideboard"):
            continue

        m = line_re.match(line)
        if not m:
            errors.append(f"Could not parse: {line!r}")
            continue

        qty = int(m.group(1))
        name = m.group(2).strip()
        set_code = m.group(3)
        collector_number = m.group(4)

        card = None
        if set_code and collector_number:
            card = db.query(Card).filter(
                Card.set_code == set_code.lower(),
                Card.collector_number == collector_number,
            ).first()
        if not card:
            card = db.query(Card).filter(
                Card.name == name,
            ).order_by(Card.id.desc()).first()

        if not card:
            errors.append(f"Card not found: {name!r}")
            skipped += 1
            continue

        try:
            _check_limits(db, col, CardCategory.mainboard, qty)
            existing = db.query(CollectionCard).filter(
                CollectionCard.collection_id == collection_id,
                CollectionCard.card_id == card.id,
                CollectionCard.category == CardCategory.mainboard,
            ).first()
            if existing:
                existing.quantity += qty
            else:
                db.add(CollectionCard(
                    collection_id=collection_id,
                    card_id=card.id,
                    quantity=qty,
                    category=CardCategory.mainboard,
                ))
            if not col.cover_image_uri and card.image_uri:
                col.cover_image_uri = card.image_uri
            added += qty
        except ValueError as e:
            errors.append(str(e))
            skipped += 1

    col.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"added": added, "skipped": skipped, "errors": errors}


def get_public_profile(db: Session, username: str) -> Optional[dict]:
    from app.modules.marketplace.models import Listing
    from app.modules.catalogue.models import Card

    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None

    listings = (
        db.query(Listing, Card)
        .join(Card, Listing.card_id == Card.id)
        .filter(Listing.user_id == user.id, Listing.is_active == 1)
        .order_by(Listing.created_at.desc())
        .limit(50)
        .all()
    )
    listing_data = [
        {
            "id": l.id,
            "card_name": card.name,
            "set_name": card.set_name,
            "image_uri": card.image_uri,
            "condition": l.condition.value,
            "price": l.price,
            "quantity": l.quantity,
        }
        for l, card in listings
    ]

    bundles = (
        db.query(BundleListing, Collection)
        .join(Collection, BundleListing.collection_id == Collection.id)
        .filter(BundleListing.user_id == user.id, BundleListing.is_active == 1)
        .order_by(BundleListing.created_at.desc())
        .limit(10)
        .all()
    )
    bundle_data = []
    for b, col in bundles:
        cards = db.query(CollectionCard).filter(CollectionCard.collection_id == col.id).all()
        bundle_data.append({
            "id": b.id,
            "collection_id": col.id,
            "name": col.name,
            "type": col.type.value,
            "price": b.price,
            "card_count": sum(c.quantity for c in cards),
            "cover_image_uri": col.cover_image_uri,
        })

    return {
        "id": user.id,
        "username": user.username,
        "guild_tag": user.guild_tag,
        "member_since": user.created_at,
        "listings": listing_data,
        "bundles": bundle_data,
        "listing_count": len(listing_data),
        "bundle_count": len(bundle_data),
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _own(db: Session, collection_id: int, user_id: int) -> Collection:
    col = db.query(Collection).filter(
        Collection.id == collection_id,
        Collection.user_id == user_id,
        Collection.is_active == 1,
    ).first()
    if not col:
        raise ValueError("Collection not found or access denied")
    return col


def _check_limits(db: Session, col: Collection, category: CardCategory, qty: int) -> None:
    if col.type == CollectionType.collection:
        total = db.query(sqlfunc.sum(CollectionCard.quantity)).filter(
            CollectionCard.collection_id == col.id
        ).scalar() or 0
        if total + qty > MAX_COLLECTION_CARDS:
            raise ValueError(f"Collection limit is {MAX_COLLECTION_CARDS} cards")
        return

    # Deck limits
    fmt_key = col.format.value if col.format else "custom"
    limits = FORMAT_LIMITS.get(fmt_key)
    if not limits:
        return

    cat_total = db.query(sqlfunc.sum(CollectionCard.quantity)).filter(
        CollectionCard.collection_id == col.id,
        CollectionCard.category == category,
    ).scalar() or 0

    cat_label = category.value
    max_for_cat = limits.get(cat_label)
    if max_for_cat is not None and cat_total + qty > max_for_cat:
        raise ValueError(
            f"{cat_label.capitalize()} limit for {fmt_key} is {max_for_cat} cards"
        )
