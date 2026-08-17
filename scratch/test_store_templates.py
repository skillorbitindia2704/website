import os
import sys
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.getcwd())

from flask import render_template
from app import create_app
from models import db
from models.store import (
    Product, Order, OrderItem, StoreCategory, StoreSubcategory,
    ProductGalleryImage, Coupon, ProductReview
)

print("Initializing test application context for store templates...")
app = create_app()

with app.test_request_context():
    # Make sure we don't commit anything to DB
    try:
        print("\n--- Starting Template Compiling Suite ---")
        
        # 1. Prepare minimal transient data for the templates
        category = StoreCategory(
            id=999,
            name="Robotics Kits",
            slug="robotics-kits",
            banner_url="/static/images/robotics_banner.webp",
            icon_url="🤖",
            description="Premium robotic development kits."
        )
        subcategory = StoreSubcategory(
            id=999,
            category_id=category.id,
            name="Arduino Chassis",
            slug="arduino-chassis",
            description="Arduino based robot chassis kits."
        )
        product = Product(
            id=999,
            name="SOI Arduino 4WD Obstacle Robot Kit",
            slug="soi-arduino-4wd-obstacle-robot-kit",
            sku="SO-ARDU-4WD-001",
            brand="Skill Orbit",
            description="Detailed explanation of the DIY 4WD Robot chassis kit.",
            category=category.name,
            subcategory=subcategory.name,
            price_inr=2499,
            discount_price_inr=1999,
            stock=15,
            low_stock_threshold=3,
            gst_percent=18.0,
            status="published",
            specifications=json.dumps([
                {"key": "Microcontroller", "value": "ATmega328P"},
                {"key": "Chassis Material", "value": "Acrylic Double Layer"}
            ]),
            features=json.dumps([
                "Ultrasonic obstacle avoidance sensor suite",
                "Full line follower tracker modules included"
            ]),
            warranty="6 Months replacement",
            video_url="https://youtube.com/watch?v=soi_robot_kit",
            image_url="/static/uploads/products/4wd_kit.webp"
        )
        gallery_img = ProductGalleryImage(
            id=999,
            product_id=product.id,
            image_url="/static/uploads/products/4wd_kit_side.webp",
            display_order=1
        )
        product.gallery_images.append(gallery_img)
        
        review = ProductReview(
            id=999,
            product_id=product.id,
            user_id=1,
            rating=5,
            review_text="This is a phenomenal STEM kit. My students absolute love it!",
            status="approved",
            created_at=datetime.utcnow()
        )
        # Mock a backref user for the review template rendering
        from models.user import User
        mock_user = User(id=1, full_name="test_maker", email="maker@student.in")
        review.user = mock_user
        product.reviews.append(review)

        coupon = Coupon(
            id=999,
            code="ROBOTICS25",
            discount_type="percentage",
            discount_value=25,
            expiry_date=datetime.utcnow() + timedelta(days=30),
            usage_limit=100,
            usage_count=5,
            min_purchase_amount=1500,
            is_active=True,
            product_id=product.id,
            product=product
        )

        order = Order(
            id=999,
            user_id=mock_user.id,
            user=mock_user,
            total_inr=1875,
            payment_status="paid",
            status="Paid",
            coupon_code=coupon.code,
            discount_amount=624,
            shipping_address="Room 304, Makerspace Lab, SOI Headquarters, New Delhi",
            shipping_phone="+919876543210",
            shipping_email="maker@student.in",
            created_at=datetime.utcnow()
        )
        order_item = OrderItem(
            id=999,
            order_id=order.id,
            product_id=product.id,
            product=product,
            quantity=1,
            price_inr=product.price_inr
        )
        order.items.append(order_item)

        # 2. Compile Public Storefront Product Detail Page
        print("\n[TEST 1] Compiling Public Storefront Product Detail Page...")
        detail_html = render_template(
            "store/detail.html",
            product=product,
            reviews=[review],
            related_products=[product],
            specifications=[{"key": "Microcontroller", "value": "ATmega328P"}],
            features=["Ultrasonic obstacle avoidance sensor suite"],
            wishlist_ids=[]
        )
        assert "SOI Arduino 4WD Obstacle Robot" in detail_html, "Product title not rendered in detail page"
        assert "Robotics Kits" in detail_html, "Product category not rendered in detail page"
        assert "test_maker" in detail_html, "Reviewer username not rendered in detail page"
        assert "ATmega328P" in detail_html, "Specifications not rendered in detail page"
        print("  ✓ Detail page template compiled successfully (asserts passed).")

        # 3. Compile Printable A4 Invoice Layout
        print("\n[TEST 2] Compiling Printable A4 GST Invoice...")
        # Prepare invoice item breakdown details like in routes/admin.py
        gst_pct = product.gst_percent
        subtotal = order_item.price_inr * order_item.quantity
        tax_divisor = 1.0 + (gst_pct / 100.0)
        taxable_value = round(subtotal / tax_divisor, 2)
        gst_amt = round(subtotal - taxable_value, 2)
        
        invoice_items = [{
            "item": order_item,
            "taxable_value": taxable_value,
            "gst_pct": gst_pct,
            "gst_amount": gst_amt
        }]
        
        invoice_html = render_template(
            "admin/invoice.html",
            order=order,
            items=invoice_items,
            total_taxable=taxable_value,
            total_gst=gst_amt
        )
        assert "INVOICE" in invoice_html or "Invoice" in invoice_html, "Invoice header missing"
        assert "maker@student.in" in invoice_html, "Client email missing in invoice"
        assert "₹1875" in invoice_html or "1,875" in invoice_html or "1875" in invoice_html, "Net total missing in invoice"
        assert f"{gst_pct}%" in invoice_html, "GST rate breakdown missing in invoice"
        print("  ✓ GST invoice template compiled successfully (asserts passed).")

        # 4. Compile Unified Store CMS Dashboard
        print("\n[TEST 3] Compiling Store Manager CMS Dashboard...")
        # Prepare json-spec strings
        product_specs_dict = {product.id: [{"key": "Microcontroller", "value": "ATmega328P"}]}
        product_features_dict = {product.id: ["Ultrasonic obstacle avoidance sensor suite"]}
        
        cms_html = render_template(
            "admin/store_manager.html",
            products=[product],
            categories=[category],
            subcategories=[subcategory],
            coupons=[coupon],
            reviews=[review],
            orders=[order],
            total_revenue=1875,
            total_orders=1,
            active_products=1,
            low_stock_count=0,
            low_stock_items=[],
            pending_reviews_count=0,
            product_specs=product_specs_dict,
            product_features=product_features_dict
        )
        assert "Dashboard" in cms_html, "CMS Dashboard tab missing"
        assert "Products" in cms_html or "Product" in cms_html, "CMS Product catalog list missing"
        assert "Coupon" in cms_html, "CMS Coupons list missing"
        assert "ROBOTICS25" in cms_html, "Coupon campaign code not rendered"
        assert "test_maker" in cms_html, "Customer review author not rendered"
        print("  ✓ Store Manager CMS Dashboard compiled successfully (asserts passed).")

        print("\n🎉 ALL HTML TEMPLATE COMPILES VERIFIED AND 100% REGRESSION-FREE!")
        
    except Exception as exc:
        print(f"\n❌ TEMPLATE TEST RUN FAILED with error: {exc}")
        raise exc
    finally:
        db.session.rollback()
