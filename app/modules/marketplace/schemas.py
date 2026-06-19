from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator
from app.modules.marketplace.models import Condition, ListingType, OrderStatus


class ListingCreate(BaseModel):
    scryfall_id: str
    condition: Condition
    price: float
    quantity: int = 1
    notes: Optional[str] = None

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Price must be greater than zero")
        return round(v, 3)


class ListingUpdate(BaseModel):
    price: Optional[float] = None
    quantity: Optional[int] = None
    description: Optional[str] = None

    @field_validator("price")
    @classmethod
    def price_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Price must be greater than zero")
        return round(v, 3) if v is not None else v


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
    listing_id: Optional[int] = None
    bundle_listing_id: Optional[int] = None
    quantity: int = 1
    payment_method: str = "cod"
    pickup_location: Optional[str] = None


class CodConfirm(BaseModel):
    pickup_location: str


class OrderOut(BaseModel):
    id: int
    listing_id: Optional[int]
    bundle_listing_id: Optional[int]
    total_price: float
    status: OrderStatus
    payment_method: Optional[str]
    pickup_location: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
