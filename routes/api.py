import hashlib
import hmac
import os
from datetime import datetime

import requests
from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from flask_wtf.csrf import validate_csrf
from sqlalchemy.orm import selectinload

from models import db
from models.homepage_hero import HomePageHero
from models.notification import Notification
from models.store import Order, OrderItem, Product
from models.wishlist import WishlistItem
from utils.role_auth import get_session_user

api_bp = Blueprint("api", __name__, url_prefix="/api")
ORDER_STATUSES = {"Pending", "Accepted", "Rejected", "Shipped", "Delivered"}


@api_bp.before_request
def _csrf_for_writes():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        # Exempt standard public payment integration endpoints from strict CSRF header
        if request.endpoint in ("api.create_order", "api.verify_payment"):
            return None
        try:
            validate_csrf(request.headers.get("X-CSRFToken"))
        except Exception:
            return jsonify({"error": "Invalid or missing CSRF token"}), 403


@api_bp.get("/notifications")
@login_required
def list_notifications():
    items = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(30)
        .all()
    )
    unread = sum(1 for n in items if not n.is_read)
    return jsonify(
        {
            "notifications": [
                {"id": n.id, "message": n.message, "is_read": n.is_read, "created_at": n.created_at.isoformat()}
                for n in items
            ],
            "unread_count": unread,
        }
    )


@api_bp.post("/notifications/<int:nid>/read")
@login_required
def mark_notification_read(nid):
    n = Notification.query.filter_by(id=nid, user_id=current_user.id).first_or_404()
    n.is_read = True
    db.session.commit()
    return jsonify({"ok": True})


@api_bp.post("/wishlist/toggle")
@login_required
def wishlist_toggle():
    product_id = request.json.get("product_id") if request.is_json else None
    if not product_id:
        return jsonify({"error": "product_id required"}), 400
    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid product_id"}), 400

    # Verify product exists
    product = Product.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404

    existing = WishlistItem.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"in_wishlist": False})
    db.session.add(WishlistItem(user_id=current_user.id, product_id=product_id))
    db.session.commit()
    return jsonify({"in_wishlist": True})


@api_bp.get("/wishlist/ids")
@login_required
def wishlist_ids():
    ids = [w.product_id for w in WishlistItem.query.filter_by(user_id=current_user.id).all()]
    return jsonify({"product_ids": ids})


def _is_admin_request():
    """Check if current request is from an admin user (session + database verification)."""
    if not current_user.is_authenticated:
        return False
    user_id = current_user.id
    user = db.session.get(current_user.__class__, user_id)
    if not user:
        return False
    return user.role == "admin" or user.is_admin


