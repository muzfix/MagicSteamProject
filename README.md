# MagicSteam

A local Magic: The Gathering card marketplace for the Oman market. Sellers list physical cards; buyers browse, search, and buy — with OMR pricing, Arabic-friendly search, and Tap Payments (OmanNet, Apple Pay, Visa/Mastercard) for checkout.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.14 · FastAPI · SQLAlchemy · SQLite (dev) / PostgreSQL (prod) |
| Auth | JWT (PyJWT) · bcrypt |
| Frontend | Jinja2 templates · HTMX · Tailwind CSS |
| Payments | Tap Payments (OMR) · Stripe (fallback) |
| Card data | Scryfall bulk API (~130MB, 100k+ cards) |
| Deployment | Docker · Gunicorn · Nginx |

---

## Quick Start

```bash
# 1. Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# 2. Copy environment variables and fill in secrets
copy .env.example .env

# 3. Start the development server
uvicorn app.main:app --reload

# 4. (First run only) Populate the card database
python sync/scryfall_sync.py
```

The server runs at http://localhost:8000. API docs at http://localhost:8000/docs.

---

## Pages

| URL | Description |
|---|---|
| `/` | Homepage card search |
| `/marketplace` | Community listings + deck/collection bundles |
| `/store` | Official store (admin listings) |
| `/sell` | List individual cards for sale |
| `/my-collections` | Your collections and decks (create, manage, sell as bundle) |
| `/collections/:id` | Collection/deck detail — add cards, export, share |
| `/my-listings` | Manage your active card listings |
| `/my-orders` | Order history — purchases and sales |
| `/checkout/:order_id` | COD checkout with pickup location |
| `/u/:username` | Public seller profile |
| `/account` | Account settings |

## Collections & Decks

- **Collections**: up to 100 per user, 1 000 cards each
- **Decks**: format-aware limits (Commander 100, Standard 60+15 sideboard, etc.)
- Cards added immediately on click — no save step
- Cover art auto-set from first card; fully customisable
- **Export**: Arena/Moxfield text, MTGO text, CSV (stamped with username, guild tag, date)
- **Import**: paste any MTGO / Arena / Moxfield decklist
- **List for sale**: entire deck/collection listed as one bundle in the marketplace
- Share button: copy link or download export file

---

## Git Workflow (Keeping Up with Teammates)

```bash
# Pull the latest changes from GitHub before starting work each day
git pull

# After making changes, commit and push
git add <files>
git commit -m "describe what you changed"
git push
```

If two people edit the same file, Git will ask you to resolve the conflict before pushing. Always `git pull` first to minimize conflicts.

---

## Project Structure

```
MagicSteamProject/
├── app/                    # FastAPI application (see app/README.md)
│   ├── modules/
│   │   ├── auth/           # User accounts, JWT, login/register
│   │   ├── catalogue/      # Card search, Scryfall data, currency conversion
│   │   ├── marketplace/    # Listings, orders, COD checkout
│   │   ├── collections/    # Collections, decks, bundle listings, import/export
│   │   ├── payments/       # Tap Payments + Stripe integrations
│   │   └── scanner/        # Card image recognition (roadmap)
│   ├── static/js/          # Frontend JavaScript (HTMX-driven)
│   └── templates/          # Jinja2 HTML templates
├── sync/                   # Scryfall data sync scripts
├── scripts/                # One-off maintenance utilities
├── tests/                  # Automated test suite
├── alembic/                # Database migrations
├── tools/                  # Developer tools (doc checker, archiver)
├── docker-compose.yml      # Production container setup
├── Dockerfile
├── nginx.conf
├── gunicorn.conf.py
├── requirements.txt
└── CHANGELOG.md            # Version history — update this with every release
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | JWT signing key (generate with `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `DATABASE_URL` | `sqlite:///./mtg.db` for dev; PostgreSQL URL for prod |
| `TAP_SECRET_KEY` | Tap Payments merchant key |
| `TAP_WEBHOOK_SECRET` | Tap webhook HMAC secret |
| `STRIPE_SECRET_KEY` | Stripe fallback key (optional) |

The server refuses to start in `ENVIRONMENT=production` with a placeholder `SECRET_KEY`.

---

## Versioning

Every release is tagged in Git and logged in `CHANGELOG.md`.

```bash
# Tag a new version
git tag -a v0.2.0 -m "Add payment flow"
git push origin v0.2.0
```

Run `python tools/doc_checker.py --archive` at any time to snapshot the current project state to `D:\MagicSteamArchives\`.
