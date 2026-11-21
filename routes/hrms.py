"""Additive HRMS workflows. Existing /admin HR and /teacher HR routes remain intact."""
import calendar
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models import db
from models.hr import Employee
from models.payroll import PayrollRun, PayrollAdjustment
from models.hrms import (
    TeacherPaymentAgreement, TeachingActivity, PayrollPeriodLock,
    PayrollApproval, PayrollPayment, PayrollDispute,
)
from utils.role_auth import admin_required, teacher_required

hrms_bp = Blueprint("hrms", __name__)
CENT = Decimal("0.01")


def money(value):
    try:
        amount = Decimal(str(value or "0")).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Enter a valid monetary amount.")
    if not amount.is_finite() or amount < 0:
        raise ValueError("Amounts must be valid non-negative numbers.")
    return amount


def parse_date(value, field):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError(f"Select a valid {field}.")


def _agreement_for_period(employee_id, start, end):
    agreements = TeacherPaymentAgreement.query.filter(
        TeacherPaymentAgreement.employee_id == employee_id,
        TeacherPaymentAgreement.is_active.is_(True),
        TeacherPaymentAgreement.effective_from <= end,
        db.or_(
            TeacherPaymentAgreement.effective_to.is_(None),
            TeacherPaymentAgreement.effective_to >= start,
        ),
    ).order_by(TeacherPaymentAgreement.effective_from.asc()).all()
    if len(agreements) > 1:
        raise ValueError("Multiple payment agreements overlap this payroll month. Resolve the effective dates before generating payroll.")
    return agreements[0] if agreements else None


def _approval_map(payroll_run):
    rows = PayrollApproval.query.filter_by(payroll_run_id=payroll_run.id).order_by(PayrollApproval.created_at.asc()).all()
    latest = {}
    for row in rows:
        latest[row.stage] = row
    return latest


def _paid_total(payroll_run):
    value = db.session.query(func.coalesce(func.sum(PayrollPayment.amount), 0)).filter(
        PayrollPayment.payroll_run_id == payroll_run.id,
        PayrollPayment.status == "Paid",
    ).scalar()
    return Decimal(str(value or 0)).quantize(CENT)


@hrms_bp.route("/admin/dashboard/hr-management/compensation", methods=["GET", "POST"])
@admin_required
def compensation():
    employees = Employee.query.order_by(Employee.name.asc()).all()
    if request.method == "POST":
        try:
            employee_id = int(request.form.get("employee_id", ""))
            employee = db.session.get(Employee, employee_id)
            if not employee:
                raise ValueError("Select a valid teacher/employee.")
            start = parse_date(request.form.get("effective_from"), "effective start date")
            end_raw = request.form.get("effective_to", "").strip()
            end = parse_date(end_raw, "effective end date") if end_raw else None
            if end and end < start:
                raise ValueError("Effective end date cannot be before the start date.")

            overlap = TeacherPaymentAgreement.query.filter(
                TeacherPaymentAgreement.employee_id == employee.id,
                TeacherPaymentAgreement.is_active.is_(True),
                TeacherPaymentAgreement.effective_from <= (end or date.max),
                db.or_(TeacherPaymentAgreement.effective_to.is_(None), TeacherPaymentAgreement.effective_to >= start),
            ).first()
            if overlap:
                raise ValueError("This teacher already has an active agreement overlapping the selected dates. Close the earlier agreement first.")

            share = money(request.form.get("revenue_share_percent", "0"))
            if share > Decimal("100"):
                raise ValueError("Revenue share must be between 0 and 100 percent.")

            agreement = TeacherPaymentAgreement(
                employee_id=employee.id,
                engagement_type=request.form.get("engagement_type", "Contractual").strip(),
                payment_model=request.form.get("payment_model", "Hybrid").strip(),
                monthly_retainer=money(request.form.get("monthly_retainer")),
                hourly_rate=money(request.form.get("hourly_rate")),
                per_class_rate=money(request.form.get("per_class_rate")),
                course_incentive_rate=money(request.form.get("course_incentive_rate")),
                revenue_share_percent=share,
                effective_from=start,
                effective_to=end,
                agreement_reference=request.form.get("agreement_reference", "").strip()[:120],
                notes=request.form.get("notes", "").strip(),
                created_by=current_user.id,
            )
            db.session.add(agreement)
            db.session.commit()
            flash("Payment agreement saved. Historical agreements remain unchanged.", "success")
        except (ValueError, TypeError) as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Could not save the payment agreement. Please retry.", "danger")
        return redirect(url_for("hrms.compensation"))

    agreements = TeacherPaymentAgreement.query.order_by(TeacherPaymentAgreement.created_at.desc()).all()
    return render_template("admin/hrms_compensation.html", employees=employees, agreements=agreements, today=date.today())


