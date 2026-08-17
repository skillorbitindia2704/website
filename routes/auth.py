from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import bcrypt
from models import db
from models.user import User
from utils.security_helpers import rate_limit

auth_bp = Blueprint("auth", __name__)


def _safe_redirect_target(url):
    """Allow only same-site relative paths (avoid open redirects)."""
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if url.startswith("/") and not url.startswith("//"):
        return url
    return None


@auth_bp.route("/signup", methods=["GET", "POST"])
@rate_limit(limit=5, period=60)
def signup():
    if current_user.is_authenticated:
        role = session.get("role") or current_user.role
        session["user_id"] = current_user.id
        session["role"] = role or "student"
        if role == "admin":
            return redirect(url_for("admin.index"))
        if role == "teacher":
            return redirect(url_for("teacher.dashboard"))
        return redirect(url_for("student.dashboard"))
    if request.method == "POST":
        # Backward compatible with legacy forms using "name".
        full_name = request.form.get("full_name") or request.form.get("name", "")
        full_name = full_name.strip()
        email_raw = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if len(full_name) < 3 or len(password) < 8:
            flash("Name must be 3+ characters and password 8+.", "danger")
            return redirect(url_for("auth.signup"))
        try:
            email = validate_email(email_raw, check_deliverability=False).normalized
        except EmailNotValidError:
            flash("Invalid email address.", "danger")
            return redirect(url_for("auth.signup"))
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "warning")
            return redirect(url_for("auth.signup"))
        user = User(
            full_name=full_name,
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
            role="student",
            is_approved=True,
        )
        user.sync_admin_flags()
        try:
            db.session.add(user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Email already registered. Please log in instead.", "warning")
            return redirect(url_for("auth.signup"))
        except SQLAlchemyError as exc:
            db.session.rollback()
            auth_bp.logger.exception("Signup failed due to database error: %s", exc)
            flash("We could not create your account right now. Please try again.", "danger")
            return redirect(url_for("auth.signup"))
        flash("Student account created. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/signup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
@rate_limit(limit=5, period=60)
def login():
    # If already logged in, route to correct dashboard by role.
    if current_user.is_authenticated:
        role = session.get("role") or current_user.role
        session["user_id"] = current_user.id
        session["role"] = role or "student"
        if role == "admin":
            return redirect(url_for("admin.index"))
        if role == "teacher":
            if not current_user.is_approved:
                flash("Waiting for admin approval", "warning")
                logout_user()
                session.pop("user_id", None)
                session.pop("role", None)
                return redirect(url_for("auth.login"))
            return redirect(url_for("teacher.dashboard"))
        if role == "student":
            return redirect(url_for("student.dashboard"))
            
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Email and password are required.", "danger")
            return redirect(url_for("auth.login"))
        try:
            email = validate_email(email, check_deliverability=False).normalized
        except EmailNotValidError:
            flash("Invalid email address.", "danger")
            return redirect(url_for("auth.login"))
            
        user = User.query.filter_by(email=email).first()
        from datetime import datetime, timedelta
        
        if user:
            # Check lockout
            if user.locked_until and user.locked_until > datetime.utcnow():
                lock_duration = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
                flash(f"Account locked due to repeated failed attempts. Try again in {lock_duration} minutes.", "danger")
                return redirect(url_for("auth.login"))
                
            if not bcrypt.check_password_hash(user.password_hash, password):
                # Failed attempt
                user.failed_login_attempts += 1
                if user.failed_login_attempts >= 5:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                    db.session.commit()
                    flash("Account locked due to repeated failed attempts. Locked for 15 minutes.", "danger")
                else:
                    db.session.commit()
                    flash(f"Invalid credentials. Attempts remaining: {5 - user.failed_login_attempts}", "danger")
                return redirect(url_for("auth.login"))
                
            if user.is_active is False:
                flash("This account has been disabled. Contact an administrator.", "danger")
                return redirect(url_for("auth.login"))
                
            # Successful attempt
            if user.role == "teacher" and not user.is_approved:
                flash("Waiting for admin approval", "warning")
                return redirect(url_for("auth.login"))
                
            user.failed_login_attempts = 0
            user.locked_until = None
            db.session.commit()
        else:
            # timing delay to prevent timing analysis of non-existent user
            bcrypt.generate_password_hash("dummy-pass")
            flash("Invalid credentials.", "danger")
            return redirect(url_for("auth.login"))
            
        # Store session for all roles; redirects by role
        # Prevent Session Fixation by clearing the session and rebuilding it
        old_session = {k: v for k, v in session.items() if not k.startswith("_")}
        session.clear()
        for k, v in old_session.items():
            session[k] = v
            
        session["user_id"] = user.id
        session["role"] = (user.role or "student")
        session.permanent = True  # Enforces 30-minute idle session expiration timeout
        login_user(user, remember=True)
        flash("Welcome back!", "success")
        next_url = _safe_redirect_target(request.args.get("next") or request.form.get("next"))
        if next_url:
            return redirect(next_url)
        if session["role"] == "admin":
            return redirect(url_for("admin.index"))
        if session["role"] == "teacher":
            return redirect(url_for("teacher.dashboard"))
        return redirect(url_for("student.dashboard"))
    return render_template("auth/login.html")


@auth_bp.get("/logout")
@login_required
def logout():
    session.pop("user_id", None)
    session.pop("role", None)
    logout_user()
    flash("Logged out successfully.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.full_name = request.form.get("full_name", current_user.full_name).strip()
        current_user.bio = request.form.get("bio", current_user.bio).strip()
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html")


from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@rate_limit(limit=3, period=60)
def forgot_password():
    if request.method == "POST":
        email_raw = request.form.get("email", "").strip().lower()
        if not email_raw:
            flash("Email is required.", "danger")
            return redirect(url_for("auth.forgot_password"))
        try:
            email = validate_email(email_raw, check_deliverability=False).normalized
        except EmailNotValidError:
            flash("Invalid email address.", "danger")
            return redirect(url_for("auth.forgot_password"))
            
        user = User.query.filter_by(email=email).first()
        if user:
            # Generate highly secure timed reset token
            from flask import current_app
            serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
            token = serializer.dumps(email, salt="password-reset-salt")
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            
            # Secure warning and console logging for developer local sandbox testing
            current_app.logger.info(f"--- PASSWORD RESET LINK REQUESTED FOR {email} ---")
            current_app.logger.info(f"Reset Link: {reset_url}")
            current_app.logger.info(f"--------------------------------------------------")
            
        # Timing safe: always display the same success message to prevent user enumeration
        flash("If the email address is registered, a password reset link has been sent to it.", "success")
        return redirect(url_for("auth.forgot_password"))
        
    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<string:token>", methods=["GET", "POST"])
@rate_limit(limit=5, period=60)
def reset_password(token):
    from flask import current_app
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        email = serializer.loads(token, salt="password-reset-salt", max_age=900)  # 15 minutes limit
    except (SignatureExpired, BadTimeSignature):
        flash("The password reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.login"))
        
    user = User.query.filter_by(email=email).first()
    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("auth.login"))
        
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if not password or len(password) < 8:
            flash("Password must be 8+ characters.", "danger")
            return redirect(url_for("auth.reset_password", token=token))
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.reset_password", token=token))
            
        user.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        user.failed_login_attempts = 0
        user.locked_until = None
        db.session.commit()
        flash("Your password has been reset successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))
        
    return render_template("auth/reset_password.html", token=token)
