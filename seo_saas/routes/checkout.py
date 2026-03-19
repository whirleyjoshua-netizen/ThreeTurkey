import stripe
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from seo_saas.config import (
    STRIPE_SECRET_KEY,
    STRIPE_PUBLISHABLE_KEY,
    STRIPE_WEBHOOK_SECRET,
    STRIPE_PRICE_ID,
    BASE_URL,
)
import seo_saas.storage.database as store

stripe.api_key = STRIPE_SECRET_KEY

router = APIRouter()

MAX_SPOTS = 500


class CheckoutRequest(BaseModel):
    email: str


async def _paid_count() -> int:
    if not store.db:
        return 0
    async with store.db.execute("SELECT count(*) FROM customers") as cursor:
        row = await cursor.fetchone()
    return row[0] if row else 0


@router.post("/api/checkout")
async def create_checkout(body: CheckoutRequest):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(500, "Stripe not configured")

    if not STRIPE_PRICE_ID:
        raise HTTPException(500, "Stripe price not configured")

    paid = await _paid_count()
    if paid >= MAX_SPOTS:
        raise HTTPException(410, "All lifetime spots have been claimed")

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            customer_email=body.email,
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            success_url=f"{BASE_URL}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/#pricing",
            metadata={"email": body.email},
        )
        return {"url": session.url}
    except stripe.StripeError as e:
        raise HTTPException(500, f"Stripe error: {str(e)}")


@router.get("/api/checkout/spots")
async def spots_status():
    paid = await _paid_count()
    return {"paid": paid, "remaining": max(0, MAX_SPOTS - paid)}


@router.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, "Invalid webhook signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session.get("customer_email") or session.get("metadata", {}).get("email", "")
        customer_id = session.get("customer", "")
        session_id = session.get("id", "")
        amount = session.get("amount_total", 14900)

        if email and store.db:
            try:
                await store.db.execute(
                    """INSERT INTO customers (email, stripe_customer_id, stripe_session_id, amount_paid)
                       VALUES (?, ?, ?, ?)""",
                    (email, customer_id, session_id, amount),
                )
                await store.db.commit()
            except Exception:
                pass  # duplicate email — already recorded

    return {"ok": True}


@router.get("/checkout/success", response_class=HTMLResponse)
async def checkout_success(session_id: str = ""):
    return HTMLResponse(SUCCESS_HTML)


SUCCESS_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Welcome to Three Turkey!</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#x1F983;</text></svg>">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0f; color: #e8e8ed; min-height: 100vh; display: flex; align-items: center; justify-content: center; text-align: center; padding: 24px; }
  .card { max-width: 520px; }
  .icon { font-size: 4rem; margin-bottom: 16px; }
  h1 { font-size: 2rem; margin-bottom: 12px; background: linear-gradient(135deg, #6c5ce7, #a29bfe); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  p { color: #9898a6; font-size: 1.1rem; line-height: 1.6; margin-bottom: 24px; }
  .btn { display: inline-block; padding: 14px 32px; background: #6c5ce7; color: #fff; border: none; border-radius: 8px; font-size: 1rem; font-weight: 600; text-decoration: none; }
  .btn:hover { background: #5a4bd4; }
</style>
</head>
<body>
<div class="card">
  <div class="icon">&#x1F389;</div>
  <h1>You're a Founding Member!</h1>
  <p>Payment confirmed. You've locked in lifetime access to Three Turkey for $149. We'll email you as soon as the platform is ready to use.</p>
  <a href="/" class="btn">Back to Home</a>
</div>
</body>
</html>
"""
