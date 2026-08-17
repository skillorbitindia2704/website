# Store Product Search & Filter API Routes
# Add this to routes/store.py or create routes/store_api.py

from flask import Blueprint, request, jsonify
from models.store import Product, StoreCategory, ProductReview
from sqlalchemy import or_, and_
import json

store_api_bp = Blueprint("store_api", __name__)


@store_api_bp.route("/api/products/search", methods=["GET"])
def api_products_search():
    """
    Search products by keyword
    Query parameters:
    - q: search query (searches name, description, tags)
    - category: filter by category
    - subcategory: filter by subcategory
    - brand: filter by brand
    - sort: new, popular, price_low, price_high, rating (default: new)
    - page: pagination (default: 1)
    - per_page: items per page (default: 12)
    """
    try:
        query = request.args.get("q", "").strip()
        category = request.args.get("category", "").strip()
        subcategory = request.args.get("subcategory", "").strip()
        brand = request.args.get("brand", "").strip()
        sort = request.args.get("sort", "new").strip()
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 12))
        
        # Build query
        products = Product.query.filter(
            or_(Product.is_deleted.is_(False), Product.is_deleted.is_(None)),
            Product.status == "published"
        )
        
        # Apply filters
        if query:
            search_pattern = f"%{query}%"
            products = products.filter(
                or_(
                    Product.name.ilike(search_pattern),
                    Product.description.ilike(search_pattern),
                    Product.tags.ilike(search_pattern),
                    Product.brand.ilike(search_pattern)
                )
            )
            
        if category:
            products = products.filter_by(category=category)
            
        if subcategory:
            products = products.filter_by(subcategory=subcategory)
            
        if brand:
            products = products.filter_by(brand=brand)
            
        # Apply sorting
        if sort == "price_low":
            products = products.order_by(Product.price_inr.asc())
        elif sort == "price_high":
            products = products.order_by(Product.price_inr.desc())
        elif sort == "rating":
            products = products.order_by(Product.rating.desc())
        elif sort == "popular":
            # Order by featured, then rating
            products = products.order_by(Product.is_featured.desc(), Product.rating.desc())
        else:  # new (default)
            products = products.order_by(Product.created_at.desc())
            
        # Paginate
        paginated = products.paginate(page=page, per_page=per_page)
        
        # Format response
        items = []
        for p in paginated.items:
            items.append({
                "id": p.id,
                "name": p.name,
                "slug": p.slug,
                "price": p.price_inr,
                "discount_price": p.discount_price_inr,
                "image_url": p.image_url,
                "rating": p.rating,
                "brand": p.brand,
                "category": p.category,
                "is_featured": p.is_featured,
                "is_trending": p.is_trending,
                "is_new_arrival": p.is_new_arrival,
                "stock": p.stock,
                "in_stock": p.stock > 0
            })
            
        return jsonify({
            "success": True,
            "items": items,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": paginated.total,
                "pages": paginated.pages
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@store_api_bp.route("/api/products/<int:product_id>", methods=["GET"])
def api_product_detail(product_id):
    """Get detailed product information"""
    try:
        product = Product.query.filter(
            Product.id == product_id,
            or_(Product.is_deleted.is_(False), Product.is_deleted.is_(None)),
            Product.status == "published"
        ).first_or_404()
        
        # Get approved reviews
        reviews = ProductReview.query.filter_by(
            product_id=product_id,
            status="approved"
        ).all()
        
        review_list = []
        for r in reviews:
            review_list.append({
                "id": r.id,
                "user": r.user.username if r.user else "Anonymous",
                "rating": r.rating,
                "text": r.review_text,
                "created_at": r.created_at.isoformat()
            })
            
        return jsonify({
            "success": True,
            "product": {
                "id": product.id,
                "name": product.name,
                "slug": product.slug,
                "description": product.description,
                "short_description": product.short_description,
                "price": product.price_inr,
                "discount_price": product.discount_price_inr,
                "image_url": product.image_url,
                "gallery": [
                    {"id": g.id, "url": g.image_url, "order": g.display_order}
                    for g in product.gallery_images
                ],
                "rating": product.rating,
                "reviews_count": len(reviews),
                "brand": product.brand,
                "category": product.category,
                "subcategory": product.subcategory,
                "tags": product.tags.split(",") if product.tags else [],
                "sku": product.sku,
                "stock": product.stock,
                "in_stock": product.stock > 0,
                "low_stock": product.stock <= product.low_stock_threshold,
                "specifications": json.loads(product.specifications or "[]"),
                "features": json.loads(product.features or "[]"),
                "warranty": product.warranty,
                "video_url": product.video_url,
                "gst_percent": product.gst_percent,
                "is_featured": product.is_featured,
                "is_trending": product.is_trending,
                "is_new_arrival": product.is_new_arrival,
                "seo": {
                    "title": product.seo_title,
                    "description": product.seo_description,
                    "keywords": product.seo_keywords,
                    "canonical_url": product.seo_canonical_url,
                    "og_image": product.seo_og_image
                }
            },
            "reviews": review_list
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@store_api_bp.route("/api/products/featured", methods=["GET"])
def api_products_featured():
    """Get featured products for homepage"""
    try:
        limit = int(request.args.get("limit", 8))
        
        products = Product.query.filter(
            Product.is_featured == True,
            Product.status == "published",
            or_(Product.is_deleted.is_(False), Product.is_deleted.is_(None))
        ).order_by(Product.created_at.desc()).limit(limit).all()
        
        items = []
        for p in products:
            items.append({
                "id": p.id,
                "name": p.name,
                "slug": p.slug,
                "price": p.price_inr,
                "discount_price": p.discount_price_inr,
                "image_url": p.image_url,
                "rating": p.rating,
                "category": p.category
            })
            
        return jsonify({"success": True, "products": items})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@store_api_bp.route("/api/categories", methods=["GET"])
def api_categories():
    """Get all product categories with counts"""
    try:
        from models.store import StoreCategory
        
        categories = StoreCategory.query.order_by(
            StoreCategory.display_order.asc()
        ).all()
        
        items = []
        for c in categories:
            product_count = Product.query.filter(
                Product.category == c.name,
                Product.status == "published",
                or_(Product.is_deleted.is_(False), Product.is_deleted.is_(None))
            ).count()
            
            items.append({
                "id": c.id,
                "name": c.name,
                "slug": c.slug,
                "icon_url": c.icon_url,
                "banner_url": c.banner_url,
                "product_count": product_count
            })
            
        return jsonify({"success": True, "categories": items})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@store_api_bp.route("/api/filters", methods=["GET"])
def api_filters():
    """Get available filter options (brands, price ranges, etc.)"""
    try:
        category = request.args.get("category", "").strip()
        
        # Get all brands for available products
        query = Product.query.filter(
            Product.status == "published",
            or_(Product.is_deleted.is_(False), Product.is_deleted.is_(None))
        )
        
        if category:
            query = query.filter_by(category=category)
            
        all_products = query.all()
        
        brands = sorted(set(p.brand for p in all_products if p.brand))
        prices = sorted(set(p.price_inr for p in all_products))
        
        # Calculate price ranges
        price_ranges = [
            {"label": "Under ₹1000", "min": 0, "max": 1000},
            {"label": "₹1000 - ₹5000", "min": 1000, "max": 5000},
            {"label": "₹5000 - ₹10000", "min": 5000, "max": 10000},
            {"label": "₹10000 - ₹50000", "min": 10000, "max": 50000},
            {"label": "Above ₹50000", "min": 50000, "max": 999999}
        ]
        
        return jsonify({
            "success": True,
            "filters": {
                "brands": brands,
                "price_ranges": price_ranges,
                "min_price": min(prices) if prices else 0,
                "max_price": max(prices) if prices else 0
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@store_api_bp.route("/api/products/related/<int:product_id>", methods=["GET"])
def api_products_related(product_id):
    """Get related products based on category and tags"""
    try:
        product = Product.query.get_or_404(product_id)
        limit = int(request.args.get("limit", 4))
        
        # Find products in same category with similar tags
        related = Product.query.filter(
            Product.id != product_id,
            Product.category == product.category,
            Product.status == "published",
            or_(Product.is_deleted.is_(False), Product.is_deleted.is_(None))
        ).order_by(Product.rating.desc()).limit(limit).all()
        
        items = []
        for p in related:
            items.append({
                "id": p.id,
                "name": p.name,
                "slug": p.slug,
                "price": p.price_inr,
                "discount_price": p.discount_price_inr,
                "image_url": p.image_url,
                "rating": p.rating
            })
            
        return jsonify({"success": True, "products": items})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Register blueprint in app.py
# from routes.store_api import store_api_bp
# app.register_blueprint(store_api_bp)
