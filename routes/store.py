import os
from datetime import datetime
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from models import db
from models.store import Order, OrderItem, Product, StorePayment, StoreTransaction, PaymentAuditLog
from models.user import User
from utils.decorators import login_required
from models.wishlist import WishlistItem
from utils.notifications import notify_user
from utils.payments import create_razorpay_order, verify_razorpay_signature, verify_razorpay_webhook_signature
from utils.security_helpers import rate_limit
from extensions import csrf

store_bp = Blueprint("store", __name__)


def _get_cart():
    return session.setdefault("cart", {})


@store_bp.get("/")
@login_required
def listing():
    q = Product.query.filter(
        or_(Product.is_deleted.is_(False), Product.is_deleted.is_(None)),
        Product.status == "published"
    )
    cat = request.args.get("category", "").strip()
    min_p = request.args.get("min_price", type=int)
    max_p = request.args.get("max_price", type=int)
    if cat:
        q = q.filter(Product.category == cat)
    if min_p is not None:
        q = q.filter(Product.price_inr >= min_p)
    if max_p is not None:
        q = q.filter(Product.price_inr <= max_p)
    products = q.order_by(Product.created_at.desc()).all()
    # Extract valid categories from products only, trim whitespace
    categories = sorted(set(
        row[0].strip() for row in db.session.query(Product.category)
        .filter(
            or_(Product.is_deleted.is_(False), Product.is_deleted.is_(None)),
            Product.status == "published"
        )
        .distinct().all() if row[0] and row[0].strip()
    ))
    wishlist_ids = []
    if current_user.is_authenticated:
        wishlist_ids = [w.product_id for w in WishlistItem.query.filter_by(user_id=current_user.id).all()]
    return render_template(
        "store/listing.html",
        products=products,
        categories=categories,
        wishlist_ids=wishlist_ids,
        filter_category=cat,
        filter_min=min_p,
        filter_max=max_p,
    )


@store_bp.post("/add-to-cart/<int:product_id>")
@login_required
def add_to_cart(product_id):
    try:
        qty = int(request.form.get("quantity", 1))
    except (TypeError, ValueError):
        qty = 1
    qty = max(1, qty)
    product = Product.query.get_or_404(product_id)
    if product.is_deleted or product.status != "published" or product.stock <= 0:
        flash(f"'{product.name}' is not available for purchase.", "warning")
        return redirect(url_for("store.listing"))
    if qty > product.stock:
        qty = product.stock
        flash(f"Only {product.stock} units of '{product.name}' were available and added to your cart.", "warning")
    cart = _get_cart()
    cart[str(product.id)] = min(product.stock, cart.get(str(product.id), 0) + qty)
    session["cart"] = cart
    session.modified = True
    flash(f"{product.name} added to cart.", "success")
    return redirect(url_for("store.listing"))


@store_bp.get("/cart")
@login_required
def view_cart():
    cart = _get_cart()
    items = []
    total = 0
    invalid_pids = []
    for pid, qty in list(cart.items()):
        product = db.session.get(Product, int(pid))
        if not product or product.is_deleted or product.status != "published":
            invalid_pids.append(pid)
            continue
        subtotal = product.price_inr * qty
        total += subtotal
        items.append({"product": product, "quantity": qty, "subtotal": subtotal})
    
    if invalid_pids:
        for pid in invalid_pids:
            cart.pop(pid, None)
        session["cart"] = cart
        session.modified = True
        flash("Removed unavailable items from your cart.", "warning")
    
    # Calculate discount from coupon session
    discount = session.get("coupon_discount", 0)
    if discount > total:
        discount = total
        session["coupon_discount"] = discount
    net_total = max(0, total - discount)
    
    return render_template(
        "store/cart.html", 
        items=items, 
        total=total, 
        discount=discount, 
        coupon_code=session.get("coupon_code", ""), 
        net_total=net_total
    )