@api_bp.get("/admin/orders")
def admin_list_orders():
    if not _is_admin_request():
        return jsonify({"error": "Admin access required"}), 403

    status_filter = (request.args.get("status") or "").strip()
    q = Order.query.options(
        selectinload(Order.user),
        selectinload(Order.items).selectinload(OrderItem.product),
    ).order_by(Order.created_at.desc())

    if status_filter in ORDER_STATUSES:
        q = q.filter(Order.status == status_filter)

    rows = q.limit(100).all()
    return jsonify(
        {
            "orders": [
                {
                    "id": o.id,
                    "user_name": o.user.full_name if o.user else "Unknown",
                    "products": [
                        {
                            "name": item.product.name if item.product else "Deleted product",
                            "quantity": item.quantity,
                        }
                        for item in o.items
                    ],
                    "total_inr": o.total_inr,
                    "payment_status": o.payment_status,
                    "status": o.status or "Pending",
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in rows
            ]
        }
    )


@api_bp.put("/admin/orders/<int:order_id>")
def admin_update_order(order_id):
    if not _is_admin_request():
        return jsonify({"error": "Admin access required"}), 403
    payload = request.get_json(silent=True) or {}
    new_status = (payload.get("status") or request.form.get("status") or "").strip()
    if new_status not in ORDER_STATUSES:
        return jsonify({"error": "Invalid status"}), 400
    order = Order.query.get_or_404(order_id)
    order.status = new_status
    db.session.commit()
    return jsonify({"ok": True, "order_id": order.id, "status": order.status})


@api_bp.get("/homepage-hero")
def get_homepage_hero():
    """Fetch published homepage hero content and visuals for frontend."""
    hero = HomePageHero.query.filter_by(is_published=True).first()
    if not hero:
        return jsonify({
            "error": "Homepage hero not configured",
            "data": None
        }), 404
    return jsonify(hero.to_dict()), 200


# =========================================================================
# RAZORPAY STANDARD WEB CHECKOUT ENDPOINTS
# =========================================================================

@api_bp.post("/create-order")
def create_order():
    """Create Razorpay order for Standard Checkout.

    Endpoint: POST /api/create-order
    Request JSON: { "amount": <int paise>, "currency": "INR", "receipt": "..." }
    Return JSON: { "order_id": str, "amount": int, "currency": str, "key_id": str }
    Minimum amount: 100 paise
    """
    data = request.get_json(silent=True) or request.form or {}
    raw_amount = data.get("amount")
    if raw_amount is None:
        return jsonify({"error": "amount is required"}), 400

    try:
        amount_paise = int(float(raw_amount))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400

    if amount_paise < 100:
        return jsonify({"error": "Minimum amount is 100 paise"}), 400

    currency = data.get("currency", "INR")
    receipt = str(data.get("receipt", f"rcpt_{int(datetime.now().timestamp())}"))

    key_id = (current_app.config.get("RAZORPAY_KEY_ID") or os.getenv("RAZORPAY_KEY_ID") or "").strip()
    key_secret = (current_app.config.get("RAZORPAY_KEY_SECRET") or os.getenv("RAZORPAY_KEY_SECRET") or "").strip()

    if not key_id or not key_secret:
        return jsonify({"error": "Razorpay credentials are not configured"}), 500

    try:
        response = requests.post(
            "https://api.razorpay.com/v1/orders",
            auth=(key_id, key_secret),
            json={
                "amount": amount_paise,
                "currency": currency,
                "receipt": receipt,
            },
            timeout=10,
        )
        if response.status_code == 401:
            if os.getenv("FLASK_ENV") == "development":
                import uuid
                mock_order_id = f"order_test_{uuid.uuid4().hex[:14]}"
                return jsonify({
                    "order_id": mock_order_id,
                    "amount": amount_paise,
                    "currency": currency,
                    "key_id": key_id,
                    "mock": True
                }), 200
            return jsonify({"error": "Authentication failed with Razorpay"}), 401

        if response.status_code not in (200, 201):
            current_app.logger.error("Razorpay order API error: %s %s", response.status_code, response.text)
            return jsonify({"error": "Failed to create Razorpay order", "details": response.text}), 500

        order_data = response.json()
        return jsonify({
            "order_id": order_data.get("id"),
            "amount": order_data.get("amount"),
            "currency": order_data.get("currency", "INR"),
            "key_id": key_id,
        }), 200
    except requests.RequestException as e:
        current_app.logger.error("Razorpay connection error: %s", e)
        if os.getenv("FLASK_ENV") == "development":
            import uuid
            return jsonify({
                "order_id": f"order_test_{uuid.uuid4().hex[:14]}",
                "amount": amount_paise,
                "currency": currency,
                "key_id": key_id,
                "mock": True
            }), 200
        return jsonify({"error": "Network error connecting to payment gateway"}), 500


@api_bp.post("/verify-payment")
def verify_payment():
    """Verify Razorpay payment signature.

    Endpoint: POST /api/verify-payment
    Request JSON: { "razorpay_order_id": str, "razorpay_payment_id": str, "razorpay_signature": str }
    Algorithm: HMAC-SHA256(order_id + "|" + payment_id, KEY_SECRET)
    """
    data = request.get_json(silent=True) or request.form or {}
    order_id = (data.get("razorpay_order_id") or "").strip()
    payment_id = (data.get("razorpay_payment_id") or "").strip()
    signature = (data.get("razorpay_signature") or "").strip()

    if not order_id or not payment_id or not signature:
        return jsonify({"error": "Missing required fields: razorpay_order_id, razorpay_payment_id, and razorpay_signature are required"}), 400

    key_secret = (current_app.config.get("RAZORPAY_KEY_SECRET") or os.getenv("RAZORPAY_KEY_SECRET") or "").strip()
    if not key_secret:
        return jsonify({"error": "Razorpay secret is not configured"}), 500

    # Development mode test orders
    if order_id.startswith("order_test_") and os.getenv("FLASK_ENV") == "development":
        return jsonify({
            "success": True,
            "message": "Payment verified successfully (development test mode)",
            "order_id": order_id,
            "payment_id": payment_id,
        }), 200

    message = f"{order_id}|{payment_id}".encode("utf-8")
    generated_signature = hmac.new(
        key_secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(generated_signature, signature):
        return jsonify({"success": False, "error": "Signature verification failed"}), 400

    # If order exists in Store Order table, update its status
    store_order = Order.query.filter_by(razorpay_order_id=order_id).first()
    if store_order and store_order.payment_status != "paid":
        store_order.payment_status = "paid"
        store_order.status = "Paid"
        store_order.razorpay_payment_id = payment_id
        db.session.commit()

    return jsonify({
        "success": True,
        "message": "Payment verified successfully",
        "order_id": order_id,
        "payment_id": payment_id,
    }), 200
