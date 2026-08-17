from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from flask_wtf.csrf import validate_csrf
from sqlalchemy.orm import selectinload

from models import db
from models.notification import Notification
from models.store import Order, OrderItem, Product
from models.wishlist import WishlistItem
from models.homepage_hero import HomePageHero
from utils.role_auth import get_session_user

api_bp = Blueprint("api", __name__, url_prefix="/api")
ORDER_STATUSES = {"Pending", "Accepted", "Rejected", "Shipped", "Delivered"}


@api_bp.before_request
def _csrf_for_writes():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
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
    # Verify admin status from database, not just session
    user_id = current_user.id
    user = db.session.get(current_user.__class__, user_id)
    if not user:
        return False
    return user.role == "admin" or user.is_admin


@api_bp.get("/products")
def list_products_api():
    q = Product.query.filter(Product.is_deleted.isnot(True))
    category = (request.args.get("category") or "").strip()
    categories_raw = (request.args.get("categories") or "").strip()
    if categories_raw:
        # Parse multiple categories, trim each one
        categories = [c.strip() for c in categories_raw.split(",") if c.strip()]
        if categories:
            q = q.filter(Product.category.in_(categories))
    elif category:
        # Single category filter with trimmed whitespace
        q = q.filter(Product.category == category)
    products = q.order_by(Product.created_at.desc()).all()
    return jsonify(
        {
            "products": [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "price_inr": p.price_inr,
                    "stock": p.stock,
                    "category": p.category,
                    "rating": p.rating,
                    "image_url": p.image_url,
                }
                for p in products
            ]
        }
    )


@api_bp.get("/admin/orders")
def admin_orders():
    if not _is_admin_request():
        return jsonify({"error": "Admin access required"}), 403
    rows = (
        Order.query.options(
            selectinload(Order.user),
            selectinload(Order.items).selectinload(OrderItem.product),
        )
        .order_by(Order.created_at.desc())
        .all()
    )
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
    """Fetch published homepage hero content and visuals for frontend.
    
    This endpoint is public and returns the latest published hero content.
    No authentication required as this is public homepage data.
    """
    hero = HomePageHero.query.filter_by(is_published=True).first()
    
    if not hero:
        # Return default/empty response if no published hero exists
        return jsonify({
            "error": "Homepage hero not configured",
            "data": None
        }), 404
    
    return jsonify(hero.to_dict()), 200