@store_bp.post("/checkout")
@login_required
def checkout():
    cart = _get_cart()
    if not cart:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("store.listing"))
    
    # Validate all items in cart before creating order
    order_items_data = []
    total = 0
    invalid_pids = []
    for pid, qty in list(cart.items()):
        try:
            product = db.session.get(Product, int(pid))
        except (TypeError, ValueError):
            invalid_pids.append(pid)
            continue
        
        if not product or product.is_deleted or product.status != "published":
            flash(f"Product #{pid} is no longer available.", "warning")
            invalid_pids.append(pid)
            continue
        
        # Check stock availability
        if product.stock < qty:
            flash(f"Product '{product.name}' has only {product.stock} in stock (requested {qty}).", "warning")
            invalid_pids.append(pid)
            continue
        
        total += product.price_inr * qty
        order_items_data.append((product.id, qty, product.price_inr))
    
    if invalid_pids:
        for pid in invalid_pids:
            cart.pop(pid, None)
        session["cart"] = cart
        session.modified = True
        if not cart:
            flash("Removed unavailable items from your cart.", "warning")
            return redirect(url_for("store.listing"))
    
    if not order_items_data:
        flash("No valid items in cart. Please review your items.", "warning")
        return redirect(url_for("store.listing"))
    
    # Apply coupon discount if set in session
    discount = session.get("coupon_discount", 0)
    net_total = max(0, total - discount)
    
    # Create order with validated items
    try:
        order = Order(
            user_id=current_user.id,
            total_inr=net_total,
            payment_status="payment_pending",
            coupon_code=session.get("coupon_code", ""),
            discount_amount=discount
        )
        db.session.add(order)
        db.session.flush()
        
        for product_id, qty, price in order_items_data:
            db.session.add(OrderItem(order_id=order.id, product_id=product_id, quantity=qty, price_inr=price))
        
        if net_total == 0:
            order.payment_status = "paid"
            order.status = "Paid"
            if order.coupon_code:
                from models.store import Coupon
                coupon = Coupon.query.filter_by(code=order.coupon_code).first()
                if coupon:
                    coupon.usage_count += 1
            from models.store import InventoryHistory, OrderStatusTimeline
            for product_id, qty, price in order_items_data:
                product = db.session.get(Product, product_id)
                if product:
                    product.stock = max(0, product.stock - qty)
                    db.session.add(InventoryHistory(
                        product_id=product.id,
                        quantity_changed=-qty,
                        reason=f"Order #{order.id} free checkout"
                    ))
            db.session.add(OrderStatusTimeline(
                order_id=order.id,
                status="Paid",
                notes="Free order completed without payment capture."
            ))
            db.session.commit()
            session["cart"] = {}
            session.pop("coupon_code", None)
            session.pop("coupon_discount", None)
            session.modified = True
            flash("Order placed successfully.", "success")
            return redirect(url_for("dashboard.orders"))
        
        rp_order = create_razorpay_order(net_total, f"order_{order.id}")
        if rp_order:
            order.razorpay_order_id = rp_order.get("id", "")
            db.session.commit()
            return redirect(url_for("store.pay_order", order_id=order.id))
        else:
            # Fallback to simulated payment if Razorpay is not configured
            order.payment_status = "cod_simulated"
            order.status = "Paid"
            
            # Decrease stock for fallback flow
            for pid, qty in cart.items():
                p = db.session.get(Product, int(pid))
                if p:
                    p.stock = max(0, p.stock - qty)
            
                    # Add inventory history log
                    from models.store import InventoryHistory
                    db.session.add(InventoryHistory(
                        product_id=p.id,
                        quantity_changed=-qty,
                        reason=f"COD Simulated checkout order #{order.id}"
                    ))
            
            # Log status timeline
            from models.store import OrderStatusTimeline
            db.session.add(OrderStatusTimeline(
                order_id=order.id,
                status="Paid",
                notes="Order marked as paid via COD simulation checkout."
            ))
            
            current_user.points += 15
            current_user.update_badge()
            notify_user(current_user.id, f"Order #{order.id} placed — ₹{net_total}. (COD Simulated)")
            db.session.commit()
            
            # Clear cart and coupon strictly on successful capture
            session["cart"] = {}
            session.pop("coupon_code", None)
            session.pop("coupon_discount", None)
            session.modified = True
            
            flash("Order placed successfully (COD simulation).", "success")
            return redirect(url_for("dashboard.orders"))
            
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("Order creation failed. Please try again.", "danger")
        return redirect(url_for("store.listing"))


@store_bp.get("/pay/<int:order_id>")
@login_required
def pay_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for("store.listing"))
    
    if order.payment_status == "paid":
        return redirect(url_for("store.payment_success", order_id=order.id))
        
    return render_template(
        "store/payment.html",
        order=order,
        razorpay_key_id=current_app.config.get("RAZORPAY_KEY_ID", ""),
    )


