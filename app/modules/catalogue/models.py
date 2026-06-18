from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class MTGSet(Base):
    __tablename__ = "sets"

    id = Column(Integer, primary_key=True)
    code = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    released_at = Column(String)
    set_type = Column(String)
    card_count = Column(Integer)
    icon_svg_uri = Column(String)
    scryfall_id = Column(String, unique=True)


class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True)
    scryfall_id = Column(String, unique=True, index=True, nullable=False)
    oracle_id = Column(String(40), index=True)
    name = Column(String, index=True, nullable=False)
    set_code = Column(String(10), index=True)
    set_name = Column(String)
    collector_number = Column(String)
    mana_cost = Column(String)
    cmc = Column(Integer, index=True)          # mana value (converted mana cost)
    type_line = Column(String)
    oracle_text = Column(Text)
    rarity = Column(String, index=True)   # B-tree index: rarity.in_() goes O(N)→O(log N)
    image_uri = Column(String)
    colors = Column(JSON)
    color_identity = Column(JSON)
    legalities = Column(JSON)
    prices = Column(JSON)
    scryfall_data = Column(JSON)
    # Materialized from scryfall_data["keywords"] by scripts/optimize_db.py.
    # Avoids json_extract(scryfall_data, '$.keywords') ILIKE on every keyword
    # query — that blob parse costs 72–150 ms per filter on 90k rows.
    keywords = Column(Text)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())


class CardTranslation(Base):
    """Foreign-language card names. Populated by sync/scryfall_translations_sync.py."""
    __tablename__ = "card_translations"

    id = Column(Integer, primary_key=True)
    oracle_id = Column(String(40), index=True, nullable=False)
    lang = Column(String(10), index=True, nullable=False)
    printed_name = Column(String, index=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("oracle_id", "lang", name="uq_translation_oracle_lang"),
    )
