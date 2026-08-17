from datetime import datetime

from models import db


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    price_inr = db.Column(db.Integer, nullable=False)
    stock = db.Column(db.Integer, default=0)
    category = db.Column(db.String(80), nullable=False, default="Electronics", index=True)
    rating = db.Column(db.Float, default=4.5)
    image_url = db.Column(db.String(255), default="/static/images/default_product.svg")
    is_deleted = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Centralized CMS Extensions
    slug = db.Column(db.String(120), unique=True, index=True, nullable=True)
    short_description = db.Column(db.Text, default="")
    sku = db.Column(db.String(100), unique=True, index=True, nullable=True)
    brand = db.Column(db.String(100), default="")
    subcategory = db.Column(db.String(80), default="")
    tags = db.Column(db.String(200), default="")
    discount_price_inr = db.Column(db.Integer, default=0)
    gst_percent = db.Column(db.Float, default=18.0)
    status = db.Column(db.String(20), default="published")
    is_featured = db.Column(db.Boolean, default=False)
    is_trending = db.Column(db.Boolean, default=False)
    is_new_arrival = db.Column(db.Boolean, default=False)
    specifications = db.Column(db.Text, default="[]")  # JSON array
    features = db.Column(db.Text, default="[]")        # JSON array
    warranty = db.Column(db.String(200), default="")
    video_url = db.Column(db.String(255), default="")
    low_stock_threshold = db.Column(db.Integer, default=5)

    # SEO metadata
    seo_title = db.Column(db.String(200), default="")
    seo_description = db.Column(db.Text, default="")
    seo_keywords = db.Column(db.String(255), default="")
    seo_canonical_url = db.Column(db.String(255), default="")
    seo_og_image = db.Column(db.String(255), default="")
    seo_schema = db.Column(db.Text, default="")

    # Core Relationships
    order_items = db.relationship("OrderItem", back_populates="product", lazy=True)
    wishlist_items = db.relationship("WishlistItem", back_populates="product", cascade="all, delete-orphan", lazy=True)
    gallery_images = db.relationship("ProductGalleryImage", back_populates="product", cascade="all, delete-orphan", lazy=True)
    reviews = db.relationship("ProductReview", back_populates="product", cascade="all, delete-orphan", lazy=True)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    total_inr = db.Column(db.Integer, nullable=False)
    payment_status = db.Column(db.String(50), default="pending")
    status = db.Column(db.String(20), nullable=False, default="Pending")
    razorpay_order_id = db.Column(db.String(100), default="")
    razorpay_payment_id = db.Column(db.String(100), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Centralized CMS Extensions
    coupon_code = db.Column(db.String(50), default="")
    discount_amount = db.Column(db.Integer, default=0)
    shipping_address = db.Column(db.Text, default="")
    shipping_phone = db.Column(db.String(20), default="")
    shipping_email = db.Column(db.String(120), default="")
    tracking_number = db.Column(db.String(100), default="")
    notes = db.Column(db.Text, default="")

    user = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete", lazy=True)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "total_inr": self.total_inr,
            "payment_status": self.payment_status,
            "status": self.status,
            "coupon_code": self.coupon_code,
            "discount_amount": self.discount_amount,
            "shipping_address": self.shipping_address,
            "shipping_phone": self.shipping_phone,
            "shipping_email": self.shipping_email,
            "tracking_number": self.tracking_number,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_inr = db.Column(db.Integer, nullable=False)

    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")


class StorePayment(db.Model):
    __tablename__ = "store_payment"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    payment_id = db.Column(db.String(100), default="")
    payment_status = db.Column(db.String(50), default="created")
    amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(10), default="INR")
    gateway_response = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    order = db.relationship("Order", backref=db.backref("payments", cascade="all, delete-orphan"))
    user = db.relationship("User", backref=db.backref("payments", cascade="all, delete-orphan"))


class StoreTransaction(db.Model):
    __tablename__ = "store_transaction"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    payment_id = db.Column(db.String(100), default="")
    amount = db.Column(db.Integer, nullable=False)
    transaction_type = db.Column(db.String(50), default="purchase")  # purchase, refund
    status = db.Column(db.String(50), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    order = db.relationship("Order", backref=db.backref("transactions", cascade="all, delete-orphan"))
    user = db.relationship("User", backref=db.backref("transactions", cascade="all, delete-orphan"))


class PaymentAuditLog(db.Model):
    __tablename__ = "payment_audit_log"
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(100), nullable=False)  # signature_verification, webhook_received, stock_update, fraud_warning
    order_id = db.Column(db.Integer, nullable=True)
    payment_id = db.Column(db.String(100), default="")
    status = db.Column(db.String(50), default="info")  # info, success, warning, error
    message = db.Column(db.Text, default="")
    payload = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# Centralized Store CMS Support Tables
class StoreCategory(db.Model):
    __tablename__ = "store_category"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    banner_url = db.Column(db.String(255), default="")
    icon_url = db.Column(db.String(255), default="")
    description = db.Column(db.Text, default="")
    seo_title = db.Column(db.String(200), default="")
    seo_description = db.Column(db.Text, default="")
    display_order = db.Column(db.Integer, default=0)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "banner_url": self.banner_url,
            "icon_url": self.icon_url,
            "description": self.description,
            "seo_title": self.seo_title,
            "seo_description": self.seo_description,
            "display_order": self.display_order,
        }