@store_bp.post("/verify-payment/<int:order_id>")
@login_required
@rate_limit(limit=5, period=60)
def verify_payment(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
        
    rz_order_id = request.form.get("razorpay_order_id", "").strip()
    rz_payment_id = request.form.get("razorpay_payment_id", "").strip()
    rz_signature = request.form.get("razorpay_signature", "").strip()
    
    if not rz_order_id or not rz_payment_id or not rz_signature:
        flash("Missing payment verification details.", "danger")
        return redirect(url_for("store.pay_order", order_id=order.id))
        
    if rz_order_id != order.razorpay_order_id:
        flash("Payment order ID mismatch.", "danger")
        return redirect(url_for("store.pay_order", order_id=order.id))
        
    # Prevent duplicate capture if order is already paid
    if order.payment_status == "paid":
        db.session.add(PaymentAuditLog(
            event_type="signature_verification",
            order_id=order.id,
            payment_id=rz_payment_id,
            status="info",
            message=f"Order #{order.id} is already paid. Skipping duplicate capture.",
            payload=f"payment_id={rz_payment_id}"
        ))
        db.session.commit()
        session["cart"] = {}
        session.pop("coupon_code", None)
        session.pop("coupon_discount", None)
        session.modified = True
        flash("This payment has already been verified.", "success")
        return redirect(url_for("store.payment_success", order_id=order.id))

    # Prevent duplicate capture if the payment_id has already been recorded
    existing_payment = StorePayment.query.filter_by(payment_id=rz_payment_id).first()
    if existing_payment:
        db.session.add(PaymentAuditLog(
            event_type="signature_verification",
            order_id=order.id,
            payment_id=rz_payment_id,
            status="info",
            message=f"StorePayment record for {rz_payment_id} already exists. Marking order as paid.",
            payload=f"payment_id={rz_payment_id}"
        ))
        order.payment_status = "paid"
        order.status = "Paid"
        order.razorpay_payment_id = rz_payment_id
        db.session.commit()
        session["cart"] = {}
        session.pop("coupon_code", None)
        session.pop("coupon_discount", None)
        session.modified = True
        flash("This payment has already been verified.", "success")
        return redirect(url_for("store.payment_success", order_id=order.id))

    is_valid = verify_razorpay_signature(rz_order_id, rz_payment_id, rz_signature)
    
    try:
        if not is_valid:
            order.payment_status = "failed_signature"
            
            # Record failed payment and transaction ledger
            pay_record = StorePayment(
                order_id=order.id,
                user_id=current_user.id,
                payment_id=rz_payment_id,
                payment_status="failed_signature",
                amount=order.total_inr,
                gateway_response=f"Signature verification failed for order {order.id}"
            )
            tx_record = StoreTransaction(
                order_id=order.id,
                user_id=current_user.id,
                payment_id=rz_payment_id,
                amount=order.total_inr,
                transaction_type="purchase",
                status="failed"
            )
            audit_log = PaymentAuditLog(
                event_type="signature_verification",
                order_id=order.id,
                payment_id=rz_payment_id,
                status="error",
                message=f"Signature verification failed for order {order.id}.",
                payload=f"order_id={rz_order_id}&payment_id={rz_payment_id}&signature={rz_signature}"
            )
            db.session.add(pay_record)
            db.session.add(tx_record)
            db.session.add(audit_log)
            db.session.commit()
            
            flash("Payment verification failed. Please try again or contact support.", "danger")
            return redirect(url_for("store.pay_order", order_id=order.id))
            
        # Payment successful, finalize the order!
        order.payment_status = "paid"
        order.status = "Paid"
        order.razorpay_payment_id = rz_payment_id
        
        # Log timeline status transition
        from models.store import OrderStatusTimeline, InventoryHistory
        db.session.add(OrderStatusTimeline(
            order_id=order.id,
            status="Paid",
            notes=f"Payment verified successfully. Razorpay Payment ID: {rz_payment_id}"
        ))
        
        # Safe transactional stock deduction
        for item in order.items:
            product = db.session.get(Product, item.product_id)
            if product:
                product.stock = max(0, product.stock - item.quantity)
                
                # Log stock tracking
                db.session.add(InventoryHistory(
                    product_id=product.id,
                    quantity_changed=-item.quantity,
                    reason=f"Order checkout #{order.id} paid"
                ))
                
                # Audit stock update
                db.session.add(PaymentAuditLog(
                    event_type="stock_update",
                    order_id=order.id,
                    payment_id=rz_payment_id,
                    status="success",
                    message=f"Reduced stock for product '{product.name}' (id: {product.id}) by {item.quantity}. Remaining: {product.stock}"
                ))
                
        # Record successful payment ledger logs
        pay_record = StorePayment(
            order_id=order.id,
            user_id=current_user.id,
            payment_id=rz_payment_id,
            payment_status="captured",
            amount=order.total_inr,
            gateway_response=f"Order {order.id} paid. Signature validated successfully."
        )
        tx_record = StoreTransaction(
            order_id=order.id,
            user_id=current_user.id,
            payment_id=rz_payment_id,
            amount=order.total_inr,
            transaction_type="purchase",
            status="success"
        )
        audit_log = PaymentAuditLog(
            event_type="signature_verification",
            order_id=order.id,
            payment_id=rz_payment_id,
            status="success",
            message=f"Signature verified successfully for Order #{order.id}."
        )
        db.session.add(pay_record)
        db.session.add(tx_record)
        db.session.add(audit_log)
        
        # Update Coupon usage count if a coupon was used
        if order.coupon_code:
            from models.store import Coupon
            coupon = Coupon.query.filter_by(code=order.coupon_code).first()
            if coupon:
                coupon.usage_count += 1
        
        # Loyalty rewards
        current_user.points += 15
        current_user.update_badge()
        notify_user(current_user.id, f"Payment successful for Order #{order.id} — ₹{order.total_inr}. Shipping details will follow.")
        
        db.session.commit()
        
        # Clear cart and coupon strictly on successful payment capture
        session["cart"] = {}
        session.pop("coupon_code", None)
        session.pop("coupon_discount", None)
        session.modified = True
        
        flash("Payment completed successfully! Thank you for your purchase.", "success")
        return redirect(url_for("store.payment_success", order_id=order.id))
        
    except SQLAlchemyError as exc:
        db.session.rollback()
        flash("Could not finalize order payment. Please contact support.", "danger")
        return redirect(url_for("store.pay_order", order_id=order.id))


@store_bp.post("/webhook")
@csrf.exempt
def webhook():
    signature = request.headers.get("x-razorpay-signature", "").strip()
    secret = current_app.config.get("RAZORPAY_KEY_SECRET", "")
    webhook_secret = current_app.config.get("RAZORPAY_WEBHOOK_SECRET") or os.getenv("RAZORPAY_WEBHOOK_SECRET") or secret
    body = request.data
    
    # Audit log entry for webhook receipt
    audit_log = PaymentAuditLog(
        event_type="webhook_received",
        status="info",
        message="Webhook post received from Razorpay",
        payload=body.decode('utf-8', errors='ignore')
    )
    db.session.add(audit_log)
    db.session.commit()
    
    if not signature:
        audit_log.status = "error"
        audit_log.message = "Missing x-razorpay-signature header"
        db.session.commit()
        return jsonify({"status": "failed", "reason": "missing_signature"}), 400
        
    # Verify signature
    is_valid = False
    if webhook_secret:
        is_valid = verify_razorpay_webhook_signature(body, signature, webhook_secret)
    else:
        # Allow simulated bypass if env is development/testing
        if current_app.config.get("ENV") == "development" or os.getenv("FLASK_ENV") == "development":
            is_valid = True
            audit_log.message += " (Signature bypassed in development mode)"
            
    if not is_valid:
        audit_log.status = "error"
        audit_log.message = "Invalid webhook signature"
        db.session.commit()
        return jsonify({"status": "failed", "reason": "invalid_signature"}), 400
        
    # Parse event
    import json
    try:
        data = json.loads(body.decode('utf-8'))
        event = data.get("event")
        payload = data.get("payload", {})
    except Exception as e:
        audit_log.status = "error"
        audit_log.message = f"Failed to parse webhook JSON: {e}"
        db.session.commit()
        return jsonify({"status": "failed", "reason": "invalid_json"}), 400
        
    # Process event
    if event == "payment.captured":
        payment_entity = payload.get("payment", {}).get("entity", {})
        rp_order_id = payment_entity.get("order_id")
        rp_payment_id = payment_entity.get("id")
        amount = payment_entity.get("amount", 0) // 100
        
        if not rp_order_id or not rp_payment_id:
            audit_log.status = "error"
            audit_log.message = "Webhook payload missing order_id or payment_id"
            db.session.commit()
            return jsonify({"status": "failed", "reason": "missing_entities"}), 400
            
        # Find order
        order = Order.query.filter_by(razorpay_order_id=rp_order_id).first()
        if not order:
            audit_log.status = "warning"
            audit_log.message = f"Webhook payment captured but no matching order found for Razorpay order ID {rp_order_id}"
            db.session.commit()
            return jsonify({"status": "success", "message": "order_not_found"}), 200
            
        # Check if already paid
        if order.payment_status == "paid":
            audit_log.status = "success"
            audit_log.message = f"Order #{order.id} already paid. Webhook skipped duplicate capture."
            db.session.commit()
            return jsonify({"status": "success", "message": "already_processed"}), 200
            
        # Complete order payment asynchronously
        try:
            order.payment_status = "paid"
            order.status = "Paid"
            order.razorpay_payment_id = rp_payment_id
            
            # Log status timeline
            from models.store import OrderStatusTimeline, InventoryHistory
            db.session.add(OrderStatusTimeline(
                order_id=order.id,
                status="Paid",
                notes=f"Payment verified via async Webhook. Razorpay Payment ID: {rp_payment_id}"
            ))
            
            # Record successful payment and transaction
            pay_record = StorePayment(
                order_id=order.id,
                user_id=order.user_id,
                payment_id=rp_payment_id,
                payment_status="captured",
                amount=amount,
                gateway_response=f"Webhook verification: {event}"
            )
            tx_record = StoreTransaction(
                order_id=order.id,
                user_id=order.user_id,
                payment_id=rp_payment_id,
                amount=amount,
                transaction_type="purchase",
                status="success"
            )
            db.session.add(pay_record)
            db.session.add(tx_record)
            
            # Stock deduction if not already done
            for item in order.items:
                product = db.session.get(Product, item.product_id)
                if product:
                    product.stock = max(0, product.stock - item.quantity)
                    
                    # Log stock history
                    db.session.add(InventoryHistory(
                        product_id=product.id,
                        quantity_changed=-item.quantity,
                        reason=f"Order checkout #{order.id} paid (asynchronous webhook)"
                    ))
                    
                    # Audit stock update
                    db.session.add(PaymentAuditLog(
                        event_type="stock_update",
                        order_id=order.id,
                        payment_id=rp_payment_id,
                        status="success",
                        message=f"Webhook: Reduced stock for product '{product.name}' (id: {product.id}) by {item.quantity}. Remaining: {product.stock}"
                    ))
                    
            # Update coupon usage
            if order.coupon_code:
                from models.store import Coupon
                coupon = Coupon.query.filter_by(code=order.coupon_code).first()
                if coupon:
                    coupon.usage_count += 1
                    
            # Loyalty rewards for the user
            user = db.session.get(User, order.user_id)
            if user:
                user.points += 15
                user.update_badge()
                notify_user(user.id, f"Payment verified via Webhook for Order #{order.id} — ₹{order.total_inr}.")
                
            audit_log.status = "success"
            audit_log.order_id = order.id
            audit_log.payment_id = rp_payment_id
            audit_log.message = f"Asynchronous webhook captured payment successfully for Order #{order.id}"
            
            db.session.commit()
            
        except Exception as exc:
            db.session.rollback()
            audit_log.status = "error"
            audit_log.message = f"Database error in webhook processing: {exc}"
            db.session.commit()
            return jsonify({"status": "failed", "reason": "db_error"}), 500
            
    return jsonify({"status": "success"}), 200


@store_bp.get("/payment-success/<int:order_id>")
@login_required
def payment_success(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for("store.listing"))
        
    session.pop("coupon_code", None)
    session.pop("coupon_discount", None)
    session.modified = True
    return render_template("store/success.html", order=order)


@store_bp.get("/payment-failed/<int:order_id>")
@login_required
def payment_failed(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash("Unauthorized access.", "danger")
        return redirect(url_for("store.listing"))
        
    return render_template("store/failed.html", order=order)


# Dynamic Centralized CMS Front-end Enhancements
@store_bp.get("/product/<slug>")
@login_required
def product_detail(slug):
    # Retrieve product by slug, fallback to checking ID
    product = Product.query.filter(
        Product.slug == slug,
        or_(Product.is_deleted.is_(False), Product.is_deleted.is_(None))
    ).first()
    if not product and slug.isdigit():
        product = Product.query.filter(
            Product.id == int(slug),
            or_(Product.is_deleted.is_(False), Product.is_deleted.is_(None))
        ).first()
        
    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("store.listing"))
        
    # Get approved reviews
    approved_reviews = [r for r in product.reviews if r.status == 'approved']
    
    # Related products: products in same category (excluding current)
    related = Product.query.filter(
        Product.category == product.category,
        Product.id != product.id,
        or_(Product.is_deleted.is_(False), Product.is_deleted.is_(None)),
        Product.status == "published"
    ).limit(4).all()
    
    # Parse specifications and features from JSON strings
    import json
    try:
        specifications = json.loads(product.specifications or "[]")
    except Exception:
        specifications = []
        
    try:
        features = json.loads(product.features or "[]")
    except Exception:
        features = []
        
    wishlist_ids = []
    if current_user.is_authenticated:
        from models.wishlist import WishlistItem
        wishlist_ids = [w.product_id for w in WishlistItem.query.filter_by(user_id=current_user.id).all()]
        
    return render_template(
        "store/detail.html",
        product=product,
        reviews=approved_reviews,
        related_products=related,
        specifications=specifications,
        features=features,
        wishlist_ids=wishlist_ids
    )


@store_bp.post("/product/<int:product_id>/review")
@login_required
def post_review(product_id):
    product = Product.query.get_or_404(product_id)
    try:
        rating = int(request.form.get("rating", 5))
    except (TypeError, ValueError):
        rating = 5
        
    review_text = request.form.get("review_text", "").strip()
    
    if rating < 1 or rating > 5:
        flash("Rating must be between 1 and 5.", "danger")
        return redirect(url_for("store.product_detail", slug=product.slug or str(product.id)))
        
    from models.store import ProductReview
    review = ProductReview(
        product_id=product.id,
        user_id=current_user.id,
        rating=rating,
        review_text=review_text,
        status="pending"  # Admin must approve
    )
    db.session.add(review)
    db.session.commit()
    
    flash("Thank you! Your review has been submitted and is pending administrator approval.", "success")
    return redirect(url_for("store.product_detail", slug=product.slug or str(product.id)))


@store_bp.post("/apply-coupon")
@login_required
def apply_coupon():
    code = request.form.get("coupon_code", "").strip().upper()
    if not code:
        flash("Please enter a coupon code.", "warning")
        return redirect(url_for("store.view_cart"))
        
    from models.store import Coupon
    coupon = Coupon.query.filter_by(code=code, is_active=True).first()
    
    if not coupon:
        flash("Invalid coupon code.", "danger")
        session.pop("coupon_code", None)
        session.pop("coupon_discount", None)
        return redirect(url_for("store.view_cart"))
        
    if coupon.expiry_date < datetime.utcnow():
        flash("This coupon code has expired.", "danger")
        session.pop("coupon_code", None)
        session.pop("coupon_discount", None)
        return redirect(url_for("store.view_cart"))
        
    if coupon.usage_limit > 0 and coupon.usage_count >= coupon.usage_limit:
        flash("This coupon code usage limit has been reached.", "danger")
        session.pop("coupon_code", None)
        session.pop("coupon_discount", None)
        return redirect(url_for("store.view_cart"))
        
    # Calculate cart total and check conditions
    cart = _get_cart()
    total = 0
    product_matched = False
    for pid, qty in cart.items():
        product = db.session.get(Product, int(pid))
        if product:
            total += product.price_inr * qty
            if coupon.product_id is None or coupon.product_id == product.id:
                product_matched = True
                
    if not product_matched:
        flash("This coupon is not applicable to any products in your cart.", "warning")
        return redirect(url_for("store.view_cart"))
        
    if total < coupon.min_purchase_amount:
        flash(f"Minimum purchase amount of ₹{coupon.min_purchase_amount} required to use this coupon.", "warning")
        return redirect(url_for("store.view_cart"))
        
    # Calculate discount
    if coupon.discount_type == "percentage":
        discount = int(total * (coupon.discount_value / 100.0))
    else:
        discount = min(total, coupon.discount_value)
        
    session["coupon_code"] = coupon.code
    session["coupon_discount"] = discount
    session.modified = True
    
    flash(f"Coupon '{coupon.code}' applied! You saved ₹{discount}.", "success")
    return redirect(url_for("store.view_cart"))


