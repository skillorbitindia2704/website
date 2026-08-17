from functools import wraps

from flask import flash, redirect, request, url_for
from flask_login import current_user

from utils.role_auth import admin_required


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not getattr(current_user, "is_authenticated", False):
            flash("Please login to continue", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapper
