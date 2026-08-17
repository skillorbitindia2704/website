"""Add missing columns to SQLite databases created before schema updates."""

from sqlalchemy import inspect, text

from models import db


def _sync_role_from_legacy_is_admin():
    """Promote role when legacy is_admin flag is set (idempotent)."""
    with db.engine.begin() as conn:
        conn.execute(text("UPDATE user SET role = 'admin' WHERE is_admin = 1"))


def migrate_sqlite_schema(app):
    uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    if not uri.startswith("sqlite"):
        return
    with app.app_context():

        def add_col(table, col_name, ddl):
            insp = inspect(db.engine)
            if table not in insp.get_table_names():
                return
            cols = {c["name"] for c in insp.get_columns(table)}
            if col_name in cols:
                return
            # SQLite is permissive about types, but ALTER TABLE is limited.
            # Keep migrations idempotent and safe for existing data.
            try:
                with db.engine.begin() as conn:
                    conn.execute(text(ddl))
            except Exception:
                # Never crash app startup due to a best-effort schema sync.
                # If a column cannot be added (e.g. locked DB), routes may still fail
                # later; but most deployment issues are resolved by rerunning startup.
                return

        add_col("product", "category", "ALTER TABLE product ADD COLUMN category VARCHAR(80) DEFAULT 'Electronics'")
        add_col("product", "rating", "ALTER TABLE product ADD COLUMN rating FLOAT DEFAULT 4.5")
        add_col("product", "is_deleted", "ALTER TABLE product ADD COLUMN is_deleted BOOLEAN DEFAULT 0")
        add_col("order", "status", "ALTER TABLE 'order' ADD COLUMN status VARCHAR(20) DEFAULT 'Pending'")

        # Store CMS extensions
        add_col("product", "slug", "ALTER TABLE product ADD COLUMN slug VARCHAR(120)")
        add_col("product", "short_description", "ALTER TABLE product ADD COLUMN short_description TEXT DEFAULT ''")
        add_col("product", "sku", "ALTER TABLE product ADD COLUMN sku VARCHAR(100)")
        add_col("product", "brand", "ALTER TABLE product ADD COLUMN brand VARCHAR(100) DEFAULT ''")
        add_col("product", "subcategory", "ALTER TABLE product ADD COLUMN subcategory VARCHAR(80) DEFAULT ''")
        add_col("product", "tags", "ALTER TABLE product ADD COLUMN tags VARCHAR(200) DEFAULT ''")
        add_col("product", "discount_price_inr", "ALTER TABLE product ADD COLUMN discount_price_inr INTEGER DEFAULT 0")
        add_col("product", "gst_percent", "ALTER TABLE product ADD COLUMN gst_percent FLOAT DEFAULT 18.0")
        add_col("product", "status", "ALTER TABLE product ADD COLUMN status VARCHAR(20) DEFAULT 'published'")
        add_col("product", "is_featured", "ALTER TABLE product ADD COLUMN is_featured BOOLEAN DEFAULT 0")
        add_col("product", "is_trending", "ALTER TABLE product ADD COLUMN is_trending BOOLEAN DEFAULT 0")
        add_col("product", "is_new_arrival", "ALTER TABLE product ADD COLUMN is_new_arrival BOOLEAN DEFAULT 0")
        add_col("product", "specifications", "ALTER TABLE product ADD COLUMN specifications TEXT DEFAULT '[]'")
        add_col("product", "features", "ALTER TABLE product ADD COLUMN features TEXT DEFAULT '[]'")
        add_col("product", "warranty", "ALTER TABLE product ADD COLUMN warranty VARCHAR(200) DEFAULT ''")
        add_col("product", "video_url", "ALTER TABLE product ADD COLUMN video_url VARCHAR(255) DEFAULT ''")
        add_col("product", "low_stock_threshold", "ALTER TABLE product ADD COLUMN low_stock_threshold INTEGER DEFAULT 5")
        
        # Product SEO fields
        add_col("product", "seo_title", "ALTER TABLE product ADD COLUMN seo_title VARCHAR(200) DEFAULT ''")
        add_col("product", "seo_description", "ALTER TABLE product ADD COLUMN seo_description TEXT DEFAULT ''")
        add_col("product", "seo_keywords", "ALTER TABLE product ADD COLUMN seo_keywords VARCHAR(255) DEFAULT ''")
        add_col("product", "seo_canonical_url", "ALTER TABLE product ADD COLUMN seo_canonical_url VARCHAR(255) DEFAULT ''")
        add_col("product", "seo_og_image", "ALTER TABLE product ADD COLUMN seo_og_image VARCHAR(255) DEFAULT ''")
        add_col("product", "seo_schema", "ALTER TABLE product ADD COLUMN seo_schema TEXT DEFAULT ''")

        # Order table enhancements
        add_col("order", "coupon_code", "ALTER TABLE 'order' ADD COLUMN coupon_code VARCHAR(50) DEFAULT ''")
        add_col("order", "discount_amount", "ALTER TABLE 'order' ADD COLUMN discount_amount INTEGER DEFAULT 0")
        add_col("order", "shipping_address", "ALTER TABLE 'order' ADD COLUMN shipping_address TEXT DEFAULT ''")
        add_col("order", "shipping_phone", "ALTER TABLE 'order' ADD COLUMN shipping_phone VARCHAR(20) DEFAULT ''")
        add_col("order", "shipping_email", "ALTER TABLE 'order' ADD COLUMN shipping_email VARCHAR(120) DEFAULT ''")
        add_col("order", "tracking_number", "ALTER TABLE 'order' ADD COLUMN tracking_number VARCHAR(100) DEFAULT ''")
        add_col("order", "notes", "ALTER TABLE 'order' ADD COLUMN notes TEXT DEFAULT ''")
        add_col(
            "course",
            "instructor_name",
            "ALTER TABLE course ADD COLUMN instructor_name VARCHAR(120) DEFAULT 'Skill Orbit Faculty'",
        )
        add_col("course", "duration", "ALTER TABLE course ADD COLUMN duration VARCHAR(60) DEFAULT '4 weeks'")
        add_col("course", "level", "ALTER TABLE course ADD COLUMN level VARCHAR(40) DEFAULT 'Beginner'")
        add_col("course", "price_inr", "ALTER TABLE course ADD COLUMN price_inr INTEGER DEFAULT 499")
        add_col("course", "teacher_id", "ALTER TABLE course ADD COLUMN teacher_id INTEGER")
        add_col("course", "is_published", "ALTER TABLE course ADD COLUMN is_published BOOLEAN DEFAULT 1")
        add_col("course", "thumbnail_path", "ALTER TABLE course ADD COLUMN thumbnail_path VARCHAR(255) DEFAULT ''")
        add_col("course", "category", "ALTER TABLE course ADD COLUMN category VARCHAR(80) DEFAULT ''")
        add_col("course", "list_price_inr", "ALTER TABLE course ADD COLUMN list_price_inr INTEGER DEFAULT 0")
        add_col("course", "rating_avg", "ALTER TABLE course ADD COLUMN rating_avg FLOAT DEFAULT 4.8")
        add_col("course", "rating_count", "ALTER TABLE course ADD COLUMN rating_count INTEGER DEFAULT 0")
        add_col("course", "enrolled_count_display", "ALTER TABLE course ADD COLUMN enrolled_count_display INTEGER DEFAULT 0")
        add_col("course", "is_featured", "ALTER TABLE course ADD COLUMN is_featured BOOLEAN DEFAULT 0")
        add_col("course", "catalog_display_order", "ALTER TABLE course ADD COLUMN catalog_display_order INTEGER DEFAULT 0")
        add_col("course", "prerequisites", "ALTER TABLE course ADD COLUMN prerequisites TEXT DEFAULT ''")
        add_col("course", "learning_outcomes", "ALTER TABLE course ADD COLUMN learning_outcomes TEXT DEFAULT ''")
        add_col("user", "full_name", "ALTER TABLE user ADD COLUMN full_name VARCHAR(120) DEFAULT ''")
        add_col("user", "role", "ALTER TABLE user ADD COLUMN role VARCHAR(20) DEFAULT 'student'")
        add_col("user", "is_approved", "ALTER TABLE user ADD COLUMN is_approved BOOLEAN DEFAULT 0")
        add_col("user", "is_active", "ALTER TABLE user ADD COLUMN is_active BOOLEAN DEFAULT 1")
        add_col("user", "failed_login_attempts", "ALTER TABLE user ADD COLUMN failed_login_attempts INTEGER DEFAULT 0")
        add_col("user", "locked_until", "ALTER TABLE user ADD COLUMN locked_until DATETIME DEFAULT NULL")
        add_col("enrollment", "is_paid", "ALTER TABLE enrollment ADD COLUMN is_paid BOOLEAN DEFAULT 0")
        add_col("enrollment", "razorpay_order_id", "ALTER TABLE enrollment ADD COLUMN razorpay_order_id VARCHAR(100) DEFAULT ''")
        add_col("enrollment", "razorpay_payment_id", "ALTER TABLE enrollment ADD COLUMN razorpay_payment_id VARCHAR(100) DEFAULT ''")

        # About CMS enhancements
        add_col("about_timeline", "achievement_badge", "ALTER TABLE about_timeline ADD COLUMN achievement_badge VARCHAR(100) DEFAULT ''")
        add_col("about_team", "email", "ALTER TABLE about_team ADD COLUMN email VARCHAR(120) DEFAULT ''")
        add_col("about_recognition", "image_path", "ALTER TABLE about_recognition ADD COLUMN image_path VARCHAR(255) DEFAULT ''")
        add_col("about_recognition", "organization", "ALTER TABLE about_recognition ADD COLUMN organization VARCHAR(160) DEFAULT ''")
        add_col("about_recognition", "year", "ALTER TABLE about_recognition ADD COLUMN year VARCHAR(10) DEFAULT ''")

        add_col("internship", "internship_type", "ALTER TABLE internship ADD COLUMN internship_type VARCHAR(80) DEFAULT ''")
        add_col("internship", "duration", "ALTER TABLE internship ADD COLUMN duration VARCHAR(120) DEFAULT ''")
        add_col("internship", "location", "ALTER TABLE internship ADD COLUMN location VARCHAR(200) DEFAULT ''")
        add_col("internship", "requirements", "ALTER TABLE internship ADD COLUMN requirements TEXT DEFAULT ''")
        add_col("internship", "skills_needed", "ALTER TABLE internship ADD COLUMN skills_needed TEXT DEFAULT ''")
        add_col("internship", "listing_status", "ALTER TABLE internship ADD COLUMN listing_status VARCHAR(20) DEFAULT 'active'")
        add_col("internship", "is_visible", "ALTER TABLE internship ADD COLUMN is_visible BOOLEAN DEFAULT 1")
        add_col("internship", "is_featured", "ALTER TABLE internship ADD COLUMN is_featured BOOLEAN DEFAULT 0")
        add_col("internship", "is_urgent", "ALTER TABLE internship ADD COLUMN is_urgent BOOLEAN DEFAULT 0")
        add_col("internship", "is_remote", "ALTER TABLE internship ADD COLUMN is_remote BOOLEAN DEFAULT 0")
        add_col("internship", "updated_at", "ALTER TABLE internship ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")

        # Legacy HR leave_request table from old SQLite snapshots may be missing approval columns.
        add_col("leave_request", "approved_by", "ALTER TABLE leave_request ADD COLUMN approved_by INTEGER")
        add_col("leave_request", "approved_at", "ALTER TABLE leave_request ADD COLUMN approved_at DATETIME DEFAULT NULL")

        add_col("service_package", "title", "ALTER TABLE service_package ADD COLUMN title VARCHAR(140) DEFAULT ''")
        add_col("service_package", "slug", "ALTER TABLE service_package ADD COLUMN slug VARCHAR(140) DEFAULT ''")
        add_col("service_package", "short_description", "ALTER TABLE service_package ADD COLUMN short_description VARCHAR(255) DEFAULT ''")
        add_col("service_package", "full_description", "ALTER TABLE service_package ADD COLUMN full_description TEXT DEFAULT ''")
        add_col("service_package", "pricing_text", "ALTER TABLE service_package ADD COLUMN pricing_text VARCHAR(120) DEFAULT ''")
        add_col("service_package", "features", "ALTER TABLE service_package ADD COLUMN features TEXT DEFAULT ''")
        add_col("service_package", "icon", "ALTER TABLE service_package ADD COLUMN icon VARCHAR(20) DEFAULT '🔧'")
        add_col("service_package", "image", "ALTER TABLE service_package ADD COLUMN image VARCHAR(255) DEFAULT ''")
        add_col("service_package", "button_text", "ALTER TABLE service_package ADD COLUMN button_text VARCHAR(60) DEFAULT 'Request service'")
        add_col("service_package", "button_link", "ALTER TABLE service_package ADD COLUMN button_link VARCHAR(255) DEFAULT '#service-modal'")
        add_col("service_package", "category", "ALTER TABLE service_package ADD COLUMN category VARCHAR(80) DEFAULT ''")
        add_col("service_package", "badge_text", "ALTER TABLE service_package ADD COLUMN badge_text VARCHAR(80) DEFAULT ''")
        add_col("service_package", "display_order", "ALTER TABLE service_package ADD COLUMN display_order INTEGER DEFAULT 0")
        add_col("service_package", "is_active", "ALTER TABLE service_package ADD COLUMN is_active INTEGER DEFAULT 1")
        add_col("service_package", "created_at", "ALTER TABLE service_package ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
        add_col("service_package", "updated_at", "ALTER TABLE service_package ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")

        # Legacy AI Lab package columns used by production SQLite snapshots.
        add_col("ai_lab_package", "slug", "ALTER TABLE ai_lab_package ADD COLUMN slug VARCHAR(120) DEFAULT ''")
        add_col("ai_lab_package", "short_description", "ALTER TABLE ai_lab_package ADD COLUMN short_description VARCHAR(255) DEFAULT ''")
        add_col("ai_lab_package", "package_type", "ALTER TABLE ai_lab_package ADD COLUMN package_type VARCHAR(60) DEFAULT 'custom'")
        add_col("ai_lab_package", "badge", "ALTER TABLE ai_lab_package ADD COLUMN badge VARCHAR(60) DEFAULT ''")
        add_col("ai_lab_package", "is_popular", "ALTER TABLE ai_lab_package ADD COLUMN is_popular BOOLEAN DEFAULT 0")
        add_col("ai_lab_package", "is_visible", "ALTER TABLE ai_lab_package ADD COLUMN is_visible BOOLEAN DEFAULT 1")
        add_col("ai_lab_package", "cta_text", "ALTER TABLE ai_lab_package ADD COLUMN cta_text VARCHAR(60) DEFAULT 'Get started'")
        add_col("ai_lab_package", "cta_link", "ALTER TABLE ai_lab_package ADD COLUMN cta_link VARCHAR(255) DEFAULT '#inquiry'")

        # AI Lab packages: older SQLite DBs may be missing these newer columns.
        # Use DEFAULTs so legacy rows become immediately queryable.
        add_col("ai_lab_package", "subtitle", "ALTER TABLE ai_lab_package ADD COLUMN subtitle VARCHAR(200) DEFAULT ''")
        add_col("ai_lab_package", "pricing_text", "ALTER TABLE ai_lab_package ADD COLUMN pricing_text VARCHAR(100) DEFAULT ''")
        add_col("ai_lab_package", "description", "ALTER TABLE ai_lab_package ADD COLUMN description TEXT DEFAULT ''")
        add_col("ai_lab_package", "features", "ALTER TABLE ai_lab_package ADD COLUMN features TEXT DEFAULT ''")
        add_col("ai_lab_package", "button_text", "ALTER TABLE ai_lab_package ADD COLUMN button_text VARCHAR(50) DEFAULT 'Get started'")
        add_col("ai_lab_package", "button_link", "ALTER TABLE ai_lab_package ADD COLUMN button_link VARCHAR(100) DEFAULT '#inquiry'")
        add_col("ai_lab_package", "badge_text", "ALTER TABLE ai_lab_package ADD COLUMN badge_text VARCHAR(50) DEFAULT ''")
        add_col("ai_lab_package", "icon", "ALTER TABLE ai_lab_package ADD COLUMN icon VARCHAR(10) DEFAULT '🔧'")
        add_col("ai_lab_package", "display_order", "ALTER TABLE ai_lab_package ADD COLUMN display_order INTEGER DEFAULT 0")
        add_col("ai_lab_package", "is_active", "ALTER TABLE ai_lab_package ADD COLUMN is_active INTEGER DEFAULT 1")
        add_col("ai_lab_package", "created_at", "ALTER TABLE ai_lab_package ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
        add_col("ai_lab_package", "updated_at", "ALTER TABLE ai_lab_package ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")

        # Richer inquiry fields (city/lab type/budget/message) for marketing + admin CRM.
        add_col("ai_lab_inquiry", "city", "ALTER TABLE ai_lab_inquiry ADD COLUMN city VARCHAR(120) DEFAULT ''")
        add_col("ai_lab_inquiry", "lab_type", "ALTER TABLE ai_lab_inquiry ADD COLUMN lab_type VARCHAR(60) DEFAULT ''")
        add_col("ai_lab_inquiry", "budget_range", "ALTER TABLE ai_lab_inquiry ADD COLUMN budget_range VARCHAR(60) DEFAULT ''")
        add_col("ai_lab_inquiry", "message", "ALTER TABLE ai_lab_inquiry ADD COLUMN message TEXT DEFAULT ''")

        add_col("events", "mode", "ALTER TABLE events ADD COLUMN mode VARCHAR(40) DEFAULT ''")
        add_col("events", "image_path", "ALTER TABLE events ADD COLUMN image_path VARCHAR(255) DEFAULT ''")

        # Homepage dynamic content tables (created via db.create_all on new installs; migrate legacy safely).
        # For existing SQLite DBs, add missing tables by relying on SQLAlchemy create_all.
        # (No ALTER TABLE needed here because these are new tables.)

        insp = inspect(db.engine)
        if "product" in insp.get_table_names():
            with db.engine.begin() as conn:
                # Keep category populated for legacy rows.
                conn.execute(text("UPDATE product SET category = 'Electronics' WHERE category IS NULL OR TRIM(category) = ''"))
        if "course" in insp.get_table_names():
            with db.engine.begin() as conn:
                conn.execute(text("UPDATE course SET price_inr = 499 WHERE price_inr IS NULL OR price_inr < 0"))
                course_cols = {c["name"] for c in insp.get_columns("course")}
                if "is_published" in course_cols:
                    conn.execute(text("UPDATE course SET is_published = 1 WHERE is_published IS NULL"))
        if "user" in insp.get_table_names():
            with db.engine.begin() as conn:
                conn.execute(text("UPDATE user SET is_approved = 1 WHERE role = 'teacher'"))
        if "user" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("user")}
            # Legacy databases may store user name in "name" instead of "full_name".
            if "full_name" in cols and "name" in cols:
                with db.engine.begin() as conn:
                    conn.execute(text("UPDATE user SET full_name = name WHERE (full_name IS NULL OR full_name = '') AND name IS NOT NULL"))
            if "role" in cols:
                _sync_role_from_legacy_is_admin()
            with db.engine.begin() as conn:
                # Keep all core roles usable and prevent stale pending states after role updates.
                conn.execute(text("UPDATE user SET is_approved = 1 WHERE role IN ('admin', 'student', 'teacher')"))
        if "service_package" in insp.get_table_names():
            svc_cols = {c["name"] for c in insp.get_columns("service_package")}
            with db.engine.begin() as conn:
                if "title" in svc_cols:
                    conn.execute(text("UPDATE service_package SET title = '' WHERE title IS NULL"))
                if "slug" in svc_cols:
                    conn.execute(text("UPDATE service_package SET slug = ('service-' || id) WHERE slug IS NULL OR TRIM(slug) = ''"))
                if "short_description" in svc_cols:
                    conn.execute(text("UPDATE service_package SET short_description = '' WHERE short_description IS NULL"))
                if "full_description" in svc_cols:
                    conn.execute(text("UPDATE service_package SET full_description = '' WHERE full_description IS NULL"))
                if "pricing_text" in svc_cols:
                    conn.execute(text("UPDATE service_package SET pricing_text = '' WHERE pricing_text IS NULL"))
                if "features" in svc_cols:
                    conn.execute(text("UPDATE service_package SET features = '' WHERE features IS NULL"))
                if "icon" in svc_cols:
                    conn.execute(text("UPDATE service_package SET icon = '🔧' WHERE icon IS NULL OR TRIM(icon) = ''"))
                if "image" in svc_cols:
                    conn.execute(text("UPDATE service_package SET image = '' WHERE image IS NULL"))
                if "button_text" in svc_cols:
                    conn.execute(text("UPDATE service_package SET button_text = 'Request service' WHERE button_text IS NULL OR TRIM(button_text) = ''"))
                if "button_link" in svc_cols:
                    conn.execute(text("UPDATE service_package SET button_link = '#service-modal' WHERE button_link IS NULL OR TRIM(button_link) = ''"))
                if "category" in svc_cols:
                    conn.execute(text("UPDATE service_package SET category = '' WHERE category IS NULL"))
                if "badge_text" in svc_cols:
                    conn.execute(text("UPDATE service_package SET badge_text = '' WHERE badge_text IS NULL"))
                if "display_order" in svc_cols:
                    conn.execute(text("UPDATE service_package SET display_order = 0 WHERE display_order IS NULL"))
                if "is_active" in svc_cols:
                    conn.execute(text("UPDATE service_package SET is_active = 1 WHERE is_active IS NULL"))

        # Backfill AI Lab package defaults for legacy rows so templates/admin queries won't crash.
        if "ai_lab_package" in insp.get_table_names():
            pkg_cols = {c["name"] for c in insp.get_columns("ai_lab_package")}
            # Only run updates if the column exists (older DBs may be mid-migration).
            with db.engine.begin() as conn:
                if "subtitle" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET subtitle = '' WHERE subtitle IS NULL"))
                if "slug" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET slug = ('pkg-' || id) WHERE slug IS NULL OR TRIM(slug) = ''"))
                if "short_description" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET short_description = COALESCE(subtitle, '') WHERE short_description IS NULL"))
                if "package_type" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET package_type = 'custom' WHERE package_type IS NULL OR TRIM(package_type) = ''"))
                if "badge" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET badge = '' WHERE badge IS NULL"))
                if "is_popular" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET is_popular = 0 WHERE is_popular IS NULL"))
                if "is_visible" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET is_visible = 1 WHERE is_visible IS NULL"))
                if "cta_text" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET cta_text = 'Get started' WHERE cta_text IS NULL OR TRIM(cta_text) = ''"))
                if "cta_link" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET cta_link = '#inquiry' WHERE cta_link IS NULL OR TRIM(cta_link) = ''"))
                if "pricing_text" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET pricing_text = '' WHERE pricing_text IS NULL"))
                if "description" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET description = '' WHERE description IS NULL"))
                if "features" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET features = '' WHERE features IS NULL"))
                if "button_text" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET button_text = 'Get started' WHERE button_text IS NULL OR TRIM(button_text) = ''"))
                if "button_link" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET button_link = '#inquiry' WHERE button_link IS NULL OR TRIM(button_link) = ''"))
                if "badge_text" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET badge_text = '' WHERE badge_text IS NULL"))
                if "icon" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET icon = '🔧' WHERE icon IS NULL OR TRIM(icon) = ''"))
                if "display_order" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET display_order = 0 WHERE display_order IS NULL"))
                if "is_active" in pkg_cols:
                    conn.execute(text("UPDATE ai_lab_package SET is_active = 1 WHERE is_active IS NULL"))

        if "internship" in insp.get_table_names():
            int_cols = {c["name"] for c in insp.get_columns("internship")}
            with db.engine.begin() as conn:
                if "internship_type" in int_cols:
                    conn.execute(text("UPDATE internship SET internship_type = '' WHERE internship_type IS NULL"))
                if "duration" in int_cols:
                    conn.execute(text("UPDATE internship SET duration = '' WHERE duration IS NULL"))
                if "location" in int_cols:
                    conn.execute(text("UPDATE internship SET location = '' WHERE location IS NULL"))
                if "requirements" in int_cols:
                    conn.execute(text("UPDATE internship SET requirements = '' WHERE requirements IS NULL"))
                if "skills_needed" in int_cols:
                    conn.execute(text("UPDATE internship SET skills_needed = '' WHERE skills_needed IS NULL"))
                if "listing_status" in int_cols:
                    conn.execute(text("UPDATE internship SET listing_status = 'active' WHERE listing_status IS NULL OR TRIM(listing_status) = ''"))
                if "is_visible" in int_cols:
                    conn.execute(text("UPDATE internship SET is_visible = 1 WHERE is_visible IS NULL"))
                if "is_featured" in int_cols:
                    conn.execute(text("UPDATE internship SET is_featured = 0 WHERE is_featured IS NULL"))
                if "is_urgent" in int_cols:
                    conn.execute(text("UPDATE internship SET is_urgent = 0 WHERE is_urgent IS NULL"))
                if "is_remote" in int_cols:
                    conn.execute(text("UPDATE internship SET is_remote = 0 WHERE is_remote IS NULL"))

        # Backfill Store categories, slugs, and SKUs
        import re
        if "store_category" in insp.get_table_names() and "product" in insp.get_table_names():
            with db.engine.begin() as conn:
                # 1. Backfill slugs and SKUs for existing products
                rows = conn.execute(text("SELECT id, name, category, slug, sku FROM product")).all()
                for row in rows:
                    p_id, p_name, p_cat, p_slug, p_sku = row
                    updates = []
                    params = {"id": p_id}
                    if not p_slug:
                        # Clean slug
                        clean_slug = re.sub(r'[^a-zA-Z0-9\-]', '', p_name.lower().replace(' ', '-'))
                        clean_slug = clean_slug or f"prod-{p_id}"
                        updates.append("slug = :slug")
                        params["slug"] = f"{clean_slug}-{p_id}"
                    if not p_sku:
                        updates.append("sku = :sku")
                        params["sku"] = f"SKU-{p_cat[:3].upper()}-{p_id:04d}"
                    if updates:
                        sql = f"UPDATE product SET {', '.join(updates)} WHERE id = :id"
                        conn.execute(text(sql), params)
                
                # 2. Extract unique categories and populate store_category if empty
                cat_count = conn.execute(text("SELECT COUNT(*) FROM store_category")).scalar() or 0
                if cat_count == 0:
                    uniq_cats = conn.execute(text("SELECT DISTINCT category FROM product WHERE category IS NOT NULL AND TRIM(category) != ''")).all()
                    for idx, cat_row in enumerate(uniq_cats):
                        cat_name = cat_row[0].strip()
                        cat_slug = re.sub(r'[^a-zA-Z0-9\-]', '', cat_name.lower().replace(' ', '-'))
                        cat_slug = cat_slug or f"cat-{idx+1}"
                        conn.execute(
                            text("INSERT INTO store_category (name, slug, banner_url, icon_url, description, display_order) VALUES (:name, :slug, '', '📦', :desc, :order)"),
                            {"name": cat_name, "slug": cat_slug, "desc": "Products in " + cat_name + " category.", "order": idx}
                        )
