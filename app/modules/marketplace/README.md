# app/modules/marketplace/

Buying and selling: card listings and order creation.

## Files

| File | Purpose |
|---|---|
| `models.py` | `Listing` and `Order` SQLAlchemy models; `ListingType` enum (official / community); `Condition` enum (NM / LP / MP / HP / Damaged) |
| `schemas.py` | Pydantic models for creating listings and orders, and for API responses |
| `service.py` | CRUD functions: `create_listing()`, `get_listings()`, `get_listings_with_cards()`, `create_order()` |
| `router.py` | FastAPI endpoints: POST /listings, GET /listings, POST /orders |

## Listing types

- **official** — created by admin users (store inventory)
- **community** — created by regular users (peer-to-peer selling)

The listing type is set automatically based on the creator's role — admins get `official`, everyone else gets `community`.

## Condition grades

NM (Near Mint) · LP (Lightly Played) · MP (Moderately Played) · HP (Heavily Played) · Damaged

## Order flow

Currently basic: `create_order()` records buyer, seller, listing, quantity, and total price. Payment integration (Tap / Stripe) is wired in the `payments` module and will link to orders in a future version.

## Filtering

`get_listings()` and `get_listings_with_cards()` both accept an optional `listing_type` filter and support limit/offset pagination.
