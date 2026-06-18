"""Comprehensive search system audit — run from project root."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.modules.catalogue.models import Card
from app.modules.catalogue.search_parser import _ORACLE_SYNONYMS, _TYPE_SYNONYMS
from app.modules.catalogue import service as svc
from sqlalchemy import cast, String, func, or_

db = SessionLocal()
KA = svc._KEYWORD_ABILITIES


# ── 1. Type synonym word-boundary audit ─────────────────────────────────────
print("=== TYPE SYNONYM WORD-BOUNDARY AUDIT ===")
for word, tv in sorted(_TYPE_SYNONYMS.items()):
    old_n = db.query(Card).filter(Card.type_line.ilike(f"%{tv}%")).count()
    new_n = db.query(Card).filter(
        or_(
            Card.type_line.ilike(f"% {tv} %"),
            Card.type_line.ilike(f"% {tv}"),
            Card.type_line.ilike(f"{tv} %"),
            Card.type_line.ilike(tv),
        )
    ).count()
    if old_n != new_n:
        # Find what word causes the collision
        sample = db.query(Card.type_line).filter(
            Card.type_line.ilike(f"%{tv}%"),
            ~or_(
                Card.type_line.ilike(f"% {tv} %"),
                Card.type_line.ilike(f"% {tv}"),
                Card.type_line.ilike(f"{tv} %"),
                Card.type_line.ilike(tv),
            )
        ).limit(2).all()
        print(f"  [{word}] -> [{tv}]  false_positives={old_n-new_n}  e.g.{[r[0] for r in sample]}")
print()


# ── 2. Keyword ability JSON array verification ───────────────────────────────
print("=== KEYWORD ABILITY JSON ARRAY VERIFICATION ===")
hits, misses = [], []
for ka in sorted(KA):
    proper = ka.title()
    pat = f'"{proper}"'
    jc = db.query(Card).filter(
        cast(func.json_extract(Card.scryfall_data, "$.keywords"), String).contains(pat)
    ).count()
    if jc > 0:
        hits.append((ka, jc))
    else:
        misses.append(ka)
print(f"  {len(hits)}/{len(KA)} keywords found in JSON array.")
print("  Top 12 by count:")
for ka, jc in sorted(hits, key=lambda x: -x[1])[:12]:
    print(f"    {ka:20s} {jc:6d} cards")
if misses:
    print(f"  NOT IN JSON ARRAY ({len(misses)} keywords — will fall back to oracle_text):")
    for m in misses:
        print(f"    {m}")
print()


# ── 3. Oracle synonyms that should be in _KEYWORD_ABILITIES but aren't ───────
print("=== ORACLE SYNONYMS THAT SHOULD BE IN _KEYWORD_ABILITIES ===")
candidates = []
for word, oval in sorted(_ORACLE_SYNONYMS.items()):
    if oval in KA:
        continue
    if " " in oval or not oval.isalpha() or len(oval) < 4:
        continue
    proper = oval.title()
    pat = f'"{proper}"'
    jc = db.query(Card).filter(
        cast(func.json_extract(Card.scryfall_data, "$.keywords"), String).contains(pat)
    ).count()
    tc = db.query(Card).filter(Card.oracle_text.ilike(f"%{oval}%")).count()
    if jc > 100 and tc > jc + 100:
        candidates.append((word, oval, jc, tc, tc - jc))

if candidates:
    candidates.sort(key=lambda x: -x[4])
    print("  (where JSON array is precise but oracle_text is broader)")
    for w, o, j, t, d in candidates:
        print(f"  [{w}] -> [{o}]  json={j}  oracle_text={t}  eliminated={d}")
else:
    print("  None — all oracle synonyms either already in KA or have no JSON hits.")
print()


# ── 4. Oracle synonym false positive scan (non-keyword but broad text) ───────
print("=== ORACLE SYNONYM PRECISION SCAN (non-keyword synonyms) ===")
risky = []
for word, oval in sorted(_ORACLE_SYNONYMS.items()):
    if oval in KA:
        continue
    if len(oval) < 3:
        continue
    # Count cards matching this oracle pattern
    tc = db.query(Card).filter(Card.oracle_text.ilike(f"%{oval}%")).count()
    if tc > 30000:
        risky.append((word, oval, tc))

if risky:
    risky.sort(key=lambda x: -x[2])
    print("  Very broad oracle_text matches (>30k cards — consider narrowing):")
    for w, o, t in risky:
        print(f"  [{w}] -> [{o}]  {t} cards")
else:
    print("  All oracle synonyms return <30k results — precision is acceptable.")

db.close()
print("\nAudit complete.")