@hrms_bp.route("/admin/dashboard/hr-management/teaching-activity", methods=["GET", "POST"])
@admin_required
def teaching_activity():
    employees = Employee.query.order_by(Employee.name.asc()).all()
    if request.method == "POST":
        try:
            employee = db.session.get(Employee, int(request.form.get("employee_id", "")))
            if not employee:
                raise ValueError("Select a valid teacher.")
            activity_type = request.form.get("activity_type", "").strip().lower()
            if activity_type not in {"hourly", "class", "course", "revenue"}:
                raise ValueError("Select a supported activity type.")
            quantity = Decimal(str(request.form.get("quantity", "0"))).quantize(Decimal("0.001"))
            if not quantity.is_finite() or quantity <= 0:
                raise ValueError("Quantity must be greater than zero.")
            if activity_type == "revenue" and quantity < 0:
                raise ValueError("Revenue base cannot be negative.")
            activity = TeachingActivity(
                employee_id=employee.id,
                activity_date=parse_date(request.form.get("activity_date"), "activity date"),
                activity_type=activity_type,
                quantity=quantity,
                course_name=request.form.get("course_name", "").strip()[:160],
                reference=request.form.get("reference", "").strip()[:120],
                description=request.form.get("description", "").strip(),
                status="Pending",
                created_by=current_user.id,
            )
            db.session.add(activity)
            db.session.commit()
            flash("Teaching activity recorded and queued for verification.", "success")
        except (ValueError, TypeError, InvalidOperation) as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        return redirect(url_for("hrms.teaching_activity"))

    activities = TeachingActivity.query.order_by(TeachingActivity.activity_date.desc(), TeachingActivity.created_at.desc()).limit(300).all()
    return render_template("admin/hrms_activity.html", employees=employees, activities=activities)


@hrms_bp.post("/admin/dashboard/hr-management/teaching-activity/<int:activity_id>/verify")
@admin_required
def verify_teaching_activity(activity_id):
    activity = db.session.get(TeachingActivity, activity_id)
    if not activity:
        flash("Teaching activity not found.", "danger")
    elif activity.status != "Pending":
        flash("Only pending activity can be reviewed.", "warning")
    else:
        action = request.form.get("action")
        if action not in {"verify", "reject"}:
            flash("Invalid review action.", "danger")
        else:
            activity.status = "Verified" if action == "verify" else "Rejected"
            activity.verified_by = current_user.id
            activity.verified_at = datetime.utcnow()
            db.session.commit()
            flash(f"Activity {activity.status.lower()}.", "success")
    return redirect(url_for("hrms.teaching_activity"))


@hrms_bp.route("/admin/dashboard/hr-management/payroll-workflow", methods=["GET", "POST"])
@admin_required
def payroll_workflow():
    if request.method == "POST":
        try:
            month = int(request.form.get("month", ""))
            year = int(request.form.get("year", ""))
            if month < 1 or month > 12 or year < 2020 or year > 2100:
                raise ValueError("Select a valid payroll month and year.")
            start = date(year, month, 1)
            end = date(year, month, calendar.monthrange(year, month)[1])
            employees = Employee.query.filter_by(is_active=True).order_by(Employee.name.asc()).all()
            created = 0
            skipped = []
            for employee in employees:
                if PayrollPeriodLock.query.filter_by(employee_id=employee.id, period_start=start, period_end=end).first():
                    skipped.append(employee.display_name)
                    continue
                agreement = _agreement_for_period(employee.id, start, end)
                if not agreement:
                    continue

                # Monthly retainer is prorated only for a partial active period.
                active_start = max(start, agreement.effective_from, employee.joining_date or start)
                active_end = min(end, agreement.effective_to or end)
                active_days = max(0, (active_end - active_start).days + 1)
                month_days = (end - start).days + 1
                retainer = (Decimal(agreement.monthly_retainer or 0) * Decimal(active_days) / Decimal(month_days)).quantize(CENT, rounding=ROUND_HALF_UP) if active_days else Decimal("0.00")

                lines = []
                if retainer:
                    lines.append(("Monthly Retainer", Decimal(active_days), Decimal(agreement.monthly_retainer or 0) / Decimal(month_days), retainer))

                activities = TeachingActivity.query.filter(
                    TeachingActivity.employee_id == employee.id,
                    TeachingActivity.activity_date >= start,
                    TeachingActivity.activity_date <= end,
                    TeachingActivity.status == "Verified",
                ).order_by(TeachingActivity.activity_date.asc()).all()

                for item in activities:
                    rates = {
                        "hourly": Decimal(agreement.hourly_rate or 0),
                        "class": Decimal(agreement.per_class_rate or 0),
                        "course": Decimal(agreement.course_incentive_rate or 0),
                        "revenue": Decimal(agreement.revenue_share_percent or 0) / Decimal("100"),
                    }
                    rate = rates[item.activity_type]
                    amount = (Decimal(item.quantity or 0) * rate).quantize(CENT, rounding=ROUND_HALF_UP)
                    if amount:
                        label = {"hourly": "Teaching Hours", "class": "Completed Classes", "course": "Course Incentive", "revenue": "Revenue Share"}[item.activity_type]
                        lines.append((label, Decimal(item.quantity), rate, amount))

                gross = sum((line[3] for line in lines), Decimal("0.00")).quantize(CENT)
                run = PayrollRun(
                    employee_id=employee.id, period_start=start, period_end=end,
                    gross_pay=gross, allowances=Decimal("0.00"), deductions=Decimal("0.00"),
                    net_pay=gross, status="Draft",
                    remarks="Generated from active payment agreement and verified teaching activity.",
                )
                db.session.add(run)
                db.session.flush()
                db.session.add(PayrollPeriodLock(employee_id=employee.id, payroll_run_id=run.id, period_start=start, period_end=end))
                created += 1

            db.session.commit()
            flash(f"Payroll generation completed: {created} created, {len(skipped)} already existed. Teachers without an active agreement were skipped.", "success")
        except (ValueError, TypeError, InvalidOperation) as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        except IntegrityError:
            db.session.rollback()
            flash("A payroll for this teacher and period already exists. Refresh and review the payroll list.", "warning")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Payroll generation failed safely. No partial payroll batch was committed.", "danger")
        return redirect(url_for("hrms.payroll_workflow"))

    runs = PayrollRun.query.order_by(PayrollRun.period_start.desc(), PayrollRun.created_at.desc()).limit(300).all()
    approvals = {run.id: _approval_map(run) for run in runs}
    payments = {run.id: _paid_total(run) for run in runs}
    return render_template(
        "admin/hrms_payroll_workflow.html", payroll_runs=runs, approvals=approvals,
        paid_totals=payments, today=date.today(), automated_payout_ready=False,
    )


