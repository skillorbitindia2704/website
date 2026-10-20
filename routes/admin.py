
        return redirect(url_for("admin.store_manager"))
        
    try:
        # Calculate next display order
        max_order = db.session.query(db.func.max(StoreFeaturedProduct.display_order)).filter_by(section_id=section_id).scalar() or -1
        
        featured = StoreFeaturedProduct(
            section_id=section_id,
            product_id=product_id,
            display_order=max_order + 1,
            highlight_text=request.form.get("highlight_text", "").strip(),
            highlight_color=request.form.get("highlight_color", "#f43f5e").strip()
        )
        
        db.session.add(featured)
        db.session.commit()
        flash("Product added to featured section.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not add featured product: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/homepage/featured/<int:featured_id>/remove")
@admin_required
def store_homepage_featured_remove(featured_id):
    from models.store import StoreFeaturedProduct
    
    featured = StoreFeaturedProduct.query.get_or_404(featured_id)
    try:
        db.session.delete(featured)
        db.session.commit()
        flash("Product removed from featured section.", "info")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not remove featured product: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/homepage/banner/create")
@admin_required
def store_homepage_banner_create():
    from models.store import StoreBanner
    from datetime import datetime
    
    name = request.form.get("name", "").strip()
    placement = request.form.get("placement", "hero").strip()
    start_str = request.form.get("start_date", "")
    end_str = request.form.get("end_date", "")
    
    if not name or not start_str or not end_str:
        flash("Banner name and date range are required.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    banner_file = request.files.get("banner_image")
    if not banner_file or not banner_file.filename:
        flash("Banner image is required.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    try:
        banner_url = _upload_product_image(banner_file)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin.store_manager"))
        
    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_str, "%Y-%m-%d")
    except ValueError:
        flash("Date format must be YYYY-MM-DD.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    try:
        display_order = int(request.form.get("display_order", 0) or 0)
    except (TypeError, ValueError):
        display_order = 0
        
    banner = StoreBanner(
        name=name,
        image_url=banner_url,
        alt_text=request.form.get("alt_text", "").strip(),
        target_url=request.form.get("target_url", "/store").strip(),
        placement=placement,
        display_order=display_order,
        is_active=request.form.get("is_active") == "1",
        start_date=start_date,
        end_date=end_date
    )
    
    try:
        db.session.add(banner)
        db.session.commit()
        flash("Banner created successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not create banner: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/homepage/banner/<int:banner_id>/delete")
@admin_required
def store_homepage_banner_delete(banner_id):
    from models.store import StoreBanner
    
    banner = StoreBanner.query.get_or_404(banner_id)
    try:
        db.session.delete(banner)
        db.session.commit()
        flash("Banner deleted successfully.", "info")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not delete banner: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/homepage/offer/create")
@admin_required
def store_homepage_offer_create():
    from models.store import StorePromotionalOffer
    from datetime import datetime
    import json
    
    title = request.form.get("title", "").strip()
    offer_type = request.form.get("offer_type", "percentage").strip()
    start_str = request.form.get("start_date", "")
    end_str = request.form.get("end_date", "")
    
    if not title or not start_str or not end_str:
        flash("Offer title and date range are required.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    try:
        discount_value = int(request.form.get("discount_value", 0))
        min_purchase = int(request.form.get("min_purchase", 0) or 0)
        max_cap = int(request.form.get("max_discount_cap", 0) or 0)
    except (TypeError, ValueError):
        flash("Numerical values are invalid.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_str, "%Y-%m-%d")
    except ValueError:
        flash("Date format must be YYYY-MM-DD.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    # Handle product scope
    products_scope = request.form.get("products_scope", "all").strip()
    scope_category = ""
    scope_product_ids = "[]"
    
    if products_scope == "category":
        scope_category = request.form.get("scope_category", "").strip()
    elif products_scope == "specific":
        product_ids = request.form.getlist("scope_product_ids[]")
        scope_product_ids = json.dumps([int(p) for p in product_ids if p])
