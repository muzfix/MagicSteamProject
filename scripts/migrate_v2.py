"""
Migration v2: add oracle_id to cards, guild_tag to users, create card_translations table.
Run once from the project root:  python scripts/migrate_v2.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from app.database import engine
from app.modules.catalogue.models import Base   # ensures CardTranslation is registered


def run():
    with engine.connect() as conn:

        # --- cards: add oracle_id column ---
        try:
            conn.execute(text("ALTER TABLE cards ADD COLUMN oracle_id VARCHAR(40)"))
            conn.commit()
            print("Added oracle_id column to cards.")
        except Exception:
            print("oracle_id column already exists — skipping.")

        # --- populate oracle_id from the stored scryfall_data JSON ---
        try:
            result = conn.execute(text(
                "UPDATE cards SET oracle_id = json_extract(scryfall_data, '$.oracle_id') "
                "WHERE oracle_id IS NULL"
            ))
            conn.commit()
            print(f"Populated oracle_id for {result.rowcount} cards.")
        except Exception as e:
            print(f"Could not populate oracle_id: {e}")

        # --- create index on oracle_id ---
        try:
            conn.execute(text("CREATE INDEX ix_cards_oracle_id ON cards(oracle_id)"))
            conn.commit()
            print("Created index on cards.oracle_id.")
        except Exception:
            print("Index ix_cards_oracle_id already exists — skipping.")

        # --- cards: add cmc (mana value) column ---
        try:
            conn.execute(text("ALTER TABLE cards ADD COLUMN cmc INTEGER"))
            conn.commit()
            print("Added cmc column to cards.")
        except Exception:
            print("cmc column already exists — skipping.")

        try:
            result = conn.execute(text(
                "UPDATE cards SET cmc = CAST(json_extract(scryfall_data, '$.cmc') AS INTEGER) "
                "WHERE cmc IS NULL"
            ))
            conn.commit()
            print(f"Populated cmc for {result.rowcount} cards.")
        except Exception as e:
            print(f"Could not populate cmc: {e}")

        try:
            conn.execute(text("CREATE INDEX ix_cards_cmc ON cards(cmc)"))
            conn.commit()
            print("Created index on cards.cmc.")
        except Exception:
            print("Index ix_cards_cmc already exists — skipping.")

        # --- users: add guild_tag column ---
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN guild_tag VARCHAR(4)"))
            conn.commit()
            print("Added guild_tag column to users.")
        except Exception:
            print("guild_tag column already exists — skipping.")

    # --- create card_translations table (new, so create_all handles it) ---
    Base.metadata.create_all(bind=engine)
    print("Ensured card_translations table exists.")
    print("\nMigration complete.")


if __name__ == "__main__":
    run()
