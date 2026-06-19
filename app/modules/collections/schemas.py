from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.modules.collections.models import CardCategory, CollectionType, DeckFormat


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: CollectionType = CollectionType.collection
    format: Optional[DeckFormat] = None


class CollectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    format: Optional[DeckFormat] = None
    cover_image_uri: Optional[str] = None


class CollectionCardAdd(BaseModel):
    scryfall_id: str
    quantity: int = Field(1, ge=1, le=100)
    category: CardCategory = CardCategory.mainboard


class CollectionCardUpdate(BaseModel):
    quantity: Optional[int] = Field(None, ge=1, le=100)
    category: Optional[CardCategory] = None


class BundleListingCreate(BaseModel):
    price: float = Field(gt=0)
    description: Optional[str] = None


class CollectionCardOut(BaseModel):
    id: int
    collection_id: int
    card_id: int
    scryfall_id: str
    name: str
    set_name: str
    set_code: str
    released_at: Optional[str]
    image_uri: Optional[str]
    quantity: int
    category: CardCategory
    price_omr: Optional[float]

    model_config = {"from_attributes": True}


class CollectionOut(BaseModel):
    id: int
    user_id: int
    name: str
    type: CollectionType
    format: Optional[DeckFormat]
    cover_image_uri: Optional[str]
    card_count: int
    total_value_omr: Optional[float]
    is_listed_for_sale: bool
    bundle_listing_id: Optional[int]
    bundle_price: Optional[float]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CollectionDetailOut(CollectionOut):
    cards: list[CollectionCardOut] = []


class BundleListingOut(BaseModel):
    id: int
    collection_id: int
    collection_name: str
    collection_type: CollectionType
    price: float
    description: Optional[str]
    card_count: int
    total_value_omr: Optional[float]
    cover_image_uri: Optional[str]
    seller_id: int
    seller_username: str
    seller_guild_tag: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportResult(BaseModel):
    added: int
    skipped: int
    errors: list[str]