class StoreSubcategory(db.Model):
    __tablename__ = "store_subcategory"
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("store_category.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False)
    banner_url = db.Column(db.String(255), default="")
    description = db.Column(db.Text, default="")
    display_order = db.Column(db.Integer, default=0)

    category = db.relationship("StoreCategory", backref=db.backref("subcategories", cascade="all, delete-orphan", order_by="StoreSubcategory.display_order"))

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "category_id": self.category_id,
            "name": self.name,
            "slug": self.slug,
            "banner_url": self.banner_url,
            "description": self.description,
            "display_order": self.display_order,
        }


class ProductGalleryImage(db.Model):
    __tablename__ = "product_gallery_image"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    display_order = db.Column(db.Integer, default=0)

    product = db.relationship("Product", back_populates="gallery_images")


class InventoryHistory(db.Model):
    __tablename__ = "inventory_history"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity_changed = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255), nullable=False)  # restock, order, edit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship("Product")


class OrderStatusTimeline(db.Model):
    __tablename__ = "order_status_timeline"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    order = db.relationship("Order", backref=db.backref("timeline_entries", cascade="all, delete-orphan", order_by="OrderStatusTimeline.created_at"))


class Coupon(db.Model):
    __tablename__ = "coupon"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), nullable=False, unique=True, index=True)
    discount_type = db.Column(db.String(20), nullable=False, default="percentage")  # percentage, fixed
    discount_value = db.Column(db.Integer, nullable=False)
    expiry_date = db.Column(db.DateTime, nullable=False)
    usage_limit = db.Column(db.Integer, default=0)  # 0 for unlimited
    usage_count = db.Column(db.Integer, default=0)
    min_purchase_amount = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True)

    product = db.relationship("Product")

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "code": self.code,
            "discount_type": self.discount_type,
            "discount_value": self.discount_value,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "usage_limit": self.usage_limit,
            "usage_count": self.usage_count,
            "min_purchase_amount": self.min_purchase_amount,
            "is_active": bool(self.is_active),
            "product_id": self.product_id,
        }


class StoreContent(db.Model):
    __tablename__ = "store_content"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), nullable=False, unique=True)
    value = db.Column(db.Text, default="")


class ProductReview(db.Model):
    __tablename__ = "product_review"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    review_text = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="pending")  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship("Product", back_populates="reviews")
    user = db.relationship("User", backref=db.backref("reviews", cascade="all, delete-orphan"))


# ==========================================
# STORE HOMEPAGE CMS
# ==========================================

class StoreHomepageSection(db.Model):
    """Define sections/zones on store homepage for featured products"""
    __tablename__ = "store_homepage_section"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., "Top Trending", "New Arrivals"
    slug = db.Column(db.String(100), unique=True, index=True, nullable=False)
    description = db.Column(db.Text, default="")
    section_type = db.Column(db.String(50), default="featured_products")  # featured_products, category_showcase, promotional_banner
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    max_items = db.Column(db.Integer, default=8)  # Number of products to show
    banner_image_url = db.Column(db.String(255), default="")  # Optional banner for section
    banner_title = db.Column(db.String(200), default="")
    banner_subtitle = db.Column(db.String(200), default="")
    cta_button_text = db.Column(db.String(100), default="View All")
    cta_button_url = db.Column(db.String(255), default="/store")
    background_color = db.Column(db.String(20), default="#ffffff")
    text_color = db.Column(db.String(20), default="#000000")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    featured_products = db.relationship("StoreFeaturedProduct", back_populates="section", cascade="all, delete-orphan", lazy=True)


class StoreFeaturedProduct(db.Model):
    """Pin specific products to homepage sections"""
    __tablename__ = "store_featured_product"
    id = db.Column(db.Integer, primary_key=True)
    section_id = db.Column(db.Integer, db.ForeignKey("store_homepage_section.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    display_order = db.Column(db.Integer, default=0)
    highlight_text = db.Column(db.String(200), default="")  # e.g., "NEW", "BESTSELLER"
    highlight_color = db.Column(db.String(20), default="#f43f5e")  # Rose color default
    is_visible = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    section = db.relationship("StoreHomepageSection", back_populates="featured_products")
    product = db.relationship("Product", backref=db.backref("featured_in_sections", cascade="all, delete-orphan"))


class StoreBanner(db.Model):
    """Promotional banners for various store areas"""
    __tablename__ = "store_banner"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    alt_text = db.Column(db.String(200), default="")
    target_url = db.Column(db.String(255), default="/store")  # Where banner links to
    placement = db.Column(db.String(50), default="hero")  # hero, sidebar, footer, category_banner
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def is_active_now(self):
        """Check if banner is currently active (within date range)"""
        now = datetime.utcnow()
        return self.is_active and self.start_date <= now <= self.end_date


class StorePromotionalOffer(db.Model):
    """Time-limited promotional offers"""
    __tablename__ = "store_promotional_offer"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default="")
    offer_type = db.Column(db.String(50), default="percentage")  # percentage, fixed, bogo
    discount_value = db.Column(db.Integer, nullable=False)
    products_scope = db.Column(db.String(50), default="all")  # all, category, specific
    scope_category = db.Column(db.String(100), default="")  # For category-specific offers
    scope_product_ids = db.Column(db.Text, default="")  # JSON array of product IDs
    min_purchase = db.Column(db.Integer, default=0)
    max_discount_cap = db.Column(db.Integer, default=0)  # Max discount in INR (0 for no cap)
    is_active = db.Column(db.Boolean, default=True)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def is_active_now(self):
        """Check if offer is currently active"""
        now = datetime.utcnow()
        return self.is_active and self.start_date <= now <= self.end_date
