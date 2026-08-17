from datetime import datetime
from sqlalchemy import JSON

from models import db


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False, index=True)
    description = db.Column(db.Text, default="")
    price_inr = db.Column(db.Integer, nullable=False, default=499)
    instructor_name = db.Column(db.String(120), default="Skill Orbit Faculty")
    duration = db.Column(db.String(60), default="4 weeks")
    level = db.Column(db.String(40), default="Beginner")
    # LMS ownership & catalog (nullable for legacy rows)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    is_published = db.Column(db.Boolean, nullable=False, default=True)
    thumbnail_path = db.Column(db.String(255), default="")
    category = db.Column(db.String(80), default="", index=True)
    prerequisites = db.Column(db.Text, default="")
    learning_outcomes = db.Column(db.Text, default="")
    video_url = db.Column(db.String(255), nullable=False)  # Primary video
    content = db.Column(db.Text, default="")
    quiz_question = db.Column(db.String(255), default="")  # Keep for compatibility
    quiz_answer = db.Column(db.String(255), default="")    # Keep for compatibility

    # Catalog / marketing (optional; legacy DBs pick up via migrate_sqlite_schema)
    list_price_inr = db.Column(db.Integer, nullable=False, default=0)  # 0 = no strike-through
    rating_avg = db.Column(db.Float, nullable=False, default=4.8)
    rating_count = db.Column(db.Integer, nullable=False, default=0)
    enrolled_count_display = db.Column(db.Integer, nullable=False, default=0)  # override; 0 = use live count
    is_featured = db.Column(db.Boolean, nullable=False, default=False)
    catalog_display_order = db.Column(db.Integer, nullable=False, default=0)
    
    # Extended teaching system
    live_class = db.Column(JSON, default={})  # { url: string, datetime: string }
    videos = db.Column(JSON, default=[])      # [{ url: string, title: string }, ...]
    notes = db.Column(JSON, default=[])       # [{ title: string, content: string }, ...]
    quiz = db.Column(JSON, default=[])        # [{ question: string, options: [], correctAnswer: string }, ...]
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    teacher = db.relationship("User", foreign_keys=[teacher_id], backref=db.backref("courses_teaching", lazy="dynamic"))
    enrollments = db.relationship("Enrollment", back_populates="course", lazy=True)
    certificates = db.relationship("Certificate", back_populates="course", lazy=True, cascade="all, delete-orphan")


class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False, index=True)
    progress_pct = db.Column(db.Integer, default=0)
    quiz_passed = db.Column(db.Boolean, default=False)
    is_paid = db.Column(db.Boolean, nullable=False, default=False)
    razorpay_order_id = db.Column(db.String(100), default="")
    razorpay_payment_id = db.Column(db.String(100), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship("User", back_populates="enrollments")
    course = db.relationship("Course", back_populates="enrollments")

    __table_args__ = (db.UniqueConstraint("user_id", "course_id", name="unique_user_course"),)


class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    certificate_uid = db.Column(db.String(36), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    pdf_path = db.Column(db.String(255), nullable=False)

    user = db.relationship("User", back_populates="certificates")
    course = db.relationship("Course", back_populates="certificates")


class CoursePayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False, index=True)
    amount_inr = db.Column(db.Integer, nullable=False)
    razorpay_order_id = db.Column(db.String(100), nullable=False, index=True)
    razorpay_payment_id = db.Column(db.String(100), default="")
    razorpay_signature = db.Column(db.String(255), default="")
    status = db.Column(db.String(30), nullable=False, default="created")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship("User", backref="course_payments")
    course = db.relationship("Course", backref="course_payments")
