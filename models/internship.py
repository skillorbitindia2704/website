from datetime import datetime

from models import db


class Internship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, default="")
    stipend = db.Column(db.String(80), default="")
    internship_type = db.Column(db.String(80), default="")  # e.g. Paid, Academic credit
    duration = db.Column(db.String(120), default="")
    location = db.Column(db.String(200), default="")
    requirements = db.Column(db.Text, default="")
    skills_needed = db.Column(db.Text, default="")

    # active | closed | draft — public listing uses active + visible + is_active
    listing_status = db.Column(db.String(20), default="active")
    is_visible = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    is_urgent = db.Column(db.Boolean, default=False)
    is_remote = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    applications = db.relationship("InternshipApplication", back_populates="internship", lazy=True)
    program_fee_record = db.relationship("InternshipProgramFee", back_populates="internship", uselist=False, cascade="all, delete-orphan")


class InternshipApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    internship_id = db.Column(db.Integer, db.ForeignKey("internship.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    cover_letter = db.Column(db.Text, default="")
    resume_path = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(30), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    internship = db.relationship("Internship", back_populates="applications")
    user = db.relationship("User", back_populates="internship_applications")
    payments = db.relationship("InternshipProgramPayment", back_populates="application", lazy=True)


class InternshipProgramFee(db.Model):
    """Optional enrollment fee for an internship program; separate table avoids altering existing rows."""
    id = db.Column(db.Integer, primary_key=True)
    internship_id = db.Column(db.Integer, db.ForeignKey("internship.id"), nullable=False, unique=True, index=True)
    fee_inr = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    internship = db.relationship("Internship", back_populates="program_fee_record")


class InternshipProgramPayment(db.Model):
    """Razorpay payment audit record for paid internship-program applications."""
    id = db.Column(db.Integer, primary_key=True)
    internship_id = db.Column(db.Integer, db.ForeignKey("internship.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    application_id = db.Column(db.Integer, db.ForeignKey("internship_application.id"), nullable=True, index=True)
    amount_inr = db.Column(db.Integer, nullable=False)
    resume_path = db.Column(db.String(255), nullable=False)
    cover_letter = db.Column(db.Text, default="")
    status = db.Column(db.String(30), nullable=False, default="payment_pending")
    razorpay_order_id = db.Column(db.String(100), unique=True, nullable=True, index=True)
    razorpay_payment_id = db.Column(db.String(100), unique=True, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    internship = db.relationship("Internship")
    user = db.relationship("User")
    application = db.relationship("InternshipApplication", back_populates="payments")
