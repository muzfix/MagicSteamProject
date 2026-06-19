from sqlalchemy.orm import Session
from app.modules.catalogue.models import Card
from app.modules.auth.models import User
from app.modules.marketplace.models import Listing, ListingType, Order, OrderStatus
from app.modules.marketplace.schemas import ListingCreate, ListingUpdate, OrderCreate


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


def update_listing(db: Session, listing_id: int, user_id: int, data: ListingUpdate) -> Listing:
    listing = db.query(Listing).filter(
        Listing.id == listing_id,
        Listing.user_id == user_id,
        Listing.is_active == 1,
    ).first()
    if not listing:
        raise ValueError("Listing not found")
    if data.price is not None:
        listing.price = data.price
    if data.quantity is not None:
        listing.quantity = data.quantity
    if data.description is not None:
        listing.description = data.description
    db.commit()
    db.refresh(listing)
    return listing


def deactivate_listing(db: Session, listing_id: int, user_id: int) -> None:
    listing = db.query(Listing).filter(
        Listing.id == listing_id,
        Listing.user_id == user_id,
    ).first()
    if not listing:
        raise ValueError("Listing not found")
    listing.is_active = 0
    db.commit()


def get_listings(db: Session, listing_type: str = None, limit: int = 20, offset: int = 0):
    q = db.query(Listing).filter(Listing.is_active == 1)
    if listing_type:
        q = q.filter(Listing.listing_type == listing_type)
    total = q.count()
    listings = q.order_by(Listing.created_at.desc()).offset(offset).limit(limit).all()
    return total, listings


def get_listings_with_cards(db: Session, listing_type: str = None, limit: int = 20, offset: int = 0):
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
            "seller_id": user.id,
        })
    return total, results


def get_my_listings(db: Session, user_id: int, limit: int = 50, offset: int = 0):
    q = (
        db.query(Listing, Card)
        .join(Card, Listing.card_id == Card.id)
        .filter(Listing.user_id == user_id)
    )
    total = q.count()
    rows = q.order_by(Listing.created_at.desc()).offset(offset).limit(limit).all()
    results = []
    for listing, card in rows:
        # Count pending orders for this listing
        order_count = db.query(Order).filter(
            Order.listing_id == listing.id,
            Order.status.in_([OrderStatus.pending, OrderStatus.paid]),
        ).count()
        results.append({
            "id": listing.id,
            "card_name": card.name,
            "set_name": card.set_name,
            "image_uri": card.image_uri,
            "scryfall_id": card.scryfall_id,
            "condition": listing.condition.value,
            "price": listing.price,
            "quantity": listing.quantity,
            "description": listing.description,
            "listing_type": listing.listing_type.value,
            "is_active": listing.is_active,
            "created_at": listing.created_at,
            "pending_orders": order_count,
        })
    return total, results


def get_my_orders(db: Session, user_id: int):
    from app.modules.collections.models import BundleListing, Collection

    # As buyer
    buyer_rows = db.query(Order).filter(Order.buyer_id == user_id).order_by(Order.created_at.desc()).all()
    purchases = []
    for order in buyer_rows:
        item = _order_detail(db, order)
        item["role"] = "buyer"
        purchases.append(item)

    # As seller
    seller_rows = db.query(Order).filter(Order.seller_id == user_id).order_by(Order.created_at.desc()).all()
    sales = []
    for order in seller_rows:
        item = _order_detail(db, order)
        item["role"] = "seller"
        sales.append(item)

    return {"purchases": purchases, "sales": sales}


def _order_detail(db: Session, order: Order) -> dict:
    from app.modules.collections.models import BundleListing, Collection

    buyer = db.query(User).filter(User.id == order.buyer_id).first()
    seller = db.query(User).filter(User.id == order.seller_id).first()

    item_name = "Unknown"
    item_image = None
    item_set = None

    if order.listing_id:
        listing = db.query(Listing).filter(Listing.id == order.listing_id).first()
        if listing:
            card = db.query(Card).filter(Card.id == listing.card_id).first()
            if card:
                item_name = card.name
                item_image = card.image_uri
                item_set = card.set_name
    elif order.bundle_listing_id:
        bundle = db.query(BundleListing).filter(BundleListing.id == order.bundle_listing_id).first()
        if bundle:
            col = db.query(Collection).filter(Collection.id == bundle.collection_id).first()
            if col:
                item_name = col.name
                item_image = col.cover_image_uri
                item_set = f"{col.type.value.capitalize()} · {col.format.value.capitalize() if col.format else ''}"

    return {
        "id": order.id,
        "item_name": item_name,
        "item_image": item_image,
        "item_set": item_set,
        "total_price": order.total_price,
        "quantity": order.quantity,
        "status": order.status.value,
        "payment_method": order.payment_method or "cod",
        "pickup_location": order.pickup_location,
        "created_at": order.created_at,
        "buyer_username": buyer.username if buyer else "—",
        "seller_username": seller.username if seller else "—",
        "listing_id": order.listing_id,
        "bundle_listing_id": order.bundle_listing_id,
    }


def create_order(db: Session, buyer_id: int, data: OrderCreate) -> Order:
    from app.modules.collections.models import BundleListing

    if data.listing_id:
        listing = db.query(Listing).filter(Listing.id == data.listing_id, Listing.is_active == 1).first()
        if not listing:
            raise ValueError("Listing not found")
        seller_id = listing.user_id
        total = listing.price * data.quantity
        order = Order(
            buyer_id=buyer_id,
            seller_id=seller_id,
            listing_id=data.listing_id,
            quantity=data.quantity,
            total_price=total,
            payment_method=data.payment_method or "cod",
            pickup_location=data.pickup_location,
        )
    elif data.bundle_listing_id:
        bundle = db.query(BundleListing).filter(
            BundleListing.id == data.bundle_listing_id,
            BundleListing.is_active == 1,
        ).first()
        if not bundle:
            raise ValueError("Bundle listing not found")
        seller_id = bundle.user_id
        order = Order(
            buyer_id=buyer_id,
            seller_id=seller_id,
            bundle_listing_id=data.bundle_listing_id,
            quantity=1,
            total_price=bundle.price,
            payment_method=data.payment_method or "cod",
            pickup_location=data.pickup_location,
        )
    else:
        raise ValueError("Must provide listing_id or bundle_listing_id")

    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def confirm_cod(db: Session, order_id: int, buyer_id: int, pickup_location: str) -> Order:
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.buyer_id == buyer_id,
        Order.status == OrderStatus.pending,
    ).first()
    if not order:
        raise ValueError("Order not found or already confirmed")
    order.pickup_location = pickup_location
    order.payment_method = "cod"
    order.status = OrderStatus.paid
    db.commit()
    db.refresh(order)
    return order


def get_order(db: Session, order_id: int, user_id: int) -> dict:
    order = db.query(Order).filter(
        Order.id == order_id,
    ).first()
    if not order or (order.buyer_id != user_id and order.seller_id != user_id):
        raise ValueError("Order not found")
    return _order_detail(db, order)
