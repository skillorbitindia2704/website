import os
from uuid import uuid4

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from werkzeug.utils import secure_filename
from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError

from models import db
from models.internship import Internship, InternshipApplication, InternshipProgramPayment
from utils.decorators import login_required
from utils.notifications import notify_user
from utils.payments import create_razorpay_order, verify_razorpay_signature
from utils.security_helpers import rate_limit

internships_bp = Blueprint("internships", __name__)
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


def _is_allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _listing_open_filter():
    return (
        Internship.is_active.is_(True),
        Internship.is_visible.is_(True),
        Internship.listing_status == "active",
    )


@internships_bp.get("/")
def listing():
    internships = (
        Internship.query.filter(*_listing_open_filter())
        .order_by(desc(Internship.is_featured), desc(Internship.created_at))
        .all()
    )
    return render_template("internships/listing.html", internships=internships)


@internships_bp.post("/apply/<int:internship_id>")
@login_required
def apply(internship_id):
    internship = Internship.query.get_or_404(internship_id)
    if (
        not internship.is_active
        or not internship.is_visible
        or (internship.listing_status or "").lower() != "active"
    ):
        flash("This internship is not accepting applications.", "warning")
        return redirect(url_for("internships.listing"))
    resume = request.files.get("resume")
    cover_letter = request.form.get("cover_letter", "").strip()
    from utils.security_helpers import validate_file_safety
    if not resume or not resume.filename or not validate_file_safety(resume, ALLOWED_EXTENSIONS):
        flash("Upload a valid resume (pdf/doc/docx strictly expected).", "danger")
        return redirect(url_for("internships.listing"))
    
    # Check file size before saving
    resume.seek(0, os.SEEK_END)
    file_size = resume.tell()
    resume.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        flash(f"Resume file is too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB.", "danger")
        return redirect(url_for("internships.listing"))
    
    try:
        safe_name = secure_filename(resume.filename)
        file_name = f"{uuid4()}_{safe_name}"
        upload_dir = current_app.config["UPLOAD_FOLDER"]
        os.makedirs(upload_dir, exist_ok=True)
        output_path = os.path.join(upload_dir, file_name)
        resume.save(output_path)
    except (OSError, IOError):
        flash("Failed to save resume file. Please try again.", "danger")
        return redirect(url_for("internships.listing"))
    
    resume_path = f"/static/uploads/resumes/{file_name}"
    fee_record = internship.program_fee_record
    program_fee = int(fee_record.fee_inr or 0) if fee_record else 0

    if program_fee > 0:
        # Save an auditable pending payment; an application is created only after
        # Razorpay signature verification succeeds.
        rp_order = create_razorpay_order(program_fee, f"internship_{internship.id}_user_{current_user.id}_{uuid4().hex[:12]}")
        if not rp_order or not rp_order.get("id"):
            try:
                os.remove(output_path)
            except OSError:
                pass
            flash("Online payment is unavailable right now. Please try again later.", "danger")
            return redirect(url_for("internships.listing"))
        try:
            payment = InternshipProgramPayment(
                internship_id=internship.id,
                user_id=current_user.id,
                amount_inr=program_fee,
                resume_path=resume_path,
                cover_letter=cover_letter,
                status="payment_pending",
                razorpay_order_id=rp_order["id"],
            )
            db.session.add(payment)
            db.session.commit()
            return redirect(url_for("internships.pay_program", payment_id=payment.id))
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Could not save internship payment record for internship %s", internship.id)
            flash("Could not start the application. Please try again.", "danger")
            return redirect(url_for("internships.listing"))

    try:
        app_item = InternshipApplication(
            internship_id=internship.id,
            user_id=current_user.id,
            cover_letter=cover_letter,
            resume_path=resume_path,
        )
        db.session.add(app_item)
        db.session.commit()
        notify_user(current_user.id, f"Application submitted for {internship.title}. We'll notify you when reviewed.")
        flash("Application submitted.", "success")
        return redirect(url_for("dashboard.index"))
    except SQLAlchemyError:
        db.session.rollback()
        try:
            os.remove(output_path)
        except OSError:
            pass
        flash("Failed to save application. Please try again.", "danger")
        return redirect(url_for("internships.listing"))


@internships_bp.get("/pay-program/<int:payment_id>")
@login_required
def pay_program(payment_id):
    payment = InternshipProgramPayment.query.get_or_404(payment_id)
    if payment.user_id != current_user.id:
        flash("You cannot access this payment.", "danger")
        return redirect(url_for("internships.listing"))
    if payment.status == "paid":
        return redirect(url_for("dashboard.index"))
    return render_template(
        "internships/payment.html",
        payment=payment,
        razorpay_key_id=current_app.config.get("RAZORPAY_KEY_ID", ""),
    )


@internships_bp.post("/verify-program-payment/<int:payment_id>")
@login_required
@rate_limit(limit=5, period=60)
def verify_program_payment(payment_id):
    payment = InternshipProgramPayment.query.get_or_404(payment_id)
    if payment.user_id != current_user.id:
        return "Unauthorized", 403

    order_id = (request.form.get("razorpay_order_id") or "").strip()
    payment_id_gateway = (request.form.get("razorpay_payment_id") or "").strip()
    signature = (request.form.get("razorpay_signature") or "").strip()
    if payment.status == "paid":
        flash("This internship payment is already verified.", "success")
        return redirect(url_for("dashboard.index"))
    if not order_id or not payment_id_gateway or not signature or order_id != payment.razorpay_order_id:
        flash("Payment details could not be verified. Please try again.", "danger")
        return redirect(url_for("internships.pay_program", payment_id=payment.id))
    if not verify_razorpay_signature(order_id, payment_id_gateway, signature):
        payment.status = "failed_signature"
        db.session.commit()
        flash("Payment verification failed. No application was submitted.", "danger")
        return redirect(url_for("internships.pay_program", payment_id=payment.id))

    try:
        # Idempotency: never create a second application for the same verified payment.
        existing = InternshipProgramPayment.query.filter_by(razorpay_payment_id=payment_id_gateway).first()
        if existing and existing.id != payment.id:
            flash("This payment reference has already been used.", "danger")
            return redirect(url_for("internships.listing"))
        application = InternshipApplication(
            internship_id=payment.internship_id,
            user_id=payment.user_id,
            cover_letter=payment.cover_letter,
            resume_path=payment.resume_path,
            status="pending",
        )
        db.session.add(application)
        db.session.flush()
        payment.application_id = application.id
        payment.razorpay_payment_id = payment_id_gateway
        payment.status = "paid"
        db.session.commit()
        notify_user(current_user.id, f"Payment verified and application submitted for {payment.internship.title}. We'll notify you when reviewed.")
        flash("Payment successful! Your internship application has been submitted.", "success")
        return redirect(url_for("dashboard.index"))
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not finalize paid internship application %s", payment.id)
        flash("Payment was received but application finalization failed. Please contact support with payment reference.", "danger")
        return redirect(url_for("internships.pay_program", payment_id=payment.id))
