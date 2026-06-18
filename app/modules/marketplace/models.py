import enum
from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func
from app.database import Base


class Condition(str, enum.Enum):
    mint = "M"
    near_mint = "NM"
    lightly_played = "LP"
    moderately_played = "MP"
    heavily_played = "HP"
    damaged = "D"


class ListingType(str, enum.Enum):
    official = "official"
    community = "community"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    shipped = "shipped"
    completed = "completed"
    cancelled = "cancelled"


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    condition = Column(Enum(Condition), nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Integer, default=1)
    description = Column(Text)
    listing_type = Column(Enum(ListingType), default=ListingType.community)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    quantity = Column(Integer, default=1)
    total_price = Column(Float, nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.pending)
    payment_ref = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
