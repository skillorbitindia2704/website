import os
from datetime import datetime

from flask_login import UserMixin

from models import db



class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    bio = db.Column(db.Text, default="")
    points = db.Column(db.Integer, default=0)
    badge = db.Column(db.String(50), default="Starter")
    # Role-based access control: admin | teacher | student
    role = db.Column(db.String(20), nullable=False, default="student", index=True)
    # Teacher accounts must be approved by an admin before dashboard access.
    is_approved = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def username(self):
        if self.full_name:
            return self.full_name
        return self.email.split("@")[0] if self.email else "User"

    @property
    def is_super_admin(self) -> bool:
        """Return True if user is the primary master super admin."""
        primary_admin_email = os.getenv("ADMIN_EMAIL", "skillorbitindia2704@gmail.com").strip().lower()
        if self.email and self.email.strip().lower() == primary_admin_email:
            return True
        if self.id == 1:
            return True
        return False

    @property
    def has_admin_access(self) -> bool:
        return (self.role or "student") == "admin" or bool(self.is_admin)

    @property
    def has_custom_permissions(self) -> bool:
        perms = getattr(self, "custom_permissions", None) or []
        return len(perms) > 0

    @property
    def can_access_admin_panel(self) -> bool:
        """Return True if user can access the admin console area."""
        if self.is_active is False:
            return False
        if self.is_super_admin:
            return True
        perms = getattr(self, "custom_permissions", None) or []
        if perms:
            # Configured user: must have at least one active (non-'none') module permission
            return any(p.permission_key != "none" for p in perms)
        # Unconfigured user: only default admins can access
        return self.has_admin_access

    def sync_admin_flags(self):
        if (self.role or "student") == "admin":
            self.is_admin = True
            self.is_approved = True
        elif self.role == "teacher":
            self.is_admin = False
        elif self.role == "student":
            self.is_admin = False
            self.is_approved = True

    orders = db.relationship("Order", back_populates="user", lazy=True)
    enrollments = db.relationship("Enrollment", back_populates="user", lazy=True)
    certificates = db.relationship("Certificate", back_populates="user", lazy=True, cascade="all, delete-orphan")
    internship_applications = db.relationship("InternshipApplication", back_populates="user", lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="user", lazy=True, cascade="all, delete-orphan")
    wishlist_items = db.relationship("WishlistItem", back_populates="user", lazy=True, cascade="all, delete-orphan")
    employee_profile = db.relationship("Employee", uselist=False, back_populates="user", lazy=True)
    custom_permissions = db.relationship(
        "UserPermission",
        foreign_keys="UserPermission.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def has_permission(self, perm_key: str) -> bool:
        """Return True if user is super admin, or has this module permission explicitly granted."""
        if self.is_super_admin:
            return True
        perms = getattr(self, "custom_permissions", None) or []
        if perms:
            # If user has explicit permission records, check against granted active keys (ignoring sentinel 'none')
            granted = {p.permission_key for p in perms if p.permission_key != "none"}
            return perm_key in granted
        # If unconfigured: default admin has all permissions; teacher/student has none
        if self.has_admin_access:
            return True
        return False

    def get_permission_keys(self) -> set:
        """Return a set of active granted module permission keys."""
        all_modules = {
            "manage_courses",
            "manage_store",
            "manage_internships",
            "manage_ai_lab",
            "manage_services",
            "manage_hr",
            "manage_content",
            "manage_users",
        }
        if self.is_super_admin:
            return all_modules
        perms = getattr(self, "custom_permissions", None) or []
        if perms:
            return {p.permission_key for p in perms if p.permission_key != "none"}
        if self.has_admin_access:
            return all_modules
        return set()

    def update_badge(self):
        from models.course import Certificate, Enrollment
        from models.store import Order

        order_count = Order.query.filter_by(user_id=self.id).count()
        cert_count = Certificate.query.filter_by(user_id=self.id).count()
        completed_courses = Enrollment.query.filter_by(user_id=self.id, quiz_passed=True).count()

        if self.points >= 1000:
            self.badge = "Galaxy Mentor"
        elif cert_count >= 2 or completed_courses >= 2:
            self.badge = "Top Learner"
        elif order_count >= 3:
            self.badge = "Top Buyer"
        elif self.points >= 500:
            self.badge = "Orbit Pro"
        elif self.points >= 200:
            self.badge = "Orbit Learner"
        else:
            self.badge = "Starter"


class UserPermission(db.Model):
    __tablename__ = "user_permission"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_key = db.Column(db.String(50), nullable=False, index=True)
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)
    granted_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    user = db.relationship("User", foreign_keys=[user_id], back_populates="custom_permissions")
    granted_by = db.relationship("User", foreign_keys=[granted_by_id])

    __table_args__ = (
        db.UniqueConstraint("user_id", "permission_key", name="uq_user_permission"),
    )


class AdminActivityLog(db.Model):
    __tablename__ = "admin_activity_log"
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)  # create, edit, delete
    target_table = db.Column(db.String(100), nullable=False)
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, default="")
    ip_address = db.Column(db.String(45), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    admin = db.relationship("User", foreign_keys=[admin_id], backref=db.backref("admin_activities", cascade="all, delete-orphan"))


