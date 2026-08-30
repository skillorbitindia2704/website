import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None
from flask import Flask, flash, redirect, request, url_for, render_template
from flask_wtf.csrf import CSRFError
from markupsafe import Markup, escape
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from extensions import bcrypt, csrf, login_manager
from typing import cast

# Pylance/pyright: Flask-SQLAlchemy and Flask-Login are dynamically typed.
# These suppressions prevent false-positive type diagnostics without changing runtime behavior.
# pyright: ignore[reportUnusedImport, reportUnknownVariableType, reportUnknownMemberType, reportCallIssue, reportAttributeAccessIssue, reportDeprecated, reportMissingParameterType, reportUnknownArgumentType]

from models import db
if TYPE_CHECKING:
    from models.ai_lab_inquiry import AILabInquiry

if TYPE_CHECKING:
    from models.ai_lab_package import AILabPackage

if TYPE_CHECKING:
    from models.course import Course, CoursePayment, Enrollment

import models.lms  # noqa: F401  — register LMS tables with SQLAlchemy metadata


if TYPE_CHECKING:
    from models.internship import Internship, InternshipApplication

if TYPE_CHECKING:
    from models.notification import Notification

if TYPE_CHECKING:
    from models.service_request import ServiceRequest

if TYPE_CHECKING:
    from models.service_package import ServicePackage

from models.site_setting import SiteSetting

# Branding settings keys (saved in SiteSetting key-value store)
BRANDING_LOGO_KEY = "logo_url"
BRANDING_DARK_LOGO_KEY = "dark_logo_url"
BRANDING_FAVICON_KEY = "favicon_url"

if TYPE_CHECKING:
    from models.store import Order, OrderItem, Product, StorePayment, StoreTransaction

from models.user import User
from models.hr import Employee, AttendanceRecord, LeaveRequest, AttendanceCorrectionRequest, AttendanceAuditLog  # noqa: F401
from models.payroll import PayrollRun, PayrollAdjustment, PayrollPayslip  # noqa: F401

if TYPE_CHECKING:
    from models.wishlist import WishlistItem

from models.about_content import AboutContent  # noqa: F401
from models.about_team import AboutTeamMember  # noqa: F401
from models.about_timeline import AboutTimelineEntry  # noqa: F401
from models.about_gallery import AboutGalleryImage  # noqa: F401
from models.about_partner import AboutPartnerLogo  # noqa: F401
from models.about_recognition import AboutRecognition  # noqa: F401
from models.about_counter import AboutCounter  # noqa: F401
from models.about_testimonial import AboutTestimonial  # noqa: F401
from models.about_version import AboutVersion  # noqa: F401
from models.about_activity import AboutActivityLog  # noqa: F401
from models.course_cert_highlight import CourseCertHighlight  # noqa: F401
from models.course_learning_path import CourseLearningPath  # noqa: F401
from models.course_showcase_project import CourseShowcaseProject  # noqa: F401
from models.courses_page_content import CoursesPageContent  # noqa: F401
from models.homepage_hero import HomePageHero  # noqa: F401
from models.homepage_content import HomeContent  # noqa: F401
from models.homepage_version import HomeVersion  # noqa: F401
from models.homepage_activity import HomeActivityLog  # noqa: F401
from routes.admin import admin_bp

from routes.ai_lab import ai_lab_bp
from routes.api import api_bp
from routes.auth import auth_bp
from routes.certificates import cert_bp
from routes.courses import courses_bp
from routes.dashboard import dashboard_bp
from routes.internships import internships_bp
from routes.it_services import it_services_bp
from routes.it_services import ensure_default_service_packages
from routes.main import main_bp
from routes.store import store_bp
from routes.store_api import store_api_bp
from routes.student_routes import student_bp
from routes.teacher_routes import teacher_bp
from utils.db_migrate import migrate_sqlite_schema

# Help static analyzers: these functions are registered by Flask at runtime.
# (No behavioral change.)


# type: ignore[reportUnknownVariableType, reportUnknownMemberType, reportCallIssue, reportAttributeAccessIssue, reportDeprecated, reportMissingParameterType, reportUnknownArgumentType, reportUnusedImport]
# Ensure local .env overrides any pre-set environment variables when available.
if load_dotenv is not None:
    load_dotenv(override=True)


