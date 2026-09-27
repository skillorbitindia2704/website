from functools import wraps

from flask import flash, redirect, request, session, url_for
from flask_login import current_user

from models import db
from models.user import User


def get_session_user():
    """Return the active user from session or Flask-Login."""
    uid = session.get("user_id")
    if not uid:
        if getattr(current_user, "is_authenticated", False):
            # Keep session keys in sync with remembered-login sessions.
            session["user_id"] = current_user.id
            session["role"] = current_user.role or "student"
            return current_user
        return None
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        session.pop("user_id", None)
        session.pop("role", None)
        # Fall back to Flask-Login user if available.
        if getattr(current_user, "is_authenticated", False):
            session["user_id"] = current_user.id
            session["role"] = current_user.role or "student"
            return current_user
        return None
    user = db.session.get(User, uid)
    if user:
        return user
    # Recover from stale session user IDs.
    session.pop("user_id", None)
    session.pop("role", None)
    if getattr(current_user, "is_authenticated", False):
        session["user_id"] = current_user.id
        session["role"] = current_user.role or "student"
        return current_user
    return None


def _safe_redirect_target(url):
    # Avoid open redirects; allow only same-site relative paths.
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if url.startswith("/") and not url.startswith("//"):
        return url
    return None


def role_required(required_role):
    """Decorator factory to enforce a specific role."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            user = get_session_user()
            if not user:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("auth.login", next=request.path))
            # Strict DB Validation: query the database directly instead of using session role caches
            db_user = db.session.get(User, user.id)
            if not db_user:
                flash("User not found.", "danger")
                return redirect(url_for("auth.login"))
            role = db_user.role
            # Normalize role key for templates and downstream checks.
            session["role"] = role or "student"
            if role != required_role:
                flash("Access Denied", "danger")
                return redirect(url_for("auth.login"))
            if required_role == "teacher" and not db_user.is_approved:
                flash("Waiting for admin approval", "warning")
                session.pop("user_id", None)
                session.pop("role", None)
                return redirect(url_for("auth.login"))
            return view_func(*args, **kwargs)

        return wrapper

    return decorator


def get_required_permission_for_path(path: str) -> str:
    """Map an admin URL path to its required platform module permission key."""
    if not path or not isinstance(path, str):
        return "any_admin"

    p = path.strip().lower()
    if "?" in p:
        p = p.split("?")[0]
    p = p.rstrip("/")

    # Strip '/admin' prefix if present
    if p.startswith("/admin/"):
        sub = p[len("/admin"):]
    elif p == "/admin":
        sub = "/"
    else:
        sub = p

    if sub in ("", "/", "/dashboard"):
        return "any_admin"

    if (
        sub.startswith("/courses")
        or sub.startswith("/certificates")
        or sub.startswith("/dashboard/academic-management")
    ):
        return "manage_courses"

    if (
        sub.startswith("/products")
        or sub.startswith("/orders")
        or sub.startswith("/store")
        or sub.startswith("/dashboard/store-management")
    ):
        return "manage_store"

    if (
        sub.startswith("/internships")
        or sub.startswith("/internship-application")
        or sub.startswith("/dashboard/business-management")
    ):
        return "manage_internships"

    if (
        sub.startswith("/ai-lab")
        or sub.startswith("/ai-lab-inquiries")
        or sub.startswith("/dashboard/ai-lab-management")
    ):
        return "manage_ai_lab"

    if (
        sub.startswith("/services")
        or sub.startswith("/service-requests")
        or sub.startswith("/dashboard/institutional-services")
    ):
        return "manage_services"

    if sub.startswith("/dashboard/hr-management"):
        return "manage_hr"

    if (
        sub.startswith("/homepage")
        or sub.startswith("/about")
        or sub.startswith("/site-settings")
        or sub.startswith("/website-branding")
        or sub.startswith("/home/testimonials")
        or sub.startswith("/dashboard/content-management")
    ):
        return "manage_content"

    if (
        sub.startswith("/users")
        or sub.startswith("/roles")
        or sub.startswith("/admin-accounts")
        or sub.startswith("/permissions")
        or sub.startswith("/cleanup-users")
        or sub.startswith("/teachers")
        or sub.startswith("/approve_teacher")
        or sub.startswith("/reject_teacher")
        or sub.startswith("/dashboard/user-management")
    ):
        return "manage_users"

    return "any_admin"


def admin_required(view_func):
    """Decorator to enforce admin access with fine-grained module permission boundaries.

    - Primary Super Admin has unrestricted access to all modules.
    - Scoped Admins and elevated Teachers/Students can access only modules granted to them.
    - Unauthorized access to specific modules is cleanly intercepted and redirected.
    """
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        user = get_session_user()
        if not user:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))

        db_user = db.session.get(User, user.id)
        if not db_user or db_user.is_active is False:
            flash("Account inactive or not found.", "danger")
            return redirect(url_for("auth.login"))

        # Super Admin has unrestricted access to everything
        if getattr(db_user, "is_super_admin", False):
            return view_func(*args, **kwargs)

        # Check if user has permission to access the admin area at all
        if not getattr(db_user, "can_access_admin_panel", False):
            flash("Access Denied: You do not have administrative privileges.", "danger")
            return redirect(url_for("main.home"))

        # Check granular module requirement for this specific route
        req_perm = get_required_permission_for_path(request.path)
        if req_perm == "any_admin":
            return view_func(*args, **kwargs)

        if db_user.has_permission(req_perm):
            return view_func(*args, **kwargs)

        # User is an admin or team member, but lacks permission for this specific module
        module_name = req_perm.replace("manage_", "").replace("_", " ").title()
        flash(f"Access Denied: You do not have permission to access the {module_name} module.", "danger")
        return redirect(url_for("admin.index"))

    return wrapper


teacher_required = role_required("teacher")
student_required = role_required("student")


def admin_can(permission_key: str, target_user=None) -> bool:
    """Jinja/template-safe and backend RBAC helper.

    Returns True if:
    1. The target or current session user is a Super Administrator (unrestricted access).
    2. The user has been explicitly granted this granular module permission.
    """
    try:
        user = target_user or get_session_user()
        if not user:
            return False
        db_user = db.session.get(User, user.id) if hasattr(user, "id") else user
        if not db_user or not getattr(db_user, "is_active", True):
            return False
        if getattr(db_user, "is_super_admin", False):
            return True
        has_perm_fn = getattr(db_user, "has_permission", None)
        if callable(has_perm_fn):
            return bool(has_perm_fn(permission_key))
        return False
    except Exception:
        return False


def permission_required(permission_key: str):
    """Decorator factory to enforce super-admin access or specific granted module permission."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            user = get_session_user()
            if not user:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("auth.login", next=request.path))

            db_user = db.session.get(User, user.id)
            if not db_user or not getattr(db_user, "is_active", True):
                flash("Account inactive or not found.", "danger")
                return redirect(url_for("auth.login"))

            if getattr(db_user, "is_super_admin", False) or db_user.has_permission(permission_key):
                return view_func(*args, **kwargs)

            mod_label = permission_key.replace("manage_", "").replace("_", " ").title()
            flash(f"Access Denied: You do not have permission to access the {mod_label} module.", "danger")
            return redirect(url_for("main.home"))

        return wrapper

    return decorator



