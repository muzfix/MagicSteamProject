"""
Stripe integration — supports Apple Pay and Samsung Pay via Payment Request Button.
Note: Stripe payouts require a business entity registered outside Oman.
If your entity is Omani, use Tap Payments instead.

Docs: https://stripe.com/docs/api
"""
# import stripe
# stripe.api_key = settings.STRIPE_SECRET_KEY


def create_payment_intent(amount_omr: float, order_id: int) -> dict:
    """
    OMR uses 3 decimal places (1 OMR = 1000 baisa).
    Stripe expects the smallest currency unit, so multiply by 1000.
    """
    if not __import__("app.config", fromlist=["settings"]).settings.STRIPE_SECRET_KEY:
        raise RuntimeError("STRIPE_SECRET_KEY not set in .env")
    raise NotImplementedError("Uncomment stripe import and implement after account setup")
