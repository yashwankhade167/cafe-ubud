"""
Cafe Ubud — External Services
================================
WhatsApp (via Twilio) and Razorpay payment helpers.

All calls are wrapped so the app degrades gracefully when env vars
aren't set — useful for local development without real API keys.
"""

import os
import hmac
import hashlib


# ── WHATSAPP (Twilio) ─────────────────────────────────────────────────

def _twilio_client():
    """Return a Twilio client if credentials are configured, else None."""
    try:
        from twilio.rest import Client
        sid   = os.environ.get("TWILIO_SID")
        token = os.environ.get("TWILIO_TOKEN")
        if sid and token:
            return Client(sid, token)
    except Exception:
        pass
    return None


def send_whatsapp(to_number: str, message: str) -> bool:
    """
    Send a WhatsApp message via Twilio.
    `to_number` should be in E.164 format e.g. '+919876543210'
    Returns True on success, False on failure or if not configured.
    """
    client = _twilio_client()
    if not client:
        print(f"[WhatsApp skipped — Twilio not configured] To: {to_number}\n{message}")
        return False

    from_number = os.environ.get("TWILIO_FROM", "whatsapp:+14155238886")
    try:
        client.messages.create(
            body=message,
            from_=from_number,
            to=f"whatsapp:{to_number}",
        )
        return True
    except Exception as e:
        print(f"[WhatsApp error] {e}")
        return False


def reservation_confirmation_message(reservation) -> str:
    return (
        f"🌿 *Cafe Ubud* — Reservation Confirmed!\n\n"
        f"Hello {reservation.name},\n"
        f"Your table for *{reservation.guests} guest(s)* is confirmed for "
        f"*{reservation.date}* at *{reservation.time}*.\n\n"
        f"📍 Cafe Ubud, Amravati\n"
        f"📞 +91 98765 43210\n\n"
        f"_Escape Amravati. Enter Ubud._ 🪷"
    )


def order_ready_message(order) -> str:
    items_text = ", ".join(
        f"{i.quantity}× {i.menu_item.name}" for i in order.items if i.menu_item
    )
    return (
        f"🔔 *Cafe Ubud* — Your order is ready!\n\n"
        f"Table *{order.table.number if order.table else 'Takeaway'}*\n"
        f"Order #{order.id}: {items_text}\n"
        f"Total: ₹{order.total_amount:.0f}\n\n"
        f"Enjoy your experience 🌿"
    )


# ── RAZORPAY ─────────────────────────────────────────────────────────

def razorpay_client():
    """Return a Razorpay client if credentials are configured, else None."""
    try:
        import razorpay
        key_id     = os.environ.get("RAZORPAY_KEY_ID")
        key_secret = os.environ.get("RAZORPAY_SECRET")
        if key_id and key_secret:
            return razorpay.Client(auth=(key_id, key_secret))
    except ImportError:
        pass
    return None


def create_razorpay_order(amount_inr: float, receipt: str) -> dict | None:
    """
    Create a Razorpay order for the given INR amount.
    Returns the Razorpay order dict on success, None if not configured.
    amount_inr is in rupees (e.g. 249.0) — Razorpay requires paise (×100).
    """
    client = razorpay_client()
    if not client:
        print(f"[Razorpay skipped — not configured] Amount: ₹{amount_inr}")
        return None
    try:
        return client.order.create({
            "amount": int(amount_inr * 100),   # paise
            "currency": "INR",
            "receipt": receipt,
            "payment_capture": 1,
        })
    except Exception as e:
        print(f"[Razorpay error] {e}")
        return None


def verify_razorpay_signature(razorpay_order_id: str,
                               razorpay_payment_id: str,
                               razorpay_signature: str) -> bool:
    """
    Verify the payment signature Razorpay sends after a successful payment.
    Returns True if valid, False otherwise.
    """
    secret = os.environ.get("RAZORPAY_SECRET", "")
    body = f"{razorpay_order_id}|{razorpay_payment_id}"
    expected = hmac.new(
        secret.encode(), body.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, razorpay_signature)