def _ensure_admin_account():
    """Create fixed default admin on first run if not present."""
    admin_email = "skillorbitindia2704@gmail.com"
    admin_password = "MAAN0864208642"
    existing = User.query.filter_by(email=admin_email).first()
    if existing:
        return
    password_hash = bcrypt.generate_password_hash(admin_password).decode("utf-8")
    if not existing:
        user = User(
            full_name="Platform Admin",
            email=admin_email,
            password_hash=password_hash,
            role="admin",
            is_admin=True,
            is_approved=True,
        )
        user.sync_admin_flags()
        db.session.add(user)
        db.session.commit()


def _ensure_ai_lab_packages():
    """Seed default AI Lab packages on first run if none exist."""
    try:
        if AILabPackage.query.first():
            return
    except Exception:
        # Table might not exist yet, that's ok
        return

    default_packages = [
        {
            "title": "Basic Lab",
            "subtitle": "Starter STEM & coding footprint",
            "pricing_text": "From ₹1.8 L · Institutions pricing",
            "description": "Perfect for schools starting their AI & robotics journey",
            "features": "10–15 learner workstations\nArduino & sensor starter bundles\nPrinted lab curriculum outline\n2 online faculty enablement sessions",
            "button_text": "Get started",
            "icon": "🔧",
            "display_order": 0,
        },
        {
            "title": "Advanced Lab",
            "subtitle": "AI-ready builds with heavier kits",
            "pricing_text": "From ₹3.5 L",
            "description": "For institutions ready for comprehensive AI integration",
            "features": "Everything in Basic\nEdge AI modules & vision kits\nRaspberry Pi / MCU mix\n4 on-site or virtual PD days\nCompetition pathway support",
            "button_text": "Get started",
            "icon": "⚡",
            "display_order": 1,
        },
        {
            "title": "Premium Lab",
            "subtitle": "Flagship innovation center",
            "pricing_text": "Custom · Talk to us",
            "description": "Full-scale innovation labs with drone integration",
            "features": "Full room design & risk planning\nDrone + robotics lane (optional)\nLMS hooks & assessment rubrics\nDedicated success manager for 12 months\nAnnual student showcase playbook",
            "button_text": "Get started",
            "icon": "🎓",
            "display_order": 2,
        },
    ]

    for pkg_data in default_packages:
        pkg = AILabPackage(**pkg_data, is_active=1)
        db.session.add(pkg)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def create_app():
    app = Flask(__name__)

    os.makedirs(app.instance_path, exist_ok=True)
    
    # Configure production logging with RotatingFileHandler
    import logging
    from logging.handlers import RotatingFileHandler
    
    log_dir = os.path.join(app.root_path, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "skill_orbit.log")
    
    file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s'
    ))
    file_handler.setLevel(logging.INFO)
    
    class RequestIdFilter(logging.Filter):
        def filter(self, record):
            from flask import has_request_context, request
            record.request_id = request.id if has_request_context() and hasattr(request, 'id') else 'N/A'
            return True
            
    file_handler.addFilter(RequestIdFilter())
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)

    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change")

    configured_db_uri = os.getenv("DATABASE_URL")

if configured_db_uri:
    uri = configured_db_uri.strip()

    # PostgreSQL: explicitly use Psycopg 3
    if uri.startswith("postgres://"):
        uri = uri.replace(
            "postgres://",
            "postgresql+psycopg://",
            1
        )
    elif uri.startswith("postgresql://"):
        uri = uri.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1
        )

    # SQLite: keep existing local-development behavior
    elif uri.lower().startswith("sqlite:///") and not uri.lower().startswith("sqlite:////"):
        relative_db_path = uri[len("sqlite:///") :].strip()
        if relative_db_path:
            sqlite_file = os.path.normpath(
                os.path.join(app.instance_path, relative_db_path)
            )
            uri = f"sqlite:///{sqlite_file}"

    app.config["SQLALCHEMY_DATABASE_URI"] = uri