@hrms_bp.post("/admin/dashboard/hr-management/payroll/<int:run_id>/adjustment")
@admin_required
def payroll_adjustment(run_id):
    run = db.session.get(PayrollRun, run_id)
    if not run or run.status != "Draft":
        flash("Only draft payroll can be adjusted.", "warning")
        return redirect(url_for("hrms.payroll_workflow"))
    try:
        adjustment_type = request.form.get("adjustment_type", "")
        if adjustment_type not in {"Allowance", "Deduction"}:
            raise ValueError("Select Allowance or Deduction.")
        amount = money(request.form.get("amount"))
        reason = request.form.get("reason", "").strip()
        if amount <= 0 or not reason:
            raise ValueError("Enter a positive amount and a reason.")
        db.session.add(PayrollAdjustment(
            employee_id=run.employee_id, payroll_run_id=run.id,
            adjustment_type=adjustment_type, amount=amount, reason=reason,
        ))
        if adjustment_type == "Allowance":
            run.allowances = Decimal(run.allowances or 0) + amount
        else:
            run.deductions = Decimal(run.deductions or 0) + amount
        run.net_pay = run.calculate_net_pay()
        db.session.commit()
        flash("Payroll adjustment saved.", "success")
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    return redirect(url_for("hrms.payroll_workflow"))


@hrms_bp.post("/admin/dashboard/hr-management/payroll/<int:run_id>/approval")
@admin_required
def payroll_approval(run_id):
    run = db.session.get(PayrollRun, run_id)
    if not run:
        flash("Payroll record not found.", "danger")
        return redirect(url_for("hrms.payroll_workflow"))

    stage = request.form.get("stage", "")
    action = request.form.get("action", "")
    remarks = request.form.get("remarks", "").strip()
    order = ["HR", "Accounts", "Founder"]
    if stage not in order or action not in {"approve", "reject"}:
        flash("Invalid approval action.", "danger")
        return redirect(url_for("hrms.payroll_workflow"))

    latest = _approval_map(run)
    idx = order.index(stage)
    previous = latest.get(order[idx - 1]) if idx else None
    if idx and (not previous or previous.status != "Approved"):
        flash(f"{order[idx - 1]} approval is required first.", "warning")
        return redirect(url_for("hrms.payroll_workflow"))
    if stage == "Founder" and not getattr(current_user, "is_super_admin", False):
        flash("Only the Founder/Super Admin can provide final payroll approval.", "danger")
        return redirect(url_for("hrms.payroll_workflow"))
    if stage == "Accounts":
        hr_approval = latest.get("HR")
        if hr_approval and hr_approval.approver_id == current_user.id:
            flash("Accounts verification must be completed by a different authorized user than HR verification.", "danger")
            return redirect(url_for("hrms.payroll_workflow"))
    if stage == "HR" and run.status != "Draft":
        flash("HR verification is available only for draft payroll.", "warning")
        return redirect(url_for("hrms.payroll_workflow"))
    if stage == "Accounts" and run.status != "Pending Accounts Review":
        flash("Payroll is not awaiting Accounts verification.", "warning")
        return redirect(url_for("hrms.payroll_workflow"))
    if stage == "Founder" and run.status != "Pending Founder Approval":
        flash("Payroll is not awaiting Founder approval.", "warning")
        return redirect(url_for("hrms.payroll_workflow"))

    db.session.add(PayrollApproval(
        payroll_run_id=run.id, stage=stage,
        status="Approved" if action == "approve" else "Rejected",
        approver_id=current_user.id, remarks=remarks,
    ))
    if action == "reject":
        run.status = "Rejected"
    elif stage == "HR":
        run.status = "Pending Accounts Review"
    elif stage == "Accounts":
        run.status = "Pending Founder Approval"
    else:
        run.status = "Approved"
    db.session.commit()
    flash(f"{stage} {action}d successfully.", "success")
    return redirect(url_for("hrms.payroll_workflow"))


