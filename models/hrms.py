"""Additive HRMS models for versioned teacher compensation and payroll controls.

These tables extend the existing Employee and PayrollRun models. Existing HR/payroll
tables and records are intentionally left unchanged.
"""
from datetime import datetime
from models import db


class TeacherPaymentAgreement(db.Model):
    __tablename__ = "teacher_payment_agreement"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False, index=True)
    engagement_type = db.Column(db.String(40), nullable=False, default="Contractual")
    payment_model = db.Column(db.String(40), nullable=False, default="Hybrid")
    monthly_retainer = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    hourly_rate = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    per_class_rate = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    course_incentive_rate = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    revenue_share_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    effective_from = db.Column(db.Date, nullable=False)
    effective_to = db.Column(db.Date, nullable=True)
    agreement_reference = db.Column(db.String(120), default="")
    notes = db.Column(db.Text, default="")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    employee = db.relationship("Employee", lazy=True)
    creator = db.relationship("User", foreign_keys=[created_by], lazy=True)


class TeachingActivity(db.Model):
    """Admin-verified payable teaching activity; never inferred from login duration."""
    __tablename__ = "teaching_activity"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False, index=True)
    activity_date = db.Column(db.Date, nullable=False, index=True)
    activity_type = db.Column(db.String(30), nullable=False)  # hourly, class, course, revenue
    quantity = db.Column(db.Numeric(12, 3), nullable=False, default=0)
    course_name = db.Column(db.String(160), default="")
    reference = db.Column(db.String(120), default="")
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default="Pending")
    verified_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    employee = db.relationship("Employee", lazy=True)
    verifier = db.relationship("User", foreign_keys=[verified_by], lazy=True)
    creator = db.relationship("User", foreign_keys=[created_by], lazy=True)


class PayrollPeriodLock(db.Model):
    """Database-level duplicate guard for one employee's calendar-month payroll."""
    __tablename__ = "payroll_period_lock"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    payroll_run_id = db.Column(db.Integer, db.ForeignKey("payroll_run.id"), nullable=False, unique=True)
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("employee_id", "period_start", "period_end", name="uq_payroll_employee_period"),
    )

    employee = db.relationship("Employee", lazy=True)
    payroll_run = db.relationship("PayrollRun", lazy=True)


class PayrollApproval(db.Model):
    __tablename__ = "payroll_approval"

    id = db.Column(db.Integer, primary_key=True)
    payroll_run_id = db.Column(db.Integer, db.ForeignKey("payroll_run.id"), nullable=False, index=True)
    stage = db.Column(db.String(20), nullable=False)  # HR, Accounts, Founder
    status = db.Column(db.String(20), nullable=False)  # Approved, Rejected
    approver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    remarks = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    payroll_run = db.relationship("PayrollRun", lazy=True)
    approver = db.relationship("User", lazy=True)


class PayrollPayment(db.Model):
    __tablename__ = "payroll_payment"

    id = db.Column(db.Integer, primary_key=True)
    payroll_run_id = db.Column(db.Integer, db.ForeignKey("payroll_run.id"), nullable=False, index=True)
    method = db.Column(db.String(30), nullable=False, default="Manual Bank Transfer")
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Paid")
    transaction_reference = db.Column(db.String(140), nullable=False)
    proof_url = db.Column(db.String(255), default="")
    remarks = db.Column(db.Text, default="")
    processed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    paid_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    payroll_run = db.relationship("PayrollRun", lazy=True)
    processor = db.relationship("User", lazy=True)


class PayrollDispute(db.Model):
    __tablename__ = "payroll_dispute"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False, index=True)
    payroll_run_id = db.Column(db.Integer, db.ForeignKey("payroll_run.id"), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Submitted")
    resolution = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)

    employee = db.relationship("Employee", lazy=True)
    payroll_run = db.relationship("PayrollRun", lazy=True)
