from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/webhook/tap")
async def tap_webhook(request: Request):
    """
    Tap Payments sends a POST here when a payment succeeds or fails.
    Verify the signature before trusting any data — placeholder until merchant account is active.
    """
    payload = await request.body()
    signature = request.headers.get("hashstring", "")
    # TODO: verify_tap_signature(payload, signature, settings.TAP_WEBHOOK_SECRET)
    # TODO: update order status based on payload
    return {"status": "received"}


@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Stripe webhook — also delivers Apple Pay and Samsung Pay events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    # TODO: stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    return {"status": "received"}


@router.post("/initiate/{order_id}")
async def initiate_payment(order_id: int):
    """Start a payment for an order. Activate once merchant account credentials are in .env."""
    return {
        "status": "not_implemented",
        "message": "Add TAP_SECRET_KEY or STRIPE_SECRET_KEY to .env to activate payments.",
    }
