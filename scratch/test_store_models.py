import os
import sys
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.getcwd())

from app import create_app
from models import db
from models.store import (
    Product, Order, OrderItem, StoreCategory, StoreSubcategory,
    ProductGalleryImage, InventoryHistory, OrderStatusTimeline,
    Coupon, ProductReview
)

print("Initializing test application context for store models...")
app = create_app()

with app.app_context():
    # Wrap in a transaction block to rollback all test objects at the end
    try:
        print("\n--- Starting Model & Schema Verification ---")
        
        # 1. Create a Category and Subcategory
        print("[TEST 1] Creating StoreCategory and StoreSubcategory...")
        category = StoreCategory(
            name="Robotics Kits",
            slug="robotics-kits",
            banner_url="/static/images/robotics_banner.webp",
            icon_url="🤖",
            description="Premium robotic development kits for students.",
            seo_title="Buy Robotics Kits Online",
            seo_description="Get the best student robotics kits.",
            display_order=1
        )
        db.session.add(category)
        db.session.flush()
        print(f"  ✓ Created Category: {category.name} (ID: {category.id})")

        subcategory = StoreSubcategory(
            category_id=category.id,
            name="Arduino Obstacle Avoidance",
            slug="arduino-obstacle-avoidance",
            banner_url="/static/images/arduino_banner.webp",
            description="Arduino based robot chassis kits.",
            display_order=1
        )
        db.session.add(subcategory)
        db.session.flush()
        print(f"  ✓ Created Subcategory: {subcategory.name} (ID: {subcategory.id})")

        # 2. Register Product with specs and dynamic flags
        print("\n[TEST 2] Creating Product with dynamic CMS extensions...")
        product = Product(
            name="SOI Arduino 4WD Obstacle Robot Kit",
            slug="soi-arduino-4wd-obstacle-robot-kit",
            sku="SO-ARDU-4WD-001",
            brand="Skill Orbit",
            category=category.name,
            subcategory=subcategory.name,
            tags="arduino, robotics, starter, diy",
            price_inr=2499,
            discount_price_inr=1999,
            stock=15,
            low_stock_threshold=3,
            gst_percent=18.0,
            status="published",
            is_featured=True,
            is_trending=True,
            is_new_arrival=True,
            specifications=json.dumps([
                {"key": "Microcontroller", "value": "ATmega328P"},
                {"key": "Chassis Material", "value": "Acrylic Double Layer"},
                {"key": "Working Voltage", "value": "5V - 9V"}
            ]),
            features=json.dumps([
                "Ultrasonic obstacle avoidance sensor suite",
                "Full line follower tracker modules included",
                "Bluetooth smartphone controller companion app"
            ]),
            warranty="6 Months replacement on manufacturing defects",
            video_url="https://youtube.com/watch?v=soi_robot_kit",
            image_url="/static/uploads/products/4wd_kit.webp",
            seo_title="Official Skill Orbit India 4WD Arduino Robotics Kit",
            seo_description="Full DIY starter robotics kit with ATmega328P core.",
            seo_keywords="robotics kit, arduino robot, stem india"
        )
        db.session.add(product)
        db.session.flush()
        print(f"  ✓ Product registered successfully: {product.name} (SKU: {product.sku})")
        assert product.id is not None, "Product must be flushed with an ID"

        # 3. Associate Gallery Image
        print("\n[TEST 3] Uploading and linking product gallery images...")
        gallery_img = ProductGalleryImage(
            product_id=product.id,
            image_url="/static/uploads/products/4wd_kit_side.webp",
            display_order=1
        )
        db.session.add(gallery_img)
        db.session.flush()
        assert len(product.gallery_images) == 1, "Gallery relationship failed to link"
        print(f"  ✓ Linked gallery image: {product.gallery_images[0].image_url}")

        # 4. Log stock change history
        print("\n[TEST 4] Logging inventory history logs...")
        inv_log = InventoryHistory(
            product_id=product.id,
            quantity_changed=15,
            reason="Initial inventory load for release launch"
        )
        db.session.add(inv_log)
        db.session.flush()
        print(f"  ✓ Inventory history logged successfully: {inv_log.reason} (+{inv_log.quantity_changed})")

        # 5. Product Review Moderation and Average Recalculation
        print("\n[TEST 5] Submitting reviews and testing rating recalculation...")
        # Add a review (starts as pending)
        review1 = ProductReview(
            product_id=product.id,
            user_id=1,  # Assuming test user with ID 1 exists (typically seeded)
            rating=5,
            review_text="This is a phenomenal STEM kit. My students absolute love it!",
            status="pending"
        )
        db.session.add(review1)
        db.session.flush()
        print(f"  ✓ Submitted pending review: {review1.rating} stars (status: {review1.status})")
        
        # Verify product rating doesn't change yet (remains 4.5 baseline)
        assert product.rating == 4.5, f"Expected 4.5, got {product.rating}"
        print("  ✓ Confirmed pending review did NOT change the average rating.")
        
        # Approve review and manually trigger the recalculation logic like in the route
        review1.status = "approved"
        approved_ratings = [r.rating for r in product.reviews if r.status == "approved"]
        product.rating = round(sum(approved_ratings) / len(approved_ratings), 1)
        db.session.flush()
        assert product.rating == 5.0, f"Expected rating to update to 5.0, got {product.rating}"
        print(f"  ✓ Approved review! Product average rating successfully updated to: {product.rating} / 5")

        # 6. Coupon Discount validation
        print("\n[TEST 6] Validating coupon discount engine...")
        coupon = Coupon(
            code="ROBOTICS25",
            discount_type="percentage",
            discount_value=25,
            expiry_date=datetime.utcnow() + timedelta(days=30),
            usage_limit=100,
            usage_count=0,
            min_purchase_amount=1500,
            is_active=True,
            product_id=product.id
        )
        db.session.add(coupon)
        db.session.flush()
        print(f"  ✓ Coupon campaign active: {coupon.code} (Value: {coupon.discount_value}%)")
        
        # Validate coupon conditions
        assert coupon.expiry_date > datetime.utcnow(), "Coupon expired prematurely"
        assert coupon.min_purchase_amount <= product.price_inr, "Product price does not meet min purchase requirement"
        discount_amount = int(product.price_inr * (coupon.discount_value / 100.0))
        assert discount_amount == 624, f"Expected discount ₹624, got ₹{discount_amount}"
        print(f"  ✓ Coupon math validation successful: ₹{product.price_inr} - {coupon.discount_value}% = ₹{discount_amount} off.")

        # 7. Order creation and OrderStatusTimeline status transitions
        print("\n[TEST 7] Creating an order and testing shipment timeline logs...")
        order = Order(
            user_id=1,
            total_inr=1875,  # 2499 - 624
            payment_status="paid",
            status="Paid",
            coupon_code=coupon.code,
            discount_amount=discount_amount,
            shipping_address="Room 304, Makerspace Lab, SOI Headquarters, New Delhi",
            shipping_phone="+919876543210",
            shipping_email="maker@student.in"
        )
        db.session.add(order)
        db.session.flush()

        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=1,
            price_inr=product.price_inr
        )
        db.session.add(order_item)
        db.session.flush()
        print(f"  ✓ Created Order #{order.id} containing {order_item.quantity}x {product.name}")

        # Update order timeline status
        timeline1 = OrderStatusTimeline(
            order_id=order.id,
            status="Paid",
            notes="Payment captured. Assembly team notified."
        )
        timeline2 = OrderStatusTimeline(
            order_id=order.id,
            status="Processing",
            notes="Components selected and chassis verified under high-performance load testing."
        )
        db.session.add(timeline1)
        db.session.add(timeline2)
        db.session.flush()
        
        assert len(order.timeline_entries) == 2, "Expected 2 timeline logs"
        print(f"  ✓ Order shipping timeline logs added. Current status: {order.status}")
        for entry in order.timeline_entries:
            print(f"    - [{entry.status}] {entry.notes} (Logged: {entry.created_at})")

        print("\n--- All dynamic Store CMS model tests completed successfully! ---")
        
    except Exception as exc:
        print(f"\n❌ TEST RUN FAILED with error: {exc}")
        raise exc
    finally:
        print("\nRolling back db session transaction to preserve SQLite database state...")
        db.session.rollback()
        print("✓ Session rolled back successfully. Database remains perfectly clean.")