@hrms_bp.post("/admin/dashboard/hr-management/payroll/<int:run_id>/payment")
@admin_required
def payroll_payment(run_id):
    run = db.session.get(PayrollRun, run_id)
    if not run or run.status not in {"Approved", "Partially Paid"}:
        flash("Only Founder-approved payroll can be paid.", "warning")
        return redirect(url_for("hrms.payroll_workflow"))
    try:
        method = request.form.get("method", "Manual Bank Transfer")
        if method not in {"Manual Bank Transfer", "UPI", "NEFT", "IMPS", "RTGS"}:
            raise ValueError("Automated payout is not enabled until a verified payout provider is configured.")
        amount = money(request.form.get("amount"))
        reference = request.form.get("transaction_reference", "").strip()
        if amount <= 0 or not reference:
            raise ValueError("Enter a positive payment amount and transaction reference.")
        if PayrollPayment.query.filter_by(transaction_reference=reference).first():
            raise ValueError("This transaction reference has already been recorded.")
        outstanding = Decimal(run.net_pay or 0) - _paid_total(run)
        if amount > outstanding:
            raise ValueError("Payment amount cannot exceed the outstanding payroll balance.")
        db.session.add(PayrollPayment(
            payroll_run_id=run.id, method=method, amount=amount,
            status="Paid", transaction_reference=reference,
            proof_url=request.form.get("proof_url", "").strip()[:255],
            remarks=request.form.get("remarks", "").strip(),
            processed_by=current_user.id,
        ))
        db.session.flush()
        new_paid = _paid_total(run) + amount
        run.status = "Paid" if new_paid >= Decimal(run.net_pay or 0) else "Partially Paid"
        db.session.commit()
        flash("Payment transaction recorded. Reconcile the reference against the bank/UPI statement.", "success")
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        flash(str(exc), "danger")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Payment record could not be saved.", "danger")
    return redirect(url_for("hrms.payroll_workflow"))


@hrms_bp.get("/teacher/hr/earnings")
@teacher_required
def teacher_earnings():
    employee = current_user.employee_profile
    if not employee:
        flash("No employee profile is linked to your account yet. Contact admin.", "warning")
        return redirect(url_for("teacher.dashboard"))
    agreements = TeacherPaymentAgreement.query.filter_by(employee_id=employee.id, is_active=True).order_by(TeacherPaymentAgreement.effective_from.desc()).all()
    runs = PayrollRun.query.filter_by(employee_id=employee.id).order_by(PayrollRun.period_start.desc()).all()
    disputes = PayrollDispute.query.filter_by(employee_id=employee.id).order_by(PayrollDispute.created_at.desc()).all()
    return render_template("teacher/hrms_earnings.html", employee=employee, agreements=agreements, payroll_runs=runs, disputes=disputes)


@hrms_bp.post("/teacher/hr/payroll/<int:run_id>/dispute")
@teacher_required
def teacher_payroll_dispute(run_id):
    employee = current_user.employee_profile
    if not employee:
        flash("No employee profile is linked to your account.", "warning")
        return redirect(url_for("teacher.dashboard"))
    run = PayrollRun.query.filter_by(id=run_id, employee_id=employee.id).first()
    if not run:
        flash("Payroll record not found.", "danger")
        return redirect(url_for("hrms.teacher_earnings"))
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    if not category or not description:
        flash("Select an issue category and describe the discrepancy.", "danger")
    else:
        db.session.add(PayrollDispute(employee_id=employee.id, payroll_run_id=run.id, category=category[:50], description=description))
        db.session.commit()
        flash("Payroll discrepancy submitted for HR and Accounts review.", "success")
    return redirect(url_for("hrms.teacher_earnings"))
