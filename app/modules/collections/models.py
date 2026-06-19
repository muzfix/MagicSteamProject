import enum
from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func
from app.database import Base


class CollectionType(str, enum.Enum):
    collection = "collection"
    deck = "deck"


class DeckFormat(str, enum.Enum):
    commander = "commander"
    brawl = "brawl"
    standard = "standard"
    modern = "modern"
    pioneer = "pioneer"
    legacy = "legacy"
    vintage = "vintage"
    pauper = "pauper"
    custom = "custom"


class CardCategory(str, enum.Enum):
    mainboard = "mainboard"
    sideboard = "sideboard"
    commander = "commander"


# Max mainboard / sideboard per deck format
FORMAT_LIMITS = {
    "commander": {"mainboard": 99, "sideboard": 15, "commander": 2},  # 2 for Partner/Background/Friends-forever
    "brawl":     {"mainboard": 59, "sideboard": 0,  "commander": 1},
    "standard":  {"mainboard": 60, "sideboard": 15},
    "modern":    {"mainboard": 60, "sideboard": 15},
    "pioneer":   {"mainboard": 60, "sideboard": 15},
    "legacy":    {"mainboard": 60, "sideboard": 15},
    "vintage":   {"mainboard": 60, "sideboard": 15},
    "pauper":    {"mainboard": 60, "sideboard": 15},
    "custom":    None,
}

MAX_COLLECTIONS_PER_USER = 100
MAX_COLLECTION_CARDS = 1000


class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    type = Column(Enum(CollectionType), default=CollectionType.collection)
    format = Column(Enum(DeckFormat), nullable=True)
    cover_image_uri = Column(String, nullable=True)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())


class CollectionCard(Base):
    __tablename__ = "collection_cards"

    id = Column(Integer, primary_key=True)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=False)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    quantity = Column(Integer, default=1)
    category = Column(Enum(CardCategory), default=CardCategory.mainboard)
    added_at = Column(DateTime(timezone=True), server_default=func.now())


class BundleListing(Base):
    __tablename__ = "bundle_listings"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=False)
    price = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
