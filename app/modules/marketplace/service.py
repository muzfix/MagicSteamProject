from sqlalchemy.orm import Session
from app.modules.catalogue.models import Card
from app.modules.marketplace.models import Listing, ListingType, Order
from app.modules.marketplace.schemas import ListingCreate, OrderCreate


def create_listing(db: Session, user_id: int, user_role: str, data: ListingCreate) -> Listing:
    card = db.query(Card).filter(Card.scryfall_id == data.scryfall_id).first()
    if not card:
        raise ValueError("Card not found — check the scryfall_id")

    listing_type = ListingType.official if user_role == "admin" else ListingType.community

    listing = Listing(
        user_id=user_id,
        card_id=card.id,
        condition=data.condition,
        price=data.price,
        quantity=data.quantity,
        description=data.notes,
        listing_type=listing_type,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


def get_listings(db: Session, listing_type: str = None, limit: int = 20, offset: int = 0):
    q = db.query(Listing).filter(Listing.is_active == 1)
    if listing_type:
        q = q.filter(Listing.listing_type == listing_type)
    total = q.count()
    listings = q.order_by(Listing.created_at.desc()).offset(offset).limit(limit).all()
    return total, listings


def get_listings_with_cards(db: Session, listing_type: str = None, limit: int = 20, offset: int = 0):
    from app.modules.catalogue.models import Card
    from app.modules.auth.models import User
    q = (
        db.query(Listing, Card, User)
        .join(Card, Listing.card_id == Card.id)
        .join(User, Listing.user_id == User.id)
        .filter(Listing.is_active == 1)
    )
    if listing_type:
        q = q.filter(Listing.listing_type == listing_type)
    total = q.count()
    rows = q.order_by(Listing.created_at.desc()).offset(offset).limit(limit).all()
    results = []
    for listing, card, user in rows:
        results.append({
            "id": listing.id,
            "card_name": card.name,
            "set_name": card.set_name,
            "image_uri": card.image_uri,
            "condition": listing.condition.value,
            "price": listing.price,
            "quantity": listing.quantity,
            "description": listing.description,
            "listing_type": listing.listing_type.value,
            "created_at": listing.created_at,
            "seller_username": user.username,
            "seller_guild_tag": user.guild_tag,
        })
    return total, results


def create_order(db: Session, buyer_id: int, data: OrderCreate) -> Order:
    listing = db.query(Listing).filter(Listing.id == data.listing_id).first()
    if not listing:
        raise ValueError("Listing not found")
    order = Order(
        buyer_id=buyer_id,
        seller_id=listing.user_id,
        listing_id=data.listing_id,
        quantity=data.quantity,
        total_price=listing.price * data.quantity,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order
