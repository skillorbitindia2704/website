import razorpay
from flask import current_app


def create_razorpay_order(amount_inr, receipt):
    key_id = current_app.config["RAZORPAY_KEY_ID"]
    key_secret = current_app.config["RAZORPAY_KEY_SECRET"]
    if not key_id or not key_secret:
        return None
    client = razorpay.Client(auth=(key_id, key_secret))
    order = client.order.create({"amount": amount_inr * 100, "currency": "INR", "receipt": receipt})
    return order


def verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    key_id = current_app.config["RAZORPAY_KEY_ID"]
    key_secret = current_app.config["RAZORPAY_KEY_SECRET"]
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
    key_id = current_app.config["RAZORPAY_KEY_ID"]
    key_secret = current_app.config["RAZORPAY_KEY_SECRET"]
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

