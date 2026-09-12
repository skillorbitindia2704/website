import os
import razorpay
from flask import current_app


def _get_razorpay_credentials():
    key_id = (current_app.config.get("RAZORPAY_KEY_ID") or os.getenv("RAZORPAY_KEY_ID") or "").strip()
    key_secret = (current_app.config.get("RAZORPAY_KEY_SECRET") or os.getenv("RAZORPAY_KEY_SECRET") or "").strip()
    # Keep current_app.config in sync
    if key_id and not current_app.config.get("RAZORPAY_KEY_ID"):
        current_app.config["RAZORPAY_KEY_ID"] = key_id
    if key_secret and not current_app.config.get("RAZORPAY_KEY_SECRET"):
        current_app.config["RAZORPAY_KEY_SECRET"] = key_secret
    return key_id, key_secret


def create_razorpay_order(amount_inr, receipt):
    key_id, key_secret = _get_razorpay_credentials()
    if not key_id or not key_secret:
        current_app.logger.warning("Razorpay order creation aborted: key_id or key_secret is missing.")
        return None
    try:
        client = razorpay.Client(auth=(key_id, key_secret))
        amount_paise = int(round(float(amount_inr) * 100))
        order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": str(receipt)
        })
        return order
    except Exception as exc:
        current_app.logger.error(f"Razorpay API order creation error: {exc}", exc_info=True)
        return None


def verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    key_id, key_secret = _get_razorpay_credentials()
    if not key_id or not key_secret:
        return False
    client = razorpay.Client(auth=(key_id, key_secret))
    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )
        return True
    except Exception:
        return False


def verify_razorpay_webhook_signature(body_bytes, signature, secret):
    if not secret:
        return False
    key_id, key_secret = _get_razorpay_credentials()
    if not key_id or not key_secret:
        return False
    client = razorpay.Client(auth=(key_id, key_secret))
    try:
        client.utility.verify_webhook_signature(
            body_bytes.decode('utf-8'),
            signature,
            secret
        )
        return True
    except Exception:
        return False

