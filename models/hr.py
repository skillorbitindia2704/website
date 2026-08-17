from datetime import date, datetime
from uuid import uuid4

from models import db


def _generate_employee_code() -> str:
    return f"EMP-{uuid4().hex[:8].upper()}"


class Employee(db.Model):
    __tablename__ = "employee"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=True)
    employee_code = db.Column(db.String(40), unique=True, nullable=False, default=_generate_employee_code)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    designation = db.Column(db.String(80), default="Team Member")
    department = db.Column(db.String(80), default="Operations")
    base_salary = db.Column(db.Numeric(12, 2), default=0)
    is_active = db.Column(db.Boolean, default=True)
    joining_date = db.Column(db.Date, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="employee_profile", lazy=True)
    attendance_records = db.relationship(
        "AttendanceRecord",
        back_populates="employee",
        lazy=True,
        cascade="all, delete-orphan",
    )
    leave_requests = db.relationship(
        "LeaveRequest",
        back_populates="employee",
        lazy=True,
        cascade="all, delete-orphan",
    )
    payroll_runs = db.relationship(
        "PayrollRun",
        back_populates="employee",
        lazy=True,
        cascade="all, delete-orphan",
    )
    payroll_adjustments = db.relationship(
        "PayrollAdjustment",
        back_populates="employee",
        lazy=True,
        cascade="all, delete-orphan",
    )
    payslips = db.relationship(
        "PayrollPayslip",
        back_populates="employee",
        lazy=True,
        cascade="all, delete-orphan",
    )
    attendance_correction_requests = db.relationship(
        "AttendanceCorrectionRequest",
        back_populates="employee",
        lazy=True,
        cascade="all, delete-orphan",
    )

    @property
    def display_name(self) -> str:
        return self.name or self.email.split("@")[0]


class AttendanceRecord(db.Model):
    __tablename__ = "attendance_record"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    attendance_date = db.Column(db.Date, default=date.today, nullable=False)
    check_in = db.Column(db.DateTime, nullable=True)
    check_out = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="Present")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship("Employee", back_populates="attendance_records", lazy=True)


class LeaveRequest(db.Model):
    __tablename__ = "leave_request"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    leave_type = db.Column(db.String(50), nullable=False, default="Paid Leave")
    status = db.Column(db.String(20), nullable=False, default="Pending")
    reason = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)

    employee = db.relationship("Employee", back_populates="leave_requests", lazy=True)
    approver = db.relationship("User", lazy=True)


class AttendanceCorrectionRequest(db.Model):
    __tablename__ = "attendance_correction_request"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    attendance_id = db.Column(db.Integer, db.ForeignKey("attendance_record.id"), nullable=False)
    requested_check_in = db.Column(db.DateTime, nullable=True)
    requested_check_out = db.Column(db.DateTime, nullable=True)
    reason = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default="Pending")
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    original_check_in = db.Column(db.DateTime, nullable=True)
    original_check_out = db.Column(db.DateTime, nullable=True)
    change_notes = db.Column(db.Text, default="")

    employee = db.relationship("Employee", back_populates="attendance_correction_requests", lazy=True)
    attendance_record = db.relationship("AttendanceRecord", lazy=True)
    reviewer = db.relationship("User", lazy=True)


class AttendanceAuditLog(db.Model):
    """Immutable review trail for attendance correction decisions."""
    __tablename__ = "attendance_audit_log"

    id = db.Column(db.Integer, primary_key=True)
    correction_request_id = db.Column(db.Integer, db.ForeignKey("attendance_correction_request.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    attendance_id = db.Column(db.Integer, db.ForeignKey("attendance_record.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(30), nullable=False, default="Approved")
    status = db.Column(db.String(20), nullable=False, default="Pending")
    submitted_at = db.Column(db.DateTime, nullable=True)
    reviewed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    requested_check_in = db.Column(db.DateTime, nullable=True)
    requested_check_out = db.Column(db.DateTime, nullable=True)
    original_check_in = db.Column(db.DateTime, nullable=True)
    original_check_out = db.Column(db.DateTime, nullable=True)
    new_check_in = db.Column(db.DateTime, nullable=True)
    new_check_out = db.Column(db.DateTime, nullable=True)
    reason = db.Column(db.Text, default="")
    review_notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship("Employee", lazy=True)
    reviewer = db.relationship("User", lazy=True)
    correction_request = db.relationship("AttendanceCorrectionRequest", lazy=True)
    attendance_record = db.relationship("AttendanceRecord", lazy=True)
