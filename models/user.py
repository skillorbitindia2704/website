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
    def has_admin_access(self):
        return (self.role or "student") == "admin" or bool(self.is_admin)

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

    admin = db.relationship("User", backref=db.backref("admin_activities", cascade="all, delete-orphan"))

