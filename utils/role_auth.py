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


admin_required = role_required("admin")
teacher_required = role_required("teacher")
student_required = role_required("student")


def admin_can(permission_key: str) -> bool:
    """Jinja/template-safe RBAC helper.

    The project currently enforces admin access via `admin_required`.
    Templates expect `admin_can(<permission>)`; since a full permission
    matrix is not present in codebase, we conservatively grant access
    based on whether the current user is an admin.

    This keeps templates working without changing backend RBAC behavior.
    """
    try:
        user = get_session_user()
        if not user:
            return False
        # Admin gate: `sync_admin_flags()` sets `is_admin`/`role` accordingly.
        return bool(getattr(user, "has_admin_access", False) if callable(getattr(user, "has_admin_access", None)) else getattr(user, "is_admin", False)) or (
            (getattr(user, "role", None) == "admin")
        )
    except Exception:
        return False

