from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator
from app.modules.marketplace.models import Condition, ListingType, OrderStatus


class ListingCreate(BaseModel):
    scryfall_id: str          # user picks this from the visual card search
    condition: Condition
    price: float              # in OMR
    quantity: int = 1
    notes: Optional[str] = None
    # listing_type is set automatically: admin → official, everyone else → community

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Price must be greater than zero")
        return round(v, 3)


class ListingOut(BaseModel):
    id: int
    user_id: int
    card_id: int
    condition: Condition
    price: float
    quantity: int
    description: Optional[str] = None
    listing_type: ListingType
    created_at: datetime

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    listing_id: int
    quantity: int = 1


class OrderOut(BaseModel):
    id: int
    listing_id: int
    total_price: float
    status: OrderStatus
    created_at: datetime

    model_config = {"from_attributes": True}
