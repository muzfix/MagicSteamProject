"""
Tap Payments integration (tap.company) — supports OmanNet, Apple Pay, Samsung Pay, Visa, Mastercard.
Requires a merchant account registered with Tap for Oman.

Docs: https://developers.tap.company/docs
"""
import hmac
import hashlib
import httpx
from app.config import settings

TAP_BASE = "https://api.tap.company/v2"


def verify_webhook(payload: bytes, signature: str) -> bool:
    expected = hmac.new(
        settings.TAP_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def create_charge(amount_omr: float, order_id: int, customer_email: str) -> dict:
    """Initiate a charge. Returns a redirect URL for the customer to complete payment."""
    if not settings.TAP_SECRET_KEY:
        raise RuntimeError("TAP_SECRET_KEY not set in .env")

    headers = {"Authorization": f"Bearer {settings.TAP_SECRET_KEY}"}
    body = {
        "amount": amount_omr,
        "currency": "OMR",
        "customer": {"email": customer_email},
        "source": {"id": "src_all"},  # src_all shows all available payment methods
        "redirect": {"url": "https://yourdomain.com/orders/confirm"},
        "reference": {"merchant": str(order_id)},
    }
    with httpx.Client() as client:
        r = client.post(f"{TAP_BASE}/charges", json=body, headers=headers)
        r.raise_for_status()
        return r.json()
