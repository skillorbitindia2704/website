import hashlib
import hmac
import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

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
        amount = Decimal(str(amount_inr))
        amount_paise = int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        if amount_paise < 100:
            current_app.logger.warning("Razorpay order creation rejected: amount must be at least 100 paise.")
            return None

        client = razorpay.Client(auth=(key_id, key_secret))
        return client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "receipt": str(receipt),
        })
    except (InvalidOperation, TypeError, ValueError):
        current_app.logger.warning("Razorpay order creation rejected: invalid amount.")
        return None
    except Exception as exc:
        if getattr(exc, "status_code", None) == 401:
            current_app.logger.error("Razorpay authentication failed. Check server-side API credentials.")
        else:
            current_app.logger.error("Razorpay API order creation error: %s", exc, exc_info=True)
        return None


def verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    _, key_secret = _get_razorpay_credentials()
    if not key_secret or not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
        return False

    message = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
    expected_signature = hmac.new(
        key_secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, str(razorpay_signature).strip())


def verify_razorpay_webhook_signature(body_bytes, signature, secret):
    if not secret or not signature:
        return False
    try:
        if isinstance(body_bytes, str):
            body_bytes = body_bytes.encode("utf-8")
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            body_bytes,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected_signature, str(signature).strip())
    except (TypeError, ValueError):
        return False
