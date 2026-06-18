from typing import Any, Optional
from pydantic import BaseModel


class SetOut(BaseModel):
    id: int
    code: str
    name: str
    released_at: Optional[str] = None
    set_type: Optional[str] = None
    card_count: Optional[int] = None

    model_config = {"from_attributes": True}


class CardOut(BaseModel):
    id: int
    scryfall_id: str
    name: str
    set_code: Optional[str] = None
    set_name: Optional[str] = None
    collector_number: Optional[str] = None
    mana_cost: Optional[str] = None
    type_line: Optional[str] = None
    oracle_text: Optional[str] = None
    rarity: Optional[str] = None
    image_uri: Optional[str] = None
    colors: Optional[list] = None
    legalities: Optional[Any] = None
    prices: Optional[Any] = None

    model_config = {"from_attributes": True}


class CardSearchResult(BaseModel):
    total: int
    cards: list[CardOut]
