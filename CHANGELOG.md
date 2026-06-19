# Changelog

All notable changes to MagicSteam are documented here.
Format: `[version] YYYY-MM-DD — summary of what changed and why.`

---

## [0.1.0] 2026-06-18 — Initial Release

### Added
- Full project scaffold: FastAPI backend with SQLAlchemy ORM and SQLite
- User authentication: registration, login, JWT tokens, bcrypt password hashing
- Username change (once-per-year cooldown) and password change endpoints
- Guild tag system with profanity filter
- Card catalogue: Scryfall bulk sync (~130MB, 100k+ cards + sets)
- Multilingual card translations sync (Arabic, Japanese, German, French, etc.)
- Natural language search parser — understands MTG slang, color names, guild names, oracle synonyms, CMC expressions, type names, and free text across card name/type/oracle/translations
- Search cache with startup warm-up for the 40 most common queries
- Double-faced card (DFC) image backfill
- Card keyword index for precise ability filtering (flying, haste, deathtouch, etc.)
- Marketplace: community and official listings, order creation
- Tap Payments integration (OMR — OmanNet, Apple Pay, Visa, Mastercard)
- Stripe integration (fallback)
- Card scanner endpoint (Phase 1 stub — accepts images, recognition in Phase 4)
- WhatsApp listing parser
- Security headers middleware: CSP, HSTS, X-Frame-Options, Referrer-Policy
- Rate limiting on auth endpoints (slowapi)
- Docker + Nginx + Gunicorn production setup
- Per-folder README documentation
- `tools/doc_checker.py` — automated documentation health checker and project archiver

### Architecture decisions
- passlib removed (incompatible with bcrypt 5.x) — bcrypt called directly
- SQLite for development; PostgreSQL for production (same ORM, no code changes)
- Search uses window-function COUNT(*) OVER() to avoid double WHERE-clause scan
- Keyword abilities routed through Scryfall JSON array (not oracle_text) to avoid false positives

---

## [Unreleased]

_Document your next changes here as you work, then move them to a versioned section on release._