else:
    # Local development fallback
    db_file = os.path.join(
        app.instance_path,
        "skill_orbit_india.db"
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_file}"
    else:
        # Keep SQLite under the instance folder so local dev and deployment both point to a stable file.
        db_file = os.path.join(app.instance_path, "skill_orbit_india.db")
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_file}"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "connect_args": {"check_same_thread": False, "timeout": 30},
            "pool_pre_ping": True,
        }
    # Allow larger LMS media uploads (per-route validation still applies).
    app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_MB", "128")) * 1024 * 1024
    app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads", "resumes")
    app.config["RAZORPAY_KEY_ID"] = os.getenv("RAZORPAY_KEY_ID", "")
    app.config["RAZORPAY_KEY_SECRET"] = os.getenv("RAZORPAY_KEY_SECRET", "")
    app.config["ADMIN_EMAIL"] = "skillorbitindia2704@gmail.com"
    
    # Session Cookie Security Hardening
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # Enable secure cookies in non-development environments
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV", "development") != "development"
    from datetime import timedelta
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)

    # Production Environment Safety Warning
    flask_env = os.getenv("FLASK_ENV", "production")
    if app.config["SECRET_KEY"] == "dev-secret-key-change" and flask_env != "development":
        app.logger.error("CRITICAL SECURITY WARNING: SECRET_KEY is set to the default 'dev-secret-key-change' in a production environment! Set a custom SECRET_KEY environment variable immediately.")

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    cast(Any, login_manager).login_view = "auth.login"
    cast(Any, login_manager).login_message = None

    def _render_remix_icon(icon: str) -> Markup:
        if not icon:
            return Markup("")
        value = str(icon).strip()
        # Passthrough if the template already provides a full tag or a remix icon class.
        if value.startswith("<i ") or value.startswith("<i>") or value.startswith("ri-"):
            if value.startswith("ri-"):
                return Markup(f'<i class="{escape(value)}" aria-hidden="true"></i>')
            return Markup(value)

        emoji_map = {
            "🎓": "ri-graduation-cap-line",
            "⚡": "ri-flashlight-line",
            "🏫": "ri-building-2-line",
            "📞": "ri-phone-line",
            "✅": "ri-checkbox-circle-line",
            "📦": "ri-archive-line",
            "🛒": "ri-shopping-cart-line",
            "🧠": "ri-brain-line",
            "🤖": "ri-robot-2-line",
            "🌐": "ri-global-line",
            "🐍": "ri-code-line",
            "⚙️": "ri-settings-2-line",
            "⚙": "ri-settings-2-line",
            "▶": "ri-play-circle-line",
            "➡": "ri-arrow-right-line",
            "★": "ri-star-s-fill",
            "☆": "ri-star-line",
            "✉️": "ri-mail-line",
            "📧": "ri-mail-line",
            "📩": "ri-mail-send-line",
            "🧭": "ri-compass-line",
            "🎖️": "ri-award-line",
            "🎨": "ri-palette-line",
            "👨‍💻": "ri-computer-line",
            "👩‍💻": "ri-computer-line",
            "💡": "ri-lightbulb-line",
            "🎫": "ri-ticket-line",
            "📚": "ri-book-open-line",
            "📜": "ri-file-paper-line",
            "🛡️": "ri-shield-check-line",
            "🗑️": "ri-delete-bin-6-line",
            "📷": "ri-camera-line",
            "💼": "ri-briefcase-line",
            "🏠": "ri-home-7-line",
            "🌱": "ri-plant-line",
            "📅": "ri-calendar-line",
            "🔭": "ri-telescope-line",
            "🎛️": "ri-sliders-line",
            "💾": "ri-save-line",
            "🔄": "ri-refresh-line",
            "❌": "ri-close-circle-line",
            "⚠️": "ri-alert-line",
            "⚠": "ri-alert-line",
        }

        # Additional common emoji -> remix icon mappings (cover templates/admin uses)
        emoji_map.update({
            "✨": "ri-star-line",
            "📁": "ri-folder-3-line",
            "☰": "ri-drag-move-line",
            "🚀": "ri-rocket-line",
            "⭐": "ri-star-s-fill",
            "➕": "ri-add-line",
            "🔥": "ri-fire-line",
            "⏱️": "ri-timer-line",
            "⏱": "ri-timer-line",
            "👤": "ri-user-3-line",
            "📸": "ri-camera-line",
            "📷": "ri-camera-line",
            "📋": "ri-file-list-3-line",
            "🏅": "ri-award-line",
            "🇮🇳": "ri-global-line",
            "📄": "ri-file-paper-line",
            "🎯": "ri-target-line",
            "🔢": "ri-hashtag",
            "🔭": "ri-telescope-line",
            "🤝": "ri-hand-coin-line",
        })
        if value in emoji_map:
            return Markup(f'<i class="{emoji_map[value]}" aria-hidden="true"></i>')

        # Detect if the value is already a remix icon class name.
        if value.startswith("ri-"):
            return Markup(f'<i class="{escape(value)}" aria-hidden="true"></i>')

        # Fallback: use a generic icon class and preserve the raw value as alt text.
        return Markup(f'<span class="icon-fallback" title="{escape(value)}">{escape(value)}</span>')

    app.jinja_env.filters["remix_icon"] = _render_remix_icon

    @login_manager.unauthorized_handler
    def _unauthorized():
        flash("Please login to continue", "warning")
        return redirect(url_for("auth.login", next=request.path))

    @login_manager.user_loader
    def load_user(user_id: str) -> Optional[Any]:
        return db.session.get(User, int(user_id))

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(store_bp, url_prefix="/store")
    app.register_blueprint(store_api_bp, url_prefix="/store")
    app.register_blueprint(courses_bp, url_prefix="/courses")
    app.register_blueprint(cert_bp, url_prefix="/certificate")
    app.register_blueprint(internships_bp, url_prefix="/internships")
    app.register_blueprint(it_services_bp, url_prefix="/it-services")
    app.register_blueprint(ai_lab_bp, url_prefix="/ai-lab")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(teacher_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        app.logger.warning(f"CSRF validation failed: {error.description}")
        flash("Your session may have expired, or the CSRF token was invalid. Please try again.", "danger")
        return redirect(request.referrer or url_for("admin.about_recognition"))

    @app.errorhandler(400)
    def bad_request_error(error):
        app.logger.warning(f"400 Bad Request: {error}")
        return render_template("errors/400.html"), 400

    @app.errorhandler(403)
    def forbidden_error(error):
        app.logger.warning(f"403 Access Denied: {error}")
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found_error(error):
        app.logger.info(f"404 Not Found: {request.path}")
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def ratelimit_handler(error):
        app.logger.warning(f"429 Too Many Requests: {error}")
        return render_template("errors/429.html"), 429

    @app.errorhandler(SQLAlchemyError)
    def handle_sqlalchemy_error(error):
        app.logger.error(f"Database operation failed: {error}", exc_info=True)
        return render_template("errors/500.html"), 500

    @app.errorhandler(OperationalError)
    def handle_operational_error(error):
        app.logger.error(f"SQLAlchemy OperationalError: {error}", exc_info=True)
        return render_template("errors/500.html"), 500

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"500 Internal Server Error: {error}", exc_info=True)
        return render_template("errors/500.html"), 500

    @app.context_processor
    def inject_globals() -> Dict[str, Any]:
        # Make admin permission helper available in all templates.
        # (Used by templates/admin/index.html)
        try:
            from utils.role_auth import admin_can  # local import avoids cycles
        except Exception:
            admin_can = cast(Callable[[str], bool], lambda _key: False)

        from flask import has_request_context, request, url_for as original_url_for
        from werkzeug.routing import BuildError

        def safe_url_for(endpoint, **values):
            try:
                return original_url_for(endpoint, **values)
            except BuildError as e:
                app.logger.warning(f"Jinja BuildError for endpoint '{endpoint}': {e}. Falling back to '#'.")
                return "#"

        site_url = (os.getenv("SITE_URL") or "").rstrip("/")
        if not site_url and has_request_context():
            site_url = request.url_root.rstrip("/")

        default_settings = {
            "contact_email": "skillorbitindia2704@gmail.com",
            "contact_phone": "+91 99999 99999",
            "whatsapp_number": "919999999999",
            "address_text": "India (Online + On-site for institutions)",
            "map_embed_url": "https://www.google.com/maps?q=India&output=embed",
            "linkedin_url": "#",
            "youtube_url": "#",
            "instagram_url": "#",
            "logo_url": "",
            "dark_logo_url": "",
            "favicon_url": "",
        }
        site_settings = dict(default_settings)
        try:
            rows = SiteSetting.query.all()
            for row in rows:
                if row.key in site_settings and row.value:
                    site_settings[row.key] = row.value
        except Exception:
            # If table is not ready yet, keep defaults.
            pass

        return {
            "url_for": safe_url_for,
            "current_year": datetime.now(timezone.utc).year,
            "admin_can": admin_can,
            "seo_site_url": site_url,
            "seo_site_name": "Skill Orbit India",
            "seo_default_description": (
                "Skill Orbit India — hands-on tech courses, electronics store, verified certificates, "
                "internships, IT services, and AI lab setup for learners across India."
            ),
            "seo_default_keywords": (
                "Skill Orbit India, EdTech, online courses, electronics kits, certificates, "
                "internships, IT services, AI lab, India, tech education"
            ),
            "site_settings": site_settings,
        }

    import uuid

    @app.before_request
    def force_https():
        if app.config.get("TESTING"):
            return
        if os.getenv("FLASK_ENV", "production") != "development":
            if request.headers.get("X-Forwarded-Proto", "http") == "http":
                url = request.url.replace("http://", "https://", 1)
                return redirect(url, code=301)

    @app.before_request
    def add_request_id():
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.id = req_id

    @app.after_request
    def set_security_headers(response):
        # Prevent Clickjacking
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # XSS Protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Permissions Policy
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), interest-cohort=()"
        
        # Inject Request ID
        if hasattr(request, "id"):
            response.headers["X-Request-ID"] = request.id

        # Static asset caching headers
        if request.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=31536000"
        
        # HSTS (Strict-Transport-Security) - only if not in development/debug mode
        flask_env = os.getenv("FLASK_ENV", "production")
        if flask_env != "development" and not app.debug:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            
        # Content Security Policy (CSP)
        # Note: 'unsafe-inline' and 'unsafe-eval' are required for Razorpay checkout, Flask-WTF CSRF and standard templates.
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://checkout.razorpay.com https://api.razorpay.com https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://api.razorpay.com https://*.razorpay.com ws: wss:; "
            "frame-src 'self' https://api.razorpay.com https://checkout.razorpay.com https://www.google.com https://maps.google.com https://*.google.com;"
        )
        response.headers["Content-Security-Policy"] = csp
        return response

    with app.app_context():
        try:
            db.create_all()
            migrate_sqlite_schema(app)
            _ensure_admin_account()
            _ensure_ai_lab_packages()
            ensure_default_service_packages()
        except OperationalError as exc:
            app.logger.error(f"Database startup bootstrap raised SQLAlchemy OperationalError: {exc}", exc_info=True)
        except SQLAlchemyError as exc:
            app.logger.error(f"Database startup bootstrap raised SQLAlchemyError: {exc}", exc_info=True)
        except Exception as exc:
            app.logger.error(f"Database bootstrap raised an unexpected startup exception: {exc}", exc_info=True)

    return app


if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_ENV", "development") == "development"
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    try:
        app = create_app()
        print(f"Starting Skill Orbit India on http://{host}:{port} (debug={debug_mode})")
        app.run(host=host, port=port, debug=debug_mode)
    except OSError as exc:
        # Common local-dev issue: selected port already in use.
        if "Address already in use" in str(exc):
            fallback_port = 5001
            print(f"Port {port} is busy. Retrying on http://{host}:{fallback_port}")
            app = create_app()
            app.run(host=host, port=fallback_port, debug=debug_mode)
        else:
            print(f"Flask startup failed: {exc}")
            raise
    except Exception as exc:
        print(f"Application crashed during startup: {exc}")
        raise
