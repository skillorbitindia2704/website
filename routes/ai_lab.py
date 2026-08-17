"""AI / Robotics lab setup page for schools and colleges."""

from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError

from models import db
from models.ai_lab_inquiry import AILabInquiry
from models.ai_lab_package import AILabPackage
from models.ai_lab_hardware import AILabHardwareItem
from models.ai_lab_curriculum import AILabCurriculumBlock
from models.ai_lab_project import AILabProject
from models.ai_lab_testimonial import AILabTestimonial
from models.ai_lab_faq import AILabFAQ
from models.ai_lab_brochure import AILabBrochure
from models.ai_lab_gallery import AILabGalleryImage

ai_lab_bp = Blueprint("ai_lab", __name__)


@ai_lab_bp.get("/")
def index():
    packages = (
        AILabPackage.query.filter_by(is_active=1)
        .order_by(AILabPackage.display_order.asc(), AILabPackage.id.asc())
        .all()
    )

    hardware_items = (
        AILabHardwareItem.query.filter_by(is_active=True)
        .order_by(AILabHardwareItem.display_order.asc(), AILabHardwareItem.id.asc())
        .all()
    )

    curriculum_blocks = (
        AILabCurriculumBlock.query.filter_by(is_active=True)
        .order_by(AILabCurriculumBlock.display_order.asc(), AILabCurriculumBlock.id.asc())
        .all()
    )

    projects = (
        AILabProject.query.filter_by(is_active=True)
        .order_by(AILabProject.display_order.asc(), AILabProject.id.asc())
        .all()
    )

    testimonials = (
        AILabTestimonial.query.filter_by(is_active=True)
        .order_by(AILabTestimonial.display_order.asc(), AILabTestimonial.id.asc())
        .all()
    )

    faqs = (
        AILabFAQ.query.filter_by(is_active=True)
        .order_by(AILabFAQ.display_order.asc(), AILabFAQ.id.asc())
        .all()
    )

    brochure = (
        AILabBrochure.query.filter_by(is_active=True)
        .order_by(AILabBrochure.created_at.desc(), AILabBrochure.id.desc())
        .first()
    )

    gallery_images = (
        AILabGalleryImage.query.filter_by(is_active=True)
        .order_by(AILabGalleryImage.display_order.asc(), AILabGalleryImage.id.asc())
        .all()
    )

    return render_template(
        "ai_lab/index.html",
        packages=packages,
        hardware_items=hardware_items,
        curriculum_blocks=curriculum_blocks,
        projects=projects,
        testimonials=testimonials,
        faqs=faqs,
        brochure=brochure,
        gallery_images=gallery_images,
    )


@ai_lab_bp.post("/inquiry")
def inquiry():
    institution = request.form.get("institution_name", "").strip()
    contact = request.form.get("contact_person", "").strip()
    phone = request.form.get("phone", "").strip()
    email_raw = request.form.get("email", "").strip().lower()
    package_interest = request.form.get("package_interest", "").strip() or "undecided"
    city = request.form.get("city", "").strip()
    lab_type = request.form.get("lab_type", "").strip()
    budget_range = request.form.get("budget_range", "").strip()
    requirements = request.form.get("requirements", "").strip()
    message = request.form.get("message", "").strip()
    # For the new marketing form we store the same text in `message`,
    # but older forms may still submit into `requirements`.
    effective_requirements = requirements or message

    if len(institution) < 3:
        flash("Please enter the school or college name.", "danger")
        return redirect(url_for("ai_lab.index"))
    if len(contact) < 2:
        flash("Please enter a contact person name.", "danger")
        return redirect(url_for("ai_lab.index"))
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 10:
        flash("Please enter a valid phone number.", "danger")
        return redirect(url_for("ai_lab.index"))
    try:
        email = validate_email(email_raw, check_deliverability=False).normalized
    except EmailNotValidError:
        flash("Please enter a valid email.", "danger")
        return redirect(url_for("ai_lab.index"))
    
    allowed_pkg_ids = {str(p.id) for p in AILabPackage.query.all()} | {"undecided"}
    if package_interest not in allowed_pkg_ids:
        package_interest = "undecided"

    # lab_type is an optional richer field; fall back to package interest if not provided.
    if not lab_type:
        lab_type = package_interest if package_interest != "undecided" else ""
    
    if len(effective_requirements) < 15:
        flash("Please share a short description of your requirements (15+ characters).", "warning")
        return redirect(url_for("ai_lab.index"))

    # If a dedicated message field exists, prefer it; otherwise keep requirements only.
    if not message:
        message = ""

    row = AILabInquiry(
        institution_name=institution,
        city=city,
        contact_person=contact,
        phone=phone,
        email=email,
        package_interest=package_interest,
        lab_type=lab_type,
        budget_range=budget_range,
        requirements=effective_requirements,
        message=message,
        status="new",
    )
    try:
        db.session.add(row)
        db.session.commit()
        flash("Inquiry received — our academic partnerships team will contact you.", "success")
        return redirect(url_for("ai_lab.index"))
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("Failed to save inquiry. Please try again.", "danger")
        return redirect(url_for("ai_lab.index"))
