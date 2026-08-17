from datetime import date, datetime
from decimal import Decimal

from models import db
from models.hr import Employee


class PayrollRun(db.Model):
    __tablename__ = "payroll_run"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    period_start = db.Column(db.Date, nullable=False, default=date.today)
    period_end = db.Column(db.Date, nullable=False, default=date.today)
    gross_pay = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    allowances = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    deductions = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    net_pay = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    status = db.Column(db.String(30), nullable=False, default="Draft")
    remarks = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship("Employee", back_populates="payroll_runs", lazy=True)
    adjustments = db.relationship(
        "PayrollAdjustment",
        back_populates="payroll_run",
        lazy=True,
        cascade="all, delete-orphan",
    )
    payslips = db.relationship(
        "PayrollPayslip",
        back_populates="payroll_run",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def calculate_net_pay(self) -> Decimal:
        return Decimal(self.gross_pay or 0) + Decimal(self.allowances or 0) - Decimal(self.deductions or 0)


class PayrollAdjustment(db.Model):
    __tablename__ = "payroll_adjustment"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    payroll_run_id = db.Column(db.Integer, db.ForeignKey("payroll_run.id"), nullable=True)
    adjustment_type = db.Column(db.String(50), nullable=False, default="Allowance")
    amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    reason = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship("Employee", back_populates="payroll_adjustments", lazy=True)
    payroll_run = db.relationship("PayrollRun", back_populates="adjustments", lazy=True)


class PayrollPayslip(db.Model):
    __tablename__ = "payroll_payslip"

    id = db.Column(db.Integer, primary_key=True)
    payroll_run_id = db.Column(db.Integer, db.ForeignKey("payroll_run.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    pdf_url = db.Column(db.String(255), default="")
    issued_by = db.Column(db.String(120), default="HR Admin")
    notes = db.Column(db.Text, default="")

    payroll_run = db.relationship("PayrollRun", back_populates="payslips", lazy=True)
    employee = db.relationship("Employee", back_populates="payslips", lazy=True)
