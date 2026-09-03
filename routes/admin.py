import os
import csv
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import StringIO
import re
from uuid import uuid4

from typing import Tuple
from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for, Response, jsonify
from flask_login import current_user
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from werkzeug.utils import secure_filename

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
from models.course import Certificate, Course, Enrollment
from models.course_cert_highlight import CourseCertHighlight
from models.course_learning_path import CourseLearningPath
from models.course_showcase_project import CourseShowcaseProject
from models.courses_page_content import CoursesPageContent
from models.internship import Internship, InternshipApplication
from models.service_request import ServiceRequest
from models.service_package import ServicePackage
from models.event import Event
from models.homepage_testimonial import HomeTestimonial
from models.about_content import AboutContent
from models.about_team import AboutTeamMember
from models.about_timeline import AboutTimelineEntry
from models.about_gallery import AboutGalleryImage
from models.about_partner import AboutPartnerLogo
from models.about_recognition import AboutRecognition
from models.about_counter import AboutCounter
from models.about_testimonial import AboutTestimonial
from models.about_version import AboutVersion
from models.about_activity import AboutActivityLog
from models.site_setting import SiteSetting
from models.store import Order, OrderItem, Product
from models.user import User
from models.wishlist import WishlistItem
from models.hr import Employee, AttendanceRecord, LeaveRequest, AttendanceCorrectionRequest, AttendanceAuditLog
from models.payroll import PayrollRun, PayrollAdjustment, PayrollPayslip
from models.homepage_hero import HomePageHero
from models.homepage_content import HomeContent
from models.homepage_version import HomeVersion
from models.homepage_activity import HomeActivityLog
from extensions import bcrypt
from utils.certificates import generate_certificate_pdf
from utils.role_auth import admin_required
from utils.notifications import notify_user

admin_bp = Blueprint("admin", __name__)


def _date_range(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


@admin_bp.after_request
def log_admin_activity(response):
    if request.method in ("POST", "PUT", "DELETE"):
        from flask_login import current_user
        if current_user and getattr(current_user, "is_authenticated", False) and getattr(current_user, "role", None) == "admin":
            path = request.path
            target_table = "unknown"
            target_id = None
            
            if "/products" in path:
                target_table = "product"
            elif "/courses" in path:
                target_table = "course"
            elif "/internships" in path or "/internship-application" in path:
                target_table = "internship"
            elif "/site-settings" in path or "/website-branding" in path:
                target_table = "site_setting"
            elif "/users" in path or "/teachers" in path:
                target_table = "user"
            elif "/events" in path:
                target_table = "events"
            
            id_match = re.search(r'/(\d+)(?:/|$)', path)
            if id_match:
                target_id = int(id_match.group(1))
                
            form_data = {}
            if request.form:
                for k, v in request.form.items():
                    if any(sensitive in k.lower() for sensitive in ("password", "secret", "csrf_token", "key")):
                        form_data[k] = "[SCRUBBED]"
                    else:
                        form_data[k] = v
                        
            action_type = "edit"
            if "delete" in path:
                action_type = "delete"
            elif "create" in path or "add" in path:
                action_type = "create"
            elif request.method == "POST" and not id_match:
                action_type = "create"
                
            details = f"Endpoint: {request.endpoint}, Path: {path}, Status: {response.status_code}, Form: {form_data}"
            
            from models.user import AdminActivityLog
            try:
                activity = AdminActivityLog(
                    admin_id=current_user.id,
                    action_type=action_type,
                    target_table=target_table,
                    target_id=target_id,
                    details=details[:1000],
                    ip_address=request.headers.get("X-Forwarded-For", request.remote_addr or "")
                )
                db.session.add(activity)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Failed to log admin activity: {e}")
                
    return response


ALLOWED_PRODUCT_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
ORDER_STATUSES = ["Pending", "Accepted", "Rejected", "Shipped", "Delivered"]

BRANDING_DIR_REL = os.path.join("images", "branding")
MAX_BRANDING_UPLOAD_MB = 5
MAX_BRANDING_UPLOAD_BYTES = MAX_BRANDING_UPLOAD_MB * 1024 * 1024
ALLOWED_LOGO_EXTS = {"png", "jpg", "jpeg", "svg", "webp"}
ALLOWED_FAVICON_EXTS = {"png", "jpg", "jpeg", "svg", "webp"}

KEY_LOGO = "logo_url"
KEY_DARK_LOGO = "dark_logo_url"
KEY_FAVICON = "favicon_url"

KIND_TO_KEY = {
    "logo": KEY_LOGO,
    "dark_logo": KEY_DARK_LOGO,
    "favicon": KEY_FAVICON,
}

KIND_TO_DEFAULT_PATH = {
    "logo": "images/skill-orbit-logo.png",
    "dark_logo": "images/skill-orbit-logo.png",
    "favicon": "images/skill-orbit-logo.png",
}

def _allowed_branding_file(filename: str, *, allowed_exts: set[str]) -> Tuple[bool, str]:
    if not filename or "." not in filename:
        return False, "Invalid file name."
    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in allowed_exts:
        allowed = ", ".join(sorted(allowed_exts))
        return False, f"Allowed file types: {allowed}."
    return True, ""

def _save_branding_upload(file_storage, *, kind: str) -> str:
    if not file_storage or not getattr(file_storage, "filename", None):
        raise ValueError("No file uploaded.")

    filename = secure_filename(file_storage.filename)
    if not filename:
        raise ValueError("Invalid file name.")

    allowed_exts = (
        ALLOWED_LOGO_EXTS
        if kind in {"logo", "dark_logo"}
        else ALLOWED_FAVICON_EXTS
    )

    ok, err = _allowed_branding_file(
        filename,
        allowed_exts=allowed_exts,
    )

    if not ok:
        raise ValueError(err)

    if (
        hasattr(file_storage, "content_length")
        and file_storage.content_length is not None
    ):
        if int(file_storage.content_length) > MAX_BRANDING_UPLOAD_BYTES:
            raise ValueError("File too large. Max size is 5MB.")

    public_id = f"branding/{kind}_{uuid4().hex}"

    try:
        import cloudinary.uploader

        result = cloudinary.uploader.upload(
            file_storage,
            public_id=public_id,
            resource_type="image",
            overwrite=False,
            invalidate=True,
        )

        secure_url = result.get("secure_url")

        if not secure_url:
            raise RuntimeError(
                "Cloudinary did not return an image URL."
            )

        return secure_url

    except Exception as exc:
        current_app.logger.exception(
            f"Cloudinary branding upload failed for {kind}: {exc}"
        )
        raise ValueError(
            "Could not upload branding image. Please try again."
        )


def _branding_static_url(rel_path: str) -> str:
    if not rel_path:
        return ""

    if rel_path.startswith(("http://", "https://")):
        return rel_path

    return url_for("static", filename=rel_path)

def _branding_static_url(rel_path: str) -> str:
    if not rel_path:
        return ""

    if rel_path.startswith(("http://", "https://")):
        return rel_path

    return url_for("static", filename=rel_path)


def _slugify_package_title(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (title or "").strip().lower()).strip("-")
    return base or f"package-{uuid4().hex[:8]}"


def _slugify_service_title(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (title or "").strip().lower()).strip("-")
    return base or f"service-{uuid4().hex[:8]}"


def _setting_get(key: str, default: str = "") -> str:
    row = SiteSetting.query.filter_by(key=key).first()
    if not row:
        return default
    return row.value or default


def _setting_set(key: str, value: str):
    row = SiteSetting.query.filter_by(key=key).first()
    if not row:
        row = SiteSetting(key=key, value=value or "")
        db.session.add(row)
    else:
        row.value = value or ""


def _upload_product_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    safe_name = secure_filename(file_storage.filename)
    if "." not in safe_name:
        raise ValueError("Invalid image file.")
    ext = safe_name.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_PRODUCT_IMAGE_EXTENSIONS:
        raise ValueError("Allowed image formats: png, jpg, jpeg, webp, gif.")
    
    upload_rel_dir = os.path.join("uploads", "products")
    upload_abs_dir = os.path.join(current_app.static_folder, upload_rel_dir)
    os.makedirs(upload_abs_dir, exist_ok=True)
    
    # Generate unique filename with .webp extension
    base_name = safe_name.rsplit(".", 1)[0]
    unique_name = f"{uuid4().hex}_{base_name}.webp"
    abs_path = os.path.join(upload_abs_dir, unique_name)
    
    try:
        from PIL import Image
        img = Image.open(file_storage)
        # Convert to RGB/RGBA as needed and save as WebP with 85% quality
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img.save(abs_path, "WEBP", quality=85)
        else:
            img.convert("RGB").save(abs_path, "WEBP", quality=85)
    except Exception as e:
        # Fallback to standard save if Pillow conversion fails
        current_app.logger.warning(f"WebP compression failed, saving original: {e}")
        unique_name = f"{uuid4().hex}_{safe_name}"
        abs_path = os.path.join(upload_abs_dir, unique_name)
        file_storage.seek(0)
        file_storage.save(abs_path)
        
    return f"{upload_rel_dir.replace(os.sep, '/')}/{unique_name}"


def _upload_hero_image(file_storage):
    """Upload images for homepage hero section."""
    if not file_storage or not file_storage.filename:
        return None
    safe_name = secure_filename(file_storage.filename)
    if "." not in safe_name:
        raise ValueError("Invalid image file.")
    ext = safe_name.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_PRODUCT_IMAGE_EXTENSIONS:
        raise ValueError("Allowed image formats: png, jpg, jpeg, webp, gif.")
    upload_rel_dir = os.path.join("uploads", "homepage")
    upload_abs_dir = os.path.join(current_app.static_folder, upload_rel_dir)
    os.makedirs(upload_abs_dir, exist_ok=True)
    unique_name = f"{uuid4().hex}_{safe_name}"
    abs_path = os.path.join(upload_abs_dir, unique_name)
    file_storage.save(abs_path)
    return f"{upload_rel_dir.replace(os.sep, '/')}/{unique_name}"


@admin_bp.get("/")
@admin_bp.get("/dashboard")
@admin_required
def index():
    stats = {
        "users": User.query.count(),
        "orders": Order.query.count(),
        "courses": Course.query.count(),
        "service_requests": ServiceRequest.query.count(),
        "ai_lab_inquiries": AILabInquiry.query.count(),
        "ai_lab_packages": AILabPackage.query.count(),
    }
    return render_template("admin/index.html", stats=stats)


def _render_admin_module_page(title: str, description: str, features: list):
    crumbs = [
        ("Home", url_for("main.home")),
        ("Admin", url_for("admin.index")),
        (title, None),
    ]
    return render_template(
        "admin/module_group.html",
        page_title=title,
        page_description=description,
        module_features=features,
        breadcrumbs=crumbs,
    )


@admin_bp.get("/dashboard/content-management")
@admin_required
def content_management():
    features = [
        {
            "title": "Homepage Manager",
            "url": url_for("admin.homepage_manager"),
            "description": "Manage homepage hero, sections, stats, reviews, and public SEO content.",
            "icon": "🏠",
        },
        {
            "title": "About Page Manager",
            "url": url_for("admin.about_manager"),
            "description": "Publish About page stories, team, timeline, partners, testimonials, counters, and recognition.",
            "icon": "📘",
        },
        {
            "title": "Courses Page Copy",
            "url": url_for("admin.courses_page_content"),
            "description": "Edit hero copy, meta tags, and course page messaging for conversions.",
            "icon": "📝",
        },
        {
            "title": "Learning Paths",
            "url": url_for("admin.course_learning_paths"),
            "description": "Build and update structured course learning paths on the public courses page.",
            "icon": "🧭",
        },
        {
            "title": "Project Showcase",
            "url": url_for("admin.course_showcase_projects"),
            "description": "Share student showcase projects and portfolio highlights on course pages.",
            "icon": "💡",
        },
        {
            "title": "Certificate Highlights",
            "url": url_for("admin.course_cert_highlights"),
            "description": "Manage certification trust signals displayed across course landing pages.",
            "icon": "🎖️",
        },
        {
            "title": "Website Branding",
            "url": url_for("admin.website_branding"),
            "description": "Update logo, dark logo, and favicon for consistent brand presence.",
            "icon": "🎨",
        },
        {
            "title": "Site Settings",
            "url": url_for("admin.site_settings"),
            "description": "Configure contact details, social links, maps, and website footer settings.",
            "icon": "⚙️",
        },
    ]
    return _render_admin_module_page("Content Management", "A modern content operations center for your homepage, about page, courses content and branding.", features)


@admin_bp.get("/dashboard/academic-management")
@admin_required
def academic_management():
    features = [
        {
            "title": "Courses",
            "url": url_for("admin.courses"),
            "description": "Create, publish, and maintain course catalog entries and pricing.",
            "icon": "📚",
        },
        {
            "title": "Certificates",
            "url": url_for("admin.issue_certificate"),
            "description": "Issue PDF certificates and verify learner achievements.",
            "icon": "📜",
        },
        {
            "title": "Internships",
            "url": url_for("admin.internships"),
            "description": "Manage internship listings, applications, approvals, and status flows.",
            "icon": "💼",
        },
        {
            "title": "Manage Teachers",
            "url": url_for("admin.teachers"),
            "description": "Approve, reject, and oversee teacher account access to the platform.",
            "icon": "👩‍🏫",
        },
        {
            "title": "Students (Future Ready)",
            "url": url_for("admin.users"),
            "description": "Prepare student account reporting and learner segmentation with existing user management.",
            "icon": "👨‍🎓",
        },
    ]
    return _render_admin_module_page("Academic Management", "Course, certificate, internship and teacher operations for your learning platform.", features)


@admin_bp.get("/dashboard/store-management")
@admin_required
def store_management():
    features = [
        {
            "title": "Store Manager CMS",
            "url": url_for("admin.store_manager"),
            "description": "Unified ecommerce operations view with product, category, order, coupon, review, and SEO workflows.",
            "icon": "🏬",
        },
        {
            "title": "Products",
            "url": url_for("admin.store_manager") + "#products",
            "description": "Manage product catalog, pricing, stock, and marketing metadata.",
            "icon": "📦",
        },
        {
            "title": "Categories",
            "url": url_for("admin.store_manager") + "#categories",
            "description": "Organize product channels with categories, subcategories, and visual banners.",
            "icon": "📂",
        },
        {
            "title": "Orders",
            "url": url_for("admin.store_manager") + "#orders",
            "description": "Review order history, update status, and track customer shipments.",
            "icon": "🚚",
        },
        {
            "title": "Coupons",
            "url": url_for("admin.store_manager") + "#coupons",
            "description": "Launch and manage coupon campaigns for promotions and discounts.",
            "icon": "🎫",
        },
        {
            "title": "Reviews",
            "url": url_for("admin.store_manager") + "#reviews",
            "description": "Moderate customer reviews and maintain product quality signals.",
            "icon": "⭐",
        },
        {
            "title": "SEO",
            "url": url_for("admin.store_manager") + "#products",
            "description": "Maintain product SEO metadata for search and discovery.",
            "icon": "🔍",
        },
    ]
    return _render_admin_module_page("Store Management", "Handle product catalog, orders, coupons, reviews, categories and store SEO from a single store operations page.", features)


@admin_bp.get("/dashboard/ai-lab-management")
@admin_required
def ai_lab_management():
    features = [
        {
            "title": "AI Lab CMS",
            "url": url_for("admin.ai_lab_hardware"),
            "description": "Manage AI lab hardware, curriculum, projects, testimonials and gallery content.",
            "icon": "🧠",
        },
        {
            "title": "AI Lab Packages",
            "url": url_for("admin.ai_lab_packages"),
            "description": "Create and maintain packaged AI lab offerings for institutions.",
            "icon": "📦",
        },
        {
            "title": "AI Lab Leads",
            "url": url_for("admin.ai_lab_inquiries"),
            "description": "Review incoming AI lab inquiry leads and update their status.",
            "icon": "📩",
        },
        {
            "title": "Hardware",
            "url": url_for("admin.ai_lab_hardware"),
            "description": "Update hardware inventory items, descriptions, and featured lab equipment.",
            "icon": "🔧",
        },
        {
            "title": "Curriculum",
            "url": url_for("admin.ai_lab_curriculum"),
            "description": "Manage course blocks, learning outcomes, and AI lab training modules.",
            "icon": "📘",
        },
        {
            "title": "Projects",
            "url": url_for("admin.ai_lab_projects"),
            "description": "Publish student lab projects that showcase outcomes and technology use cases.",
            "icon": "🚀",
        },
    ]
    return _render_admin_module_page("AI Lab Management", "Centralize all AI lab content, packages, leads and project workflows into one enterprise module.", features)


@admin_bp.get("/dashboard/business-management")
@admin_required
def business_management():
    features = [
        {
            "title": "Service Enquiries",
            "url": url_for("admin.service_requests"),
            "description": "Review incoming service leads and update inquiry status.",
            "icon": "💬",
        },
        {
            "title": "AI Lab Enquiries",
            "url": url_for("admin.ai_lab_inquiries"),
            "description": "Manage institution inquiries for AI lab installations and partnerships.",
            "icon": "📨",
        },
        {
            "title": "Contact Messages",
            "url": url_for("admin.service_requests"),
            "description": "Track and respond to inbound business contact leads from the public site.",
            "icon": "📥",
        },
        {
            "title": "Analytics",
            "url": url_for("admin.index"),
            "description": "View platform performance metrics and top-level business signals.",
            "icon": "📈",
        },
        {
            "title": "Reports",
            "url": url_for("admin.store_manager"),
            "description": "Access store and sales reports through the store operations dashboard.",
            "icon": "📊",
        },
    ]
    return _render_admin_module_page("Business Management", "Monitor leads, inquiries, analytics signals, and business reports from one executive module.", features)


@admin_bp.get("/dashboard/hr-management")
@admin_required
def hr_management():
    employee_count = Employee.query.count()
    attendance_count = AttendanceRecord.query.count()
    leave_count = LeaveRequest.query.count()
    payroll_count = PayrollRun.query.count()

    features = [
        {
            "title": "Employees",
            "url": url_for("admin.hr_employees"),
            "description": "Create and manage employee profiles for attendance and payroll.",
            "icon": "👥",
            "count": employee_count,
        },
        {
            "title": "Attendance",
            "url": url_for("admin.hr_attendance"),
            "description": "Review attendance records and exceptions without marking attendance manually.",
            "icon": "🕒",
            "count": attendance_count,
        },
        {
            "title": "Leave Requests",
            "url": url_for("admin.hr_leave_requests"),
            "description": "Review, approve, and reject employee leave requests.",
            "icon": "🏖️",
            "count": leave_count,
        },
        {
            "title": "Correction Requests",
            "url": url_for("admin.hr_correction_requests"),
            "description": "Review employee attendance correction requests with audit history.",
            "icon": "📝",
            "count": AttendanceCorrectionRequest.query.count(),
        },
        {
            "title": "Payroll",
            "url": url_for("admin.hr_payroll"),
            "description": "Run payroll cycles, calculate net pay, and manage salary records.",
            "icon": "💰",
            "count": payroll_count,
        },
    ]
    return _render_admin_module_page(
        "HR & Payroll Management",
        "Manage employees, attendance, leave requests and payroll from one secure HR operations module.",
        features,
    )


@admin_bp.route("/dashboard/hr-management/employees", methods=["GET", "POST"])
@admin_required
def hr_employees():
    users = User.query.order_by(User.full_name.asc()).all()
    if request.method == "POST":
        user_id = request.form.get("user_id")
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        designation = request.form.get("designation", "").strip() or "Team Member"
        department = request.form.get("department", "").strip() or "Operations"
        base_salary = request.form.get("base_salary", "0").strip()
        joining_date = request.form.get("joining_date")

        if not name or not email:
            flash("Employee name and email are required.", "danger")
            return redirect(url_for("admin.hr_employees"))

        linked_user = None
        if user_id:
            try:
                linked_user = User.query.get(int(user_id))
            except (TypeError, ValueError):
                linked_user = None

        if linked_user and Employee.query.filter_by(user_id=linked_user.id).first():
            flash("Selected user already has an employee record.", "warning")
            return redirect(url_for("admin.hr_employees"))

        employee = Employee(
            user_id=linked_user.id if linked_user else None,
            name=name,
            email=email,
            designation=designation,
            department=department,
            base_salary=Decimal(base_salary or 0),
            joining_date=datetime.strptime(joining_date, "%Y-%m-%d").date() if joining_date else date.today(),
        )
        db.session.add(employee)
        db.session.commit()
        flash("Employee created successfully.", "success")
        return redirect(url_for("admin.hr_employees"))

    employees = Employee.query.order_by(Employee.created_at.desc()).all()
    return render_template(
        "admin/hr_employees.html",
        employees=employees,
        users=users,
        today=date.today().isoformat(),
    )


@admin_bp.get("/dashboard/hr-management/attendance")
@admin_required
def hr_attendance():
    employees = Employee.query.order_by(Employee.name.asc()).all()
    attendance = (
        AttendanceRecord.query.options(selectinload(AttendanceRecord.employee))
        .order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.created_at.desc())
        .all()
    )
    return render_template(
        "admin/hr_attendance.html",
        employees=employees,
        attendance=attendance,
        today=date.today().isoformat(),
    )


@admin_bp.get("/dashboard/hr-management/leave-requests")
@admin_required
def hr_leave_requests():
    employees = Employee.query.order_by(Employee.name.asc()).all()
    leave_requests = (
        LeaveRequest.query.options(selectinload(LeaveRequest.employee))
        .order_by(LeaveRequest.created_at.desc())
        .all()
    )
    return render_template(
        "admin/hr_leave_requests.html",
        employees=employees,
        leave_requests=leave_requests,
        today=date.today().isoformat(),
    )


@admin_bp.route("/dashboard/hr-management/leave-requests/<int:leave_id>/action", methods=["POST"])
@admin_required
def hr_leave_request_action(leave_id: int):
    action = request.form.get("action")
    leave_request = LeaveRequest.query.get(leave_id)
    if not leave_request:
        flash("Leave request not found.", "danger")
        return redirect(url_for("admin.hr_leave_requests"))

    if action == "approve":
        leave_request.status = "Approved"
        leave_request.approved_by = current_user.id
        leave_request.approved_at = datetime.utcnow()
        for attendance_date in _date_range(leave_request.start_date, leave_request.end_date):
            record = (
                AttendanceRecord.query.filter_by(
                    employee_id=leave_request.employee_id, attendance_date=attendance_date
                )
                .first()
            )
            if not record:
                record = AttendanceRecord(
                    employee_id=leave_request.employee_id,
                    attendance_date=attendance_date,
                )
                db.session.add(record)
            record.status = "On Leave"
            record.check_in = None
            record.check_out = None
            existing_notes = (record.notes or "").strip()
            record.notes = (
                f"{existing_notes} " if existing_notes else ""
            ) + f"Leave approved: {leave_request.leave_type}"
    elif action == "reject":
        leave_request.status = "Rejected"
    else:
        flash("Invalid leave action.", "warning")
        return redirect(url_for("admin.hr_leave_requests"))

    db.session.commit()
    flash(f"Leave request {action}d.", "success")
    return redirect(url_for("admin.hr_leave_requests"))


@admin_bp.get("/dashboard/hr-management/correction-requests")
@admin_required
def hr_correction_requests():
    correction_requests = (
        AttendanceCorrectionRequest.query.options(
            selectinload(AttendanceCorrectionRequest.employee),
            selectinload(AttendanceCorrectionRequest.attendance_record),
        )
        .order_by(AttendanceCorrectionRequest.submitted_at.desc())
        .all()
    )
    return render_template("admin/hr_correction_requests.html", correction_requests=correction_requests)


@admin_bp.route("/dashboard/hr-management/correction-requests/<int:request_id>/action", methods=["POST"])
@admin_required
def hr_correction_request_action(request_id: int):
    action = request.form.get("action")
    review_notes = request.form.get("review_notes", "").strip()
    correction_request = AttendanceCorrectionRequest.query.get(request_id)
    if not correction_request:
        flash("Correction request not found.", "danger")
        return redirect(url_for("admin.hr_correction_requests"))

    if action == "approve":
        correction_request.status = "Approved"
        correction_request.reviewed_by = current_user.id
        correction_request.reviewed_at = datetime.utcnow()
        correction_request.change_notes = review_notes
        correction_request.attendance_record.check_in = correction_request.requested_check_in
        correction_request.attendance_record.check_out = correction_request.requested_check_out
        correction_request.attendance_record.status = "Present"

        audit = AttendanceAuditLog(
            correction_request_id=correction_request.id,
            employee_id=correction_request.employee_id,
            attendance_id=correction_request.attendance_id,
            reviewer_id=current_user.id,
            action="Approved",
            status="Approved",
            submitted_at=correction_request.submitted_at,
            reviewed_at=correction_request.reviewed_at,
            requested_check_in=correction_request.requested_check_in,
            requested_check_out=correction_request.requested_check_out,
            original_check_in=correction_request.original_check_in,
            original_check_out=correction_request.original_check_out,
            new_check_in=correction_request.requested_check_in,
            new_check_out=correction_request.requested_check_out,
            reason=correction_request.reason,
            review_notes=review_notes,
        )
        db.session.add(audit)
    elif action == "reject":
        correction_request.status = "Rejected"
        correction_request.reviewed_by = current_user.id
        correction_request.reviewed_at = datetime.utcnow()
        correction_request.change_notes = review_notes

        audit = AttendanceAuditLog(
            correction_request_id=correction_request.id,
            employee_id=correction_request.employee_id,
            attendance_id=correction_request.attendance_id,
            reviewer_id=current_user.id,
            action="Rejected",
            status="Rejected",
            submitted_at=correction_request.submitted_at,
            reviewed_at=correction_request.reviewed_at,
            requested_check_in=correction_request.requested_check_in,
            requested_check_out=correction_request.requested_check_out,
            original_check_in=correction_request.original_check_in,
            original_check_out=correction_request.original_check_out,
            new_check_in=None,
            new_check_out=None,
            reason=correction_request.reason,
            review_notes=review_notes,
        )
        db.session.add(audit)
    else:
        flash("Invalid correction action.", "warning")
        return redirect(url_for("admin.hr_correction_requests"))

    db.session.commit()
    flash(f"Correction request {action}d.", "success")
    return redirect(url_for("admin.hr_correction_requests"))


@admin_bp.route("/dashboard/hr-management/payroll", methods=["GET", "POST"])
@admin_required
def hr_payroll():
    employees = Employee.query.order_by(Employee.name.asc()).all()
    if request.method == "POST":
        employee_id = request.form.get("employee_id")
        period_start = request.form.get("period_start")
        period_end = request.form.get("period_end")
        gross_pay = request.form.get("gross_pay", "0").strip()
        allowances = request.form.get("allowances", "0").strip()
        deductions = request.form.get("deductions", "0").strip()
        remarks = request.form.get("remarks", "").strip()

        if not employee_id or not period_start or not period_end:
            flash("Employee and payroll period are required.", "danger")
            return redirect(url_for("admin.hr_payroll"))

        try:
            employee = Employee.query.get(int(employee_id))
        except (TypeError, ValueError):
            employee = None

        if not employee:
            flash("Selected employee was not found.", "danger")
            return redirect(url_for("admin.hr_payroll"))

        payroll_run = PayrollRun(
            employee_id=employee.id,
            period_start=datetime.strptime(period_start, "%Y-%m-%d").date(),
            period_end=datetime.strptime(period_end, "%Y-%m-%d").date(),
            gross_pay=Decimal(gross_pay or 0),
            allowances=Decimal(allowances or 0),
            deductions=Decimal(deductions or 0),
            remarks=remarks,
            status="Draft",
        )
        payroll_run.net_pay = payroll_run.calculate_net_pay()
        db.session.add(payroll_run)
        db.session.commit()
        flash("Payroll run created.", "success")
        return redirect(url_for("admin.hr_payroll"))

    payroll_runs = (
        PayrollRun.query.options(selectinload(PayrollRun.employee))
        .order_by(PayrollRun.created_at.desc())
        .all()
    )
    return render_template("admin/hr_payroll.html", employees=employees, payroll_runs=payroll_runs, today=date.today().isoformat())


@admin_bp.get("/dashboard/user-management")
@admin_required
def user_management():
    features = [
        {
            "title": "Users",
            "url": url_for("admin.users"),
            "description": "Manage all platform accounts, learner records, and login access.",
            "icon": "👤",
        },
        {
            "title": "Roles",
            "url": url_for("admin.users"),
            "description": "Review and assign user roles with current admin-level controls.",
            "icon": "🛡️",
        },
        {
            "title": "Permissions",
            "url": url_for("admin.users"),
            "description": "Use existing user management controls for permissions and access oversight.",
            "icon": "🔐",
        },
        {
            "title": "Admin Accounts",
            "url": url_for("admin.users"),
            "description": "Review administrative accounts and ensure secure platform access.",
            "icon": "👥",
        },
    ]
    return _render_admin_module_page("User Management", "Control users, admin accounts and role-based access through the admin user cockpit.", features)


@admin_bp.route("/site-settings", methods=["GET", "POST"])
@admin_required
def site_settings():
    defaults = {
        "contact_email": "skillorbitindia2704@gmail.com",
        "contact_phone": "+91 99999 99999",
        "whatsapp_number": "919999999999",
        "address_text": "India (Online + On-site for institutions)",
        "map_embed_url": "https://www.google.com/maps?q=India&output=embed",
        "linkedin_url": "#",
        "youtube_url": "#",
        "instagram_url": "#",
    }
    fields = list(defaults.keys())

    if request.method == "POST":
        try:
            for key in fields:
                _setting_set(key, request.form.get(key, "").strip())
            db.session.commit()
            flash("Site settings updated.", "success")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Could not save site settings. Please try again.", "danger")
        return redirect(url_for("admin.site_settings"))

    values = {key: _setting_get(key, default) for key, default in defaults.items()}
    return render_template("admin/site_settings.html", values=values)


@admin_bp.route("/website-branding", methods=["GET"])
@admin_required
def website_branding():
    current_app.logger.debug("Entering website_branding handler")
    logo_url = _setting_get(KEY_LOGO, "")
    dark_logo_url = _setting_get(KEY_DARK_LOGO, "")
    favicon_url = _setting_get(KEY_FAVICON, "")

    return render_template(
        "admin/website_branding.html",
        logo_url=logo_url,
        dark_logo_url=dark_logo_url,
        favicon_url=favicon_url,
    )


@admin_bp.route("/website-branding/upload", methods=["POST"])
@admin_required
def website_branding_upload():
    current_app.logger.debug("Entering website_branding_upload handler")
    kind = (request.form.get("kind") or "").strip()
    if kind not in KIND_TO_KEY:
        current_app.logger.warning(f"Invalid branding kind requested: {kind}")
        return jsonify({"error": "Invalid branding target."}), 400

    img = request.files.get("image")
    if not img or not img.filename:
        current_app.logger.warning("No image uploaded for website branding")
        return jsonify({"error": "Please upload an image file."}), 400

    try:
        if hasattr(img, "content_length") and img.content_length is not None:
            if int(img.content_length) > MAX_BRANDING_UPLOAD_BYTES:
                current_app.logger.warning("Branding image exceeded maximum 5MB size limit")
                return jsonify({"error": "File too large. Max size is 5MB."}), 400
    except Exception as e:
        current_app.logger.warning(f"Error checking image content_length: {e}")

    try:
        rel_path = _save_branding_upload(img, kind=kind)
        _setting_set(KIND_TO_KEY[kind], rel_path)
        db.session.commit()
        current_app.logger.info(f"Branding image for {kind} uploaded successfully: {rel_path}")
        return jsonify({
            "ok": True,
            "url": _branding_static_url(rel_path),
            "kind": kind,
            "toast": "Branding updated successfully.",
        })
    except ValueError as exc:
        db.session.rollback()
        current_app.logger.error(f"ValueError saving branding upload: {exc}")
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"Unexpected error saving branding upload: {exc}")
        return jsonify({"error": "Could not save branding. Please try again."}), 500


@admin_bp.route("/website-branding/delete", methods=["POST"])
@admin_required
def website_branding_delete():
    current_app.logger.debug("Entering website_branding_delete handler")
    data = request.get_json(silent=True) or {}
    kind = (data.get("kind") or "").strip()

    if kind not in KIND_TO_KEY:
        current_app.logger.warning(f"Invalid branding kind requested for deletion: {kind}")
        return jsonify({"error": "Invalid branding target."}), 400

    try:
        _setting_set(KIND_TO_KEY[kind], "")
        db.session.commit()
        current_app.logger.info(f"Branding image for {kind} cleared")

        default_rel = KIND_TO_DEFAULT_PATH[kind]
        return jsonify({
            "ok": True,
            "url": _branding_static_url(default_rel),
            "kind": kind,
            "toast": "Branding cleared.",
        })
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"Error clearing branding: {exc}")
        return jsonify({"error": "Could not clear branding. Please try again."}), 500


@admin_bp.route("/products", methods=["GET", "POST"])
@admin_required
def products():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if len(name) < 2:
            flash("Product name must be at least 2 characters.", "danger")
            return redirect(url_for("admin.products"))
        try:
            price_inr = max(1, int(request.form.get("price_inr", 1)))
            stock = max(0, int(request.form.get("stock", 0)))
            rating = float(request.form.get("rating", 4.5) or 4.5)
        except (TypeError, ValueError):
            flash("Price, stock, and rating must be valid numbers.", "danger")
            return redirect(url_for("admin.products"))
        if rating < 0 or rating > 5:
            flash("Rating must be between 0 and 5.", "danger")
            return redirect(url_for("admin.products"))
        category = request.form.get("category", "").strip()
        if not category:
            flash("Category is required.", "danger")
            return redirect(url_for("admin.products"))
        image_file = request.files.get("image")
        try:
            uploaded_path = _upload_product_image(image_file) if image_file else None
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.products"))
        product = Product(
            name=name,
            description=request.form.get("description", "").strip(),
            price_inr=price_inr,
            stock=stock,
            category=category,
            rating=rating,
            image_url=uploaded_path or "/static/images/default_product.svg",
        )
        try:
            db.session.add(product)
            db.session.commit()
            flash("Product added.", "success")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Could not add product. Please try again.", "danger")
        return redirect(url_for("admin.products"))
    return render_template(
        "admin/products.html",
        products=Product.query.filter(or_(Product.is_deleted.is_(False), Product.is_deleted.is_(None)))
        .order_by(Product.id.desc())
        .all(),
    )


@admin_bp.post("/products/<int:product_id>/delete")
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    # Soft-delete keeps order history intact and avoids FK integrity failures.
    product.is_deleted = True
    try:
        db.session.commit()
        flash("Product deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete product because it is referenced by other records.", "danger")
    return redirect(url_for("admin.products"))


@admin_bp.post("/products/<int:product_id>/edit")
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    name = request.form.get("name", product.name).strip()
    if len(name) < 2:
        flash("Product name must be at least 2 characters.", "danger")
        return redirect(url_for("admin.products"))
    try:
        price_inr = max(1, int(request.form.get("price_inr", product.price_inr)))
        stock = max(0, int(request.form.get("stock", product.stock)))
        rating = float(request.form.get("rating", product.rating) or product.rating)
    except (TypeError, ValueError):
        flash("Price, stock, and rating must be valid numbers.", "danger")
        return redirect(url_for("admin.products"))
    if rating < 0 or rating > 5:
        flash("Rating must be between 0 and 5.", "danger")
        return redirect(url_for("admin.products"))
    category = request.form.get("category", "").strip()
    if not category:
        flash("Category is required.", "danger")
        return redirect(url_for("admin.products"))
    product.name = name
    product.description = request.form.get("description", product.description).strip()
    product.price_inr = price_inr
    product.stock = stock
    product.category = category
    product.rating = rating
    image_file = request.files.get("image")
    if image_file and image_file.filename:
        try:
            product.image_url = _upload_product_image(image_file)
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.products"))
    try:
        db.session.commit()
        flash("Product updated.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not update product. Please try again.", "danger")
    return redirect(url_for("admin.products"))


@admin_bp.get("/orders")
@admin_required
def orders():
    orders_list = (
        Order.query.options(
            selectinload(Order.user),
            selectinload(Order.items).selectinload(OrderItem.product),
        )
        .order_by(Order.created_at.desc())
        .all()
    )
    return render_template("admin/orders.html", orders=orders_list, order_statuses=ORDER_STATUSES)


@admin_bp.post("/orders/<int:order_id>/status")
@admin_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    status = request.form.get("status", "").strip()
    if status not in ORDER_STATUSES:
        flash("Invalid order status.", "danger")
        return redirect(url_for("admin.orders"))
    order.status = status
    try:
        db.session.commit()
        notify_user(order.user_id, f"Order #{order.id} status updated to {order.status}.")
        flash("Order status updated.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not update order status. Please try again.", "danger")
    return redirect(url_for("admin.orders"))


@admin_bp.route("/courses", methods=["GET", "POST"])
@admin_required
def courses():
    if request.method == "POST":
        try:
            price_inr = max(0, int(request.form.get("price_inr", 499)))
        except (TypeError, ValueError):
            flash("Course price must be a valid number.", "danger")
            return redirect(url_for("admin.courses"))
        try:
            list_price_inr = max(0, int(request.form.get("list_price_inr", "0") or 0))
        except (TypeError, ValueError):
            list_price_inr = 0
        try:
            rating_avg = float(request.form.get("rating_avg", "4.8") or 4.8)
        except (TypeError, ValueError):
            rating_avg = 4.8
        try:
            rating_count = max(0, int(request.form.get("rating_count", "0") or 0))
        except (TypeError, ValueError):
            rating_count = 0
        try:
            enrolled_count_display = max(0, int(request.form.get("enrolled_count_display", "0") or 0))
        except (TypeError, ValueError):
            enrolled_count_display = 0
        try:
            catalog_display_order = max(0, int(request.form.get("catalog_display_order", "0") or 0))
        except (TypeError, ValueError):
            catalog_display_order = 0
        is_featured = request.form.get("is_featured") == "1"
        is_published = request.form.get("is_published") != "0"
        course = Course(
            title=request.form.get("title", "").strip(),
            description=request.form.get("description", "").strip(),
            price_inr=max(1, price_inr) if price_inr > 0 else 0,
            list_price_inr=list_price_inr,
            rating_avg=rating_avg,
            rating_count=rating_count,
            enrolled_count_display=enrolled_count_display,
            is_featured=is_featured,
            catalog_display_order=catalog_display_order,
            is_published=is_published,
            category=request.form.get("category", "").strip(),
            instructor_name=request.form.get("instructor_name", "").strip() or "Skill Orbit Faculty",
            duration=request.form.get("duration", "").strip() or "4 weeks",
            level=request.form.get("level", "").strip() or "Beginner",
            video_url=request.form.get("video_url", "").strip(),
            content=request.form.get("content", "").strip(),
            quiz_question=request.form.get("quiz_question", "").strip(),
            quiz_answer=request.form.get("quiz_answer", "").strip(),
        )
        thumb = request.files.get("thumbnail")
        if thumb and thumb.filename:
            try:
                course.thumbnail_path = _upload_ai_lab_asset(
                    thumb,
                    subdir="courses/thumbnails",
                    allowed_exts=ALLOWED_AI_IMAGE_EXTENSIONS,
                )
            except ValueError as exc:
                flash(str(exc), "danger")
                return redirect(url_for("admin.courses"))
        db.session.add(course)
        db.session.commit()
        flash("Course uploaded.", "success")
        return redirect(url_for("admin.courses"))
    return render_template("admin/courses.html", courses=Course.query.order_by(Course.id.desc()).all())


@admin_bp.route("/courses/edit/<int:cid>", methods=["GET", "POST"])
@admin_required
def course_edit(cid: int):
    row = Course.query.get_or_404(cid)
    if request.method == "POST":
        try:
            price_inr = max(0, int(request.form.get("price_inr", row.price_inr)))
        except (TypeError, ValueError):
            flash("Invalid price.", "danger")
            return redirect(url_for("admin.course_edit", cid=cid))
        row.title = request.form.get("title", row.title).strip()
        row.description = request.form.get("description", row.description or "").strip()
        row.price_inr = max(1, price_inr) if price_inr > 0 else 0
        try:
            row.list_price_inr = max(0, int(request.form.get("list_price_inr", "0") or 0))
        except (TypeError, ValueError):
            row.list_price_inr = 0
        try:
            row.rating_avg = float(request.form.get("rating_avg", row.rating_avg) or 4.8)
        except (TypeError, ValueError):
            pass
        try:
            row.rating_count = max(0, int(request.form.get("rating_count", row.rating_count) or 0))
        except (TypeError, ValueError):
            pass
        try:
            row.enrolled_count_display = max(0, int(request.form.get("enrolled_count_display", "0") or 0))
        except (TypeError, ValueError):
            pass
        try:
            row.catalog_display_order = max(0, int(request.form.get("catalog_display_order", "0") or 0))
        except (TypeError, ValueError):
            pass
        row.is_featured = request.form.get("is_featured") == "1"
        row.is_published = request.form.get("is_published") != "0"
        row.category = request.form.get("category", "").strip()
        row.instructor_name = request.form.get("instructor_name", row.instructor_name or "").strip() or "Skill Orbit Faculty"
        row.duration = request.form.get("duration", row.duration or "").strip() or "4 weeks"
        row.level = request.form.get("level", row.level or "").strip() or "Beginner"
        row.video_url = request.form.get("video_url", row.video_url or "").strip()
        row.content = request.form.get("content", row.content or "").strip()
        row.quiz_question = request.form.get("quiz_question", row.quiz_question or "").strip()
        row.quiz_answer = request.form.get("quiz_answer", row.quiz_answer or "").strip()
        thumb = request.files.get("thumbnail")
        if thumb and thumb.filename:
            try:
                row.thumbnail_path = _upload_ai_lab_asset(
                    thumb,
                    subdir="courses/thumbnails",
                    allowed_exts=ALLOWED_AI_IMAGE_EXTENSIONS,
                )
            except ValueError as exc:
                flash(str(exc), "danger")
                return redirect(url_for("admin.course_edit", cid=cid))
        try:
            db.session.commit()
            flash("Course updated.", "success")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Could not update course.", "danger")
        return redirect(url_for("admin.courses"))
    return render_template("admin/course_edit.html", course=row)


def _internship_listing_status(raw: str) -> str:
    v = (raw or "active").strip().lower()
    return v if v in {"active", "closed", "draft"} else "active"


def _safe_admin_path(url: str):
    if url and isinstance(url, str) and url.startswith("/admin/") and not url.startswith("//"):
        return url
    return None


@admin_bp.route("/internships", methods=["GET", "POST"])
@admin_required
def internships():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if len(title) < 2:
            flash("Title must be at least 2 characters.", "danger")
            return redirect(url_for("admin.internships"))
        row = Internship(
            title=title,
            description=request.form.get("description", "").strip(),
            stipend=request.form.get("stipend", "").strip(),
            internship_type=request.form.get("internship_type", "").strip(),
            duration=request.form.get("duration", "").strip(),
            location=request.form.get("location", "").strip(),
            requirements=request.form.get("requirements", "").strip(),
            skills_needed=request.form.get("skills_needed", "").strip(),
            listing_status=_internship_listing_status(request.form.get("listing_status")),
            is_visible=request.form.get("is_visible") == "1",
            is_active=request.form.get("is_active") == "1",
            is_featured=request.form.get("is_featured") == "1",
            is_urgent=request.form.get("is_urgent") == "1",
            is_remote=request.form.get("is_remote") == "1",
        )
        try:
            db.session.add(row)
            db.session.commit()
            flash("Internship listing created.", "success")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Could not create internship. Please try again.", "danger")
        return redirect(url_for("admin.internships"))

    listings = (
        Internship.query.options(selectinload(Internship.applications))
        .order_by(Internship.created_at.desc())
        .all()
    )
    applications = (
        InternshipApplication.query.options(selectinload(InternshipApplication.user), selectinload(InternshipApplication.internship))
        .order_by(InternshipApplication.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template("admin/internships.html", internships=listings, applications=applications)


@admin_bp.post("/internships/edit/<int:iid>")
@admin_required
def edit_internship(iid):
    row = Internship.query.get_or_404(iid)
    title = request.form.get("title", row.title).strip()
    if len(title) < 2:
        flash("Title must be at least 2 characters.", "danger")
        return redirect(url_for("admin.internships"))
    row.title = title
    row.description = request.form.get("description", row.description).strip()
    row.stipend = request.form.get("stipend", row.stipend).strip()
    row.internship_type = request.form.get("internship_type", row.internship_type or "").strip()
    row.duration = request.form.get("duration", row.duration or "").strip()
    row.location = request.form.get("location", row.location or "").strip()
    row.requirements = request.form.get("requirements", row.requirements or "").strip()
    row.skills_needed = request.form.get("skills_needed", row.skills_needed or "").strip()
    row.listing_status = _internship_listing_status(request.form.get("listing_status", row.listing_status))
    row.is_visible = request.form.get("is_visible") == "1"
    row.is_active = request.form.get("is_active") == "1"
    row.is_featured = request.form.get("is_featured") == "1"
    row.is_urgent = request.form.get("is_urgent") == "1"
    row.is_remote = request.form.get("is_remote") == "1"
    try:
        db.session.commit()
        flash("Internship listing updated.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not update internship.", "danger")
    return redirect(url_for("admin.internships"))


@admin_bp.post("/internships/delete/<int:iid>")
@admin_required
def delete_internship(iid):
    row = Internship.query.options(selectinload(Internship.applications)).get_or_404(iid)
    title = row.title
    cnt = len(row.applications)
    try:
        if cnt > 0:
            row.listing_status = "closed"
            row.is_visible = False
            row.is_active = False
            db.session.commit()
            flash(
                f"“{title}” archived (applications preserved). Permanent delete removes data — use only on listings with zero applicants.",
                "warning",
            )
        else:
            db.session.delete(row)
            db.session.commit()
            flash(f"Internship “{title}” deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete internship.", "danger")
    return redirect(url_for("admin.internships"))


@admin_bp.post("/internships/toggle/<int:iid>")
@admin_required
def toggle_internship_visibility(iid):
    row = Internship.query.get_or_404(iid)
    row.is_visible = not bool(row.is_visible)
    try:
        db.session.commit()
        state = "visible" if row.is_visible else "hidden"
        flash(f"Listing visibility: {state}.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not toggle visibility.", "danger")
    return redirect(url_for("admin.internships"))


@admin_bp.post("/internships/status/<int:iid>")
@admin_required
def set_internship_listing_status(iid):
    row = Internship.query.get_or_404(iid)
    row.listing_status = _internship_listing_status(request.form.get("listing_status"))
    row.is_active = row.listing_status == "active"
    try:
        db.session.commit()
        flash("Listing status updated.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not update listing status.", "danger")
    return redirect(url_for("admin.internships"))


@admin_bp.get("/internships/applications/<int:iid>")
@admin_required
def internship_applications(iid):
    internship = Internship.query.get_or_404(iid)
    apps = (
        InternshipApplication.query.options(selectinload(InternshipApplication.user))
        .filter_by(internship_id=iid)
        .order_by(InternshipApplication.created_at.desc())
        .all()
    )
    return render_template(
        "admin/internship_applications.html",
        internship=internship,
        applications=apps,
    )


@admin_bp.post("/internship-application/<int:app_id>/status")
@admin_required
def update_application_status(app_id):
    app_obj = InternshipApplication.query.get_or_404(app_id)
    status = request.form.get("status", "pending")
    if status in {"pending", "approved", "rejected"}:
        app_obj.status = status
        if status == "approved":
            notify_user(
                app_obj.user_id,
                f"Your internship application for “{app_obj.internship.title}” was approved!",
            )
        elif status == "rejected":
            notify_user(
                app_obj.user_id,
                f"Update on “{app_obj.internship.title}”: application not selected this round.",
            )
        db.session.commit()
        flash("Application status updated.", "success")
    nxt = _safe_admin_path(request.form.get("next"))
    if nxt:
        return redirect(nxt)
    return redirect(url_for("admin.internships"))


@admin_bp.get("/users")
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=all_users)


@admin_bp.route("/teachers", methods=["GET", "POST"])
@admin_required
def teachers():
    # Admin creates teacher accounts; no public teacher signup.
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email_raw = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if len(full_name) < 3 or len(password) < 8:
            flash("Name must be 3+ chars and password 8+.", "danger")
            return redirect(url_for("admin.teachers"))
        try:
            email = validate_email(email_raw, check_deliverability=False).normalized
        except EmailNotValidError:
            flash("Invalid teacher email.", "danger")
            return redirect(url_for("admin.teachers"))
        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "warning")
            return redirect(url_for("admin.teachers"))
        teacher = User(
            full_name=full_name,
            email=email,
            password_hash=bcrypt.generate_password_hash(password).decode("utf-8"),
            role="teacher",
            is_approved=True,
        )
        teacher.sync_admin_flags()
        try:
            db.session.add(teacher)
            db.session.commit()
            flash("Teacher account added and approved.", "success")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Could not create teacher account. Please try again.", "danger")
        return redirect(url_for("admin.teachers"))
    teachers_list = User.query.filter_by(role="teacher").order_by(User.created_at.desc()).all()
    pending_list = (
        User.query.filter_by(role="teacher", is_approved=False).order_by(User.created_at.desc()).all()
    )
    return render_template("admin/teachers.html", teachers=teachers_list, pending_teachers=pending_list)


@admin_bp.post("/teachers/<int:user_id>/approve")
@admin_bp.post("/approve_teacher/<int:user_id>")
@admin_required
def approve_teacher(user_id):
    teacher = User.query.get_or_404(user_id)
    if teacher.role != "teacher":
        flash("Selected user is not a teacher.", "danger")
        return redirect(url_for("admin.teachers"))
    teacher.is_approved = True
    try:
        db.session.commit()
        flash("Teacher approved.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not approve teacher. Please try again.", "danger")
    return redirect(url_for("admin.teachers"))


@admin_bp.post("/teachers/<int:user_id>/reject")
@admin_bp.post("/reject_teacher/<int:user_id>")
@admin_required
def reject_teacher(user_id):
    teacher = User.query.get_or_404(user_id)
    if teacher.role != "teacher":
        flash("Selected user is not a teacher.", "danger")
        return redirect(url_for("admin.teachers"))
    teacher.is_approved = False
    try:
        db.session.commit()
        flash("Teacher access set to pending.", "warning")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not update teacher approval. Please try again.", "danger")
    return redirect(url_for("admin.teachers"))


@admin_bp.post("/teachers/<int:user_id>/delete")
@admin_required
def delete_teacher(user_id):
    teacher = User.query.get_or_404(user_id)
    if teacher.role != "teacher":
        flash("Selected user is not a teacher.", "danger")
        return redirect(url_for("admin.teachers"))
    db.session.delete(teacher)
    db.session.commit()
    flash("Teacher removed.", "info")
    return redirect(url_for("admin.teachers"))


@admin_bp.post("/users/<int:user_id>/role")
@admin_required
def set_user_role(user_id):
    user_obj = User.query.get_or_404(user_id)
    new_role = request.form.get("role", "student")
    if new_role not in ("student", "teacher", "admin"):
        flash("Invalid role.", "danger")
        return redirect(url_for("admin.users"))
    # Prevent self-demotion by checking against current session user_id.
    if session.get("user_id") and int(session.get("user_id")) == user_obj.id and new_role != "admin":
        flash("You cannot remove your own admin access.", "warning")
        return redirect(url_for("admin.users"))
    user_obj.role = new_role
    if new_role == "teacher":
        user_obj.is_approved = True
    if new_role == "student":
        user_obj.is_approved = True
    user_obj.sync_admin_flags()
    try:
        db.session.commit()
        flash("User role updated.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not update user role. Please try again.", "danger")
    return redirect(url_for("admin.users"))


@admin_bp.post("/users/<int:user_id>/disable")
@admin_required
def toggle_user_active(user_id):
    from flask_login import current_user

    user_obj = User.query.get_or_404(user_id)
    if session.get("user_id") and int(session.get("user_id")) == user_obj.id:
        flash("You cannot disable your own account while logged in.", "warning")
        return redirect(url_for("admin.users"))
    user_obj.is_active = not bool(user_obj.is_active)
    state = "enabled" if user_obj.is_active else "disabled"
    try:
        db.session.commit()
        flash(f"User account {state}.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not update user account status. Please try again.", "danger")
    return redirect(url_for("admin.users"))


@admin_bp.post("/users/<int:user_id>/delete")
@admin_required
def delete_user(user_id):
    user_obj = User.query.get_or_404(user_id)
    if session.get("user_id") and int(session.get("user_id")) == user_obj.id:
        flash("You cannot delete your own account while logged in.", "warning")
        return redirect(url_for("admin.users"))
    try:
        db.session.delete(user_obj)
        db.session.commit()
        flash("User deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete user. Please try again.", "danger")
    return redirect(url_for("admin.users"))


@admin_bp.get("/service-requests")
@admin_bp.get("/services")
@admin_required
def service_requests():
    rows = ServiceRequest.query.order_by(ServiceRequest.created_at.desc()).all()
    return render_template("admin/service_requests.html", requests=rows)


@admin_bp.get("/services/manage")
@admin_required
def services_manage():
    rows = ServicePackage.query.order_by(ServicePackage.display_order.asc(), ServicePackage.id.asc()).all()
    return render_template("admin/services_manage.html", services=rows)


@admin_bp.post("/services/create")
@admin_required
def create_service():
    title = request.form.get("title", "").strip()
    short_description = request.form.get("short_description", "").strip()
    full_description = request.form.get("full_description", "").strip()
    pricing_text = request.form.get("pricing_text", "").strip()
    features = request.form.get("features", "").strip()
    icon = request.form.get("icon", "🔧").strip() or "🔧"
    category = request.form.get("category", "").strip()
    badge_text = request.form.get("badge_text", "").strip()
    button_text = request.form.get("button_text", "Request service").strip() or "Request service"
    button_link = request.form.get("button_link", "#service-modal").strip() or "#service-modal"
    image = request.form.get("image", "").strip()
    display_order_raw = request.form.get("display_order", "0")

    if not title or not short_description or not pricing_text:
        flash("Title, short description, and pricing are required.", "danger")
        return redirect(url_for("admin.services_manage"))
    try:
        display_order = max(0, int(display_order_raw or 0))
    except (TypeError, ValueError):
        display_order = 0
    row = ServicePackage(
        title=title,
        slug=_slugify_service_title(title),
        short_description=short_description,
        full_description=full_description or short_description,
        pricing_text=pricing_text,
        features=features,
        icon=icon,
        image=image,
        button_text=button_text,
        button_link=button_link,
        category=category,
        badge_text=badge_text,
        display_order=display_order,
        is_active=1,
    )
    try:
        db.session.add(row)
        db.session.commit()
        flash(f"Service '{title}' created.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not create service. Please try again.", "danger")
    return redirect(url_for("admin.services_manage"))


@admin_bp.post("/services/edit/<int:sid>")
@admin_required
def edit_service(sid):
    row = ServicePackage.query.get_or_404(sid)
    title = request.form.get("title", row.title).strip()
    short_description = request.form.get("short_description", row.short_description).strip()
    full_description = request.form.get("full_description", row.full_description).strip()
    pricing_text = request.form.get("pricing_text", row.pricing_text).strip()
    features = request.form.get("features", row.features).strip()
    icon = request.form.get("icon", row.icon).strip() or row.icon or "🔧"
    category = request.form.get("category", row.category).strip()
    badge_text = request.form.get("badge_text", row.badge_text).strip()
    button_text = request.form.get("button_text", row.button_text).strip() or "Request service"
    button_link = request.form.get("button_link", row.button_link).strip() or "#service-modal"
    image = request.form.get("image", row.image).strip()
    display_order_raw = request.form.get("display_order", row.display_order)
    if not title or not short_description or not pricing_text:
        flash("Title, short description, and pricing are required.", "danger")
        return redirect(url_for("admin.services_manage"))
    try:
        display_order = max(0, int(display_order_raw or 0))
    except (TypeError, ValueError):
        display_order = row.display_order
    row.title = title
    row.short_description = short_description
    row.full_description = full_description or short_description
    row.pricing_text = pricing_text
    row.features = features
    row.icon = icon
    row.image = image
    row.button_text = button_text
    row.button_link = button_link
    row.category = category
    row.badge_text = badge_text
    row.display_order = display_order
    if not row.slug:
        row.slug = _slugify_service_title(title)
    try:
        db.session.commit()
        flash(f"Service '{title}' updated.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not update service. Please try again.", "danger")
    return redirect(url_for("admin.services_manage"))


@admin_bp.post("/services/delete/<int:sid>")
@admin_required
def delete_service(sid):
    row = ServicePackage.query.get_or_404(sid)
    name = row.title
    try:
        db.session.delete(row)
        db.session.commit()
        flash(f"Service '{name}' deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete service. Please try again.", "danger")
    return redirect(url_for("admin.services_manage"))


@admin_bp.post("/services/toggle/<int:sid>")
@admin_required
def toggle_service(sid):
    row = ServicePackage.query.get_or_404(sid)
    row.is_active = 0 if row.is_active else 1
    try:
        db.session.commit()
        state = "enabled" if row.is_active else "disabled"
        flash(f"Service '{row.title}' {state}.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not update service status. Please try again.", "danger")
    return redirect(url_for("admin.services_manage"))


@admin_bp.post("/service-requests/<int:rid>/status")
@admin_required
def service_request_status(rid):
    row = ServiceRequest.query.get_or_404(rid)
    status = request.form.get("status", "new")
    if status in {"new", "in_progress", "closed"}:
        row.status = status
        db.session.commit()
        flash("Request status updated.", "success")
    return redirect(url_for("admin.service_requests"))


@admin_bp.get("/ai-lab-inquiries")
@admin_bp.get("/ai-lab")
@admin_required
def ai_lab_inquiries():
    rows = AILabInquiry.query.order_by(AILabInquiry.created_at.desc()).all()
    return render_template("admin/ai_lab_inquiries.html", inquiries=rows)


@admin_bp.post("/ai-lab-inquiries/<int:iid>/status")
@admin_required
def ai_lab_inquiry_status(iid):
    row = AILabInquiry.query.get_or_404(iid)
    status = request.form.get("status", "new")
    if status in {"new", "in_progress", "closed"}:
        row.status = status
        db.session.commit()
        flash("Inquiry status updated.", "success")
    return redirect(url_for("admin.ai_lab_inquiries"))


@admin_bp.post("/ai-lab-inquiries/export")
@admin_required
def ai_lab_inquiries_export():
    """Export AI lab inquiries into CSV for offline CRM workflows."""
    rows = AILabInquiry.query.order_by(AILabInquiry.created_at.desc()).all()

    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "Created At",
            "Institution",
            "City",
            "Contact Person",
            "Phone",
            "Email",
            "Lab Type",
            "Budget Range",
            "Message",
            "Status",
        ]
    )

    for q in rows:
        writer.writerow(
            [
                q.created_at.strftime("%Y-%m-%d %H:%M"),
                q.institution_name,
                q.city or "",
                q.contact_person,
                q.phone,
                q.email,
                q.lab_type or q.package_interest or "",
                q.budget_range or "",
                q.message or q.requirements or "",
                q.status or "",
            ]
        )

    csv_bytes = out.getvalue().encode("utf-8-sig")
    resp = Response(csv_bytes, mimetype="text/csv; charset=utf-8")
    resp.headers["Content-Disposition"] = 'attachment; filename="ai_lab_inquiries.csv"'
    return resp


@admin_bp.route("/certificates", methods=["GET", "POST"])
@admin_required
def issue_certificate():
    if request.method == "POST":
        try:
            user_id = int(request.form.get("user_id", 0))
            course_id = int(request.form.get("course_id", 0))
        except (TypeError, ValueError):
            flash("Invalid learner or course selection.", "danger")
            return redirect(url_for("admin.issue_certificate"))
        learner = User.query.get_or_404(user_id)
        course = Course.query.get_or_404(course_id)
        existing = Certificate.query.filter_by(user_id=learner.id, course_id=course.id).first()
        if existing:
            flash("This learner already has a certificate for that course.", "warning")
        else:
            uid, pdf_path = generate_certificate_pdf(learner.full_name, course.title)
            db.session.add(
                Certificate(
                    certificate_uid=uid,
                    user_id=learner.id,
                    course_id=course.id,
                    pdf_path=pdf_path,
                )
            )
            notify_user(
                learner.id,
                f"A certificate was issued for “{course.title}”. Verify ID: {uid[:8]}…",
            )
            flash("Certificate generated and learner notified.", "success")
        db.session.commit()
        return redirect(url_for("admin.issue_certificate"))
    users_list = User.query.order_by(User.full_name).limit(300).all()
    courses_list = Course.query.order_by(Course.title).all()
    recent = Certificate.query.order_by(Certificate.issued_at.desc()).limit(15).all()
    return render_template(
        "admin/certificates.html",
        users_list=users_list,
        courses_list=courses_list,
        recent_certificates=recent,
    )


# ===== SAFE USER CLEANUP ROUTES =====

@admin_bp.route("/cleanup-users", methods=["GET", "POST"])
@admin_required
def cleanup_users():
    """
    Safe deletion of all non-admin users from the database.
    
    GET: Show confirmation page with deletion statistics
    POST: Execute the actual deletion with safety checks
    """
    # Verify admin account exists
    admin_user = User.query.filter(
        (User.role == 'admin') | (User.is_admin == True)
    ).first()
    
    if not admin_user:
        flash("⚠️ ERROR: No admin account found! Deletion aborted.", "danger")
        return redirect(url_for("admin.users"))
    
    if request.method == "POST":
        # Get confirmation code
        confirmation = request.form.get("confirmation", "").strip()
        
        # Safety check: require explicit confirmation
        if confirmation != "DELETE_ALL_NON_ADMIN_USERS":
            flash("❌ Deletion cancelled. Invalid confirmation code.", "warning")
            return redirect(url_for("admin.cleanup_users"))
        
        try:
            # Query all non-admin users
            non_admin_users = User.query.filter(
                (User.role != 'admin') & (User.is_admin == False)
            ).all()
            
            if not non_admin_users:
                flash("✓ No non-admin users to delete.", "info")
                return redirect(url_for("admin.users"))
            
            deletion_stats = {
                "users_deleted": 0,
                "enrollments_deleted": 0,
                "orders_deleted": 0,
                "certificates_deleted": 0,
                "internship_apps_deleted": 0,
                "wishlist_items_deleted": 0,
                "notifications_deleted": 0,
            }
            
            # Delete each non-admin user and their related data
            for user in non_admin_users:
                user_id = user.id
                
                # Cascade deletes (handled by SQLAlchemy relationships with cascade)
                # Notifications (cascade="all, delete-orphan")
                deletion_stats["notifications_deleted"] += len(user.notifications)
                
                # WishlistItems (cascade="all, delete-orphan")
                deletion_stats["wishlist_items_deleted"] += len(user.wishlist_items)
                
                # Manual deletes for other relationships without cascades
                enrollments = Enrollment.query.filter_by(user_id=user_id).all()
                deletion_stats["enrollments_deleted"] += len(enrollments)
                for enrollment in enrollments:
                    db.session.delete(enrollment)
                
                orders = Order.query.filter_by(user_id=user_id).all()
                deletion_stats["orders_deleted"] += len(orders)
                for order in orders:
                    db.session.delete(order)
                
                certificates = Certificate.query.filter_by(user_id=user_id).all()
                deletion_stats["certificates_deleted"] += len(certificates)
                for cert in certificates:
                    db.session.delete(cert)
                
                internship_apps = InternshipApplication.query.filter_by(user_id=user_id).all()
                deletion_stats["internship_apps_deleted"] += len(internship_apps)
                for app in internship_apps:
                    db.session.delete(app)
                
                # Finally delete the user (cascade relationships will handle themselves)
                db.session.delete(user)
                deletion_stats["users_deleted"] += 1
            
            # Commit all deletions
            db.session.commit()
            
            # Show detailed summary
            summary = (
                f"✅ Database cleanup complete!\n\n"
                f"Deleted:\n"
                f"  • {deletion_stats['users_deleted']} user accounts\n"
                f"  • {deletion_stats['enrollments_deleted']} enrollments\n"
                f"  • {deletion_stats['orders_deleted']} orders\n"
                f"  • {deletion_stats['certificates_deleted']} certificates\n"
                f"  • {deletion_stats['internship_apps_deleted']} internship applications\n"
                f"  • {deletion_stats['wishlist_items_deleted']} wishlist items\n"
                f"  • {deletion_stats['notifications_deleted']} notifications\n\n"
                f"Admin account '{admin_user.email}' preserved ✓"
            )
            flash(summary, "success")
            
            return redirect(url_for("admin.users"))
        
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f"❌ Database error during deletion: {str(e)}", "danger")
            return redirect(url_for("admin.cleanup_users"))
        
        except Exception as e:
            db.session.rollback()
            flash(f"❌ Unexpected error: {str(e)}", "danger")
            return redirect(url_for("admin.cleanup_users"))
    
    # GET: Show confirmation page
    non_admin_users = User.query.filter(
        (User.role != 'admin') & (User.is_admin == False)
    ).all()
    
    non_admin_count = len(non_admin_users)
    total_users = User.query.count()
    
    # Calculate related data that will be deleted
    enrollments_count = Enrollment.query.filter(
        Enrollment.user_id.in_([u.id for u in non_admin_users])
    ).count() if non_admin_users else 0
    
    orders_count = Order.query.filter(
        Order.user_id.in_([u.id for u in non_admin_users])
    ).count() if non_admin_users else 0
    
    certificates_count = Certificate.query.filter(
        Certificate.user_id.in_([u.id for u in non_admin_users])
    ).count() if non_admin_users else 0
    
    internship_apps_count = InternshipApplication.query.filter(
        InternshipApplication.user_id.in_([u.id for u in non_admin_users])
    ).count() if non_admin_users else 0
    
    cleanup_stats = {
        "non_admin_users": non_admin_count,
        "total_users": total_users,
        "enrollments": enrollments_count,
        "orders": orders_count,
        "certificates": certificates_count,
        "internship_applications": internship_apps_count,
        "admin_email": admin_user.email,
    }
    
    return render_template(
        "admin/cleanup_users.html",
        stats=cleanup_stats
    )


@admin_bp.get("/ai-lab/packages")
@admin_required
def ai_lab_packages():
    """View all AI Lab packages."""
    packages = AILabPackage.query.order_by(AILabPackage.display_order.asc()).all()
    return render_template("admin/ai_lab_packages.html", packages=packages)


@admin_bp.post("/ai-lab/packages/create")
@admin_required
def create_ai_lab_package():
    """Create a new AI Lab package."""
    title = request.form.get("title", "").strip()
    subtitle = request.form.get("subtitle", "").strip()
    pricing_text = request.form.get("pricing_text", "").strip()
    description = request.form.get("description", "").strip()
    features_raw = request.form.get("features", "").strip()
    button_text = request.form.get("button_text", "Get started").strip()
    icon = request.form.get("icon", "🔧").strip()
    display_order = request.form.get("display_order", 0)

    if not title or not subtitle or not pricing_text or not description or not features_raw:
        flash("All fields are required.", "danger")
        return redirect(url_for("admin.ai_lab_packages"))

    try:
        display_order = max(0, int(display_order or 0))
    except (TypeError, ValueError):
        display_order = 0

    pkg = AILabPackage(
        title=title,
        slug=_slugify_package_title(title),
        short_description=subtitle[:255],
        package_type="custom",
        badge="",
        is_popular=False,
        is_visible=True,
        subtitle=subtitle,
        pricing_text=pricing_text,
        description=description,
        button_text=button_text,
        cta_text=button_text,
        cta_link="#inquiry",
        icon=icon,
        display_order=display_order,
        is_active=1,
    )
    pkg.set_features_list([f.strip() for f in features_raw.split('\n') if f.strip()])

    try:
        db.session.add(pkg)
        db.session.commit()
        flash(f"Package '{title}' created.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not create package. Please try again.", "danger")

    return redirect(url_for("admin.ai_lab_packages"))


@admin_bp.post("/ai-lab/packages/<int:pkg_id>/edit")
@admin_required
def edit_ai_lab_package(pkg_id):
    """Edit an AI Lab package."""
    pkg = AILabPackage.query.get_or_404(pkg_id)

    title = request.form.get("title", pkg.title).strip()
    subtitle = request.form.get("subtitle", pkg.subtitle).strip()
    pricing_text = request.form.get("pricing_text", pkg.pricing_text).strip()
    description = request.form.get("description", pkg.description).strip()
    features_raw = request.form.get("features", "").strip()
    button_text = request.form.get("button_text", pkg.button_text).strip()
    icon = request.form.get("icon", pkg.icon).strip()
    display_order = request.form.get("display_order", pkg.display_order)

    if not title or not subtitle or not pricing_text or not description:
        flash("Title, subtitle, pricing, and description are required.", "danger")
        return redirect(url_for("admin.ai_lab_packages"))

    try:
        display_order = max(0, int(display_order or 0))
    except (TypeError, ValueError):
        display_order = pkg.display_order

    pkg.title = title
    if not pkg.slug:
        pkg.slug = _slugify_package_title(title)
    pkg.short_description = subtitle[:255]
    pkg.subtitle = subtitle
    pkg.pricing_text = pricing_text
    pkg.description = description
    pkg.package_type = pkg.package_type or "custom"
    pkg.badge = pkg.badge or ""
    pkg.is_popular = bool(pkg.is_popular)
    pkg.is_visible = bool(pkg.is_active)
    pkg.button_text = button_text
    pkg.cta_text = button_text
    pkg.cta_link = pkg.button_link or "#inquiry"
    pkg.icon = icon
    pkg.display_order = display_order
    if features_raw:
        pkg.set_features_list([f.strip() for f in features_raw.split('\n') if f.strip()])

    try:
        db.session.commit()
        flash(f"Package '{title}' updated.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not update package. Please try again.", "danger")

    return redirect(url_for("admin.ai_lab_packages"))


@admin_bp.post("/ai-lab/packages/<int:pkg_id>/delete")
@admin_required
def delete_ai_lab_package(pkg_id):
    """Delete an AI Lab package."""
    pkg = AILabPackage.query.get_or_404(pkg_id)
    title = pkg.title

    try:
        db.session.delete(pkg)
        db.session.commit()
        flash(f"Package '{title}' deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete package. Please try again.", "danger")

    return redirect(url_for("admin.ai_lab_packages"))


@admin_bp.post("/ai-lab/packages/<int:pkg_id>/toggle")
@admin_required
def toggle_ai_lab_package(pkg_id):
    """Enable/disable an AI Lab package."""
    pkg = AILabPackage.query.get_or_404(pkg_id)
    pkg.is_active = 1 if pkg.is_active == 0 else 0

    try:
        db.session.commit()
        status = "enabled" if pkg.is_active else "disabled"
        flash(f"Package '{pkg.title}' {status}.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not update package status. Please try again.", "danger")

    return redirect(url_for("admin.ai_lab_packages"))


# =========================
# AI Lab CMS (Hardware, Curriculum, Projects, Testimonials, FAQs, Brochure, Gallery)
# =========================
ALLOWED_AI_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
ALLOWED_AI_MEDIA_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp",
    "gif",
    "mp4",
    "webm",
    "mov",
    "avi",
    "mkv",
}
ALLOWED_AI_PDF_EXTENSIONS = {"pdf"}


def _upload_ai_lab_asset(file_storage, *, subdir: str, allowed_exts: set[str]) -> str:
    """Upload an AI Lab asset into static/uploads and return relative path."""
    if not file_storage or not getattr(file_storage, "filename", None):
        raise ValueError("No file uploaded.")
    if not file_storage.filename:
        raise ValueError("No file uploaded.")

    safe_name = secure_filename(file_storage.filename)
    if "." not in safe_name:
        raise ValueError("Invalid file name.")
    ext = safe_name.rsplit(".", 1)[1].lower()
    if ext not in allowed_exts:
        raise ValueError(f"Allowed file types: {', '.join(sorted(allowed_exts))}.")

    upload_rel_dir = os.path.join("uploads", "ai_lab", subdir).replace(os.sep, "/")
    upload_abs_dir = os.path.join(current_app.static_folder, upload_rel_dir.replace("/", os.sep))
    os.makedirs(upload_abs_dir, exist_ok=True)

    unique_name = f"{uuid4().hex}_{safe_name}"
    abs_path = os.path.join(upload_abs_dir, unique_name)
    file_storage.save(abs_path)
    return f"{upload_rel_dir}/{unique_name}"


# =========================
# Homepage CMS (Testimonials, Events)
# =========================
@admin_bp.route("/home/testimonials", methods=["GET", "POST"])
@admin_required
def home_testimonials():
    per_page = 20
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None

    edit_item = HomeTestimonial.query.get_or_404(edit_id) if edit_id else None

    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        item_id = int(item_id_raw) if item_id_raw.isdigit() else None

        name = request.form.get("name", "").strip()
        city = request.form.get("city", "").strip()
        course_completed = request.form.get("course_completed", "").strip()
        quote = request.form.get("quote", "").strip()
        rating_raw = request.form.get("rating", "5")
        display_order_raw = request.form.get("display_order", "0")
        is_active = request.form.get("is_active") == "1"

        try:
            rating = min(5, max(1, int(rating_raw or 5)))
        except (TypeError, ValueError):
            rating = 5

        try:
            display_order = max(0, int(display_order_raw or 0))
        except (TypeError, ValueError):
            display_order = 0

        if len(name) < 2 or len(quote) < 5:
            flash("Name and quote are required.", "danger")
            return redirect(url_for("admin.home_testimonials", q=q, page=page, edit=item_id or ""))

        try:
            row = HomeTestimonial.query.get_or_404(item_id) if item_id else HomeTestimonial()
            row.name = name
            row.city = city
            row.course_completed = course_completed
            row.quote = quote
            row.rating = rating
            row.display_order = display_order
            row.is_active = is_active

            img = request.files.get("image")
            if img and img.filename:
                row.image_path = _upload_ai_lab_asset(
                    img,
                    subdir=os.path.join("home", "testimonials").replace("\\", "/"),
                    allowed_exts=ALLOWED_AI_IMAGE_EXTENSIONS,
                )

            db.session.add(row)
            db.session.commit()
            flash("Homepage testimonial saved.", "success")
        except (ValueError, SQLAlchemyError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else "Could not save testimonial.", "danger")
        return redirect(url_for("admin.home_testimonials"))

    query = HomeTestimonial.query
    if q:
        query = query.filter(HomeTestimonial.name.ilike(f"%{q}%"))
    total = query.count()
    items = (
        query.order_by(HomeTestimonial.display_order.asc(), HomeTestimonial.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/home_testimonials.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )


@admin_bp.post("/home/testimonials/<int:item_id>/delete")
@admin_required
def home_testimonials_delete(item_id: int):
    row = HomeTestimonial.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        flash("Homepage testimonial deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete testimonial.", "danger")
    return redirect(url_for("admin.home_testimonials"))


@admin_bp.route("/homepage-events", methods=["GET", "POST"])
@admin_required
def homepage_events():
    current_app.logger.debug("Entering homepage_events handler")
    per_page = 20
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None

    edit_item = Event.query.get_or_404(edit_id) if edit_id else None

    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        item_id = int(item_id_raw) if item_id_raw.isdigit() else None

        name = request.form.get("name", "").strip()
        date_text = request.form.get("date_text", "").strip()
        location = request.form.get("location", "").strip()
        register_url = request.form.get("register_url", "").strip()
        mode = request.form.get("mode", "").strip()
        display_order_raw = request.form.get("display_order", "0")
        is_active = request.form.get("is_active") == "1"

        try:
            display_order = max(0, int(display_order_raw or 0))
        except (TypeError, ValueError):
            display_order = 0

        if len(name) < 3:
            current_app.logger.warning("Attempted to save event with name < 3 characters")
            flash("Event name is required.", "danger")
            return redirect(url_for("admin.homepage_events", q=q, page=page, edit=item_id or ""))

        try:
            row = Event.query.get_or_404(item_id) if item_id else Event()
            row.name = name
            row.date_text = date_text
            row.location = location
            row.register_url = register_url
            row.mode = mode
            img = request.files.get("image")
            if img and img.filename:
                row.image_path = _upload_ai_lab_asset(
                    img,
                    subdir="events",
                    allowed_exts=ALLOWED_AI_IMAGE_EXTENSIONS,
                )
            row.display_order = display_order
            row.is_active = is_active
            db.session.add(row)
            db.session.commit()
            current_app.logger.info(f"Event '{name}' saved successfully (ID: {row.id if hasattr(row, 'id') else 'new'})")
            flash("Event saved.", "success")
        except (ValueError, SQLAlchemyError) as exc:
            db.session.rollback()
            current_app.logger.error(f"Error saving event: {exc}")
            flash(str(exc) if isinstance(exc, ValueError) else "Could not save event.", "danger")
        return redirect(url_for("admin.homepage_events"))

    query = Event.query
    if q:
        query = query.filter(Event.name.ilike(f"%{q}%"))
    total = query.count()
    items = (
        query.order_by(Event.display_order.asc(), Event.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/homepage_events.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )


@admin_bp.post("/homepage-events/<int:item_id>/delete")
@admin_required
def homepage_events_delete(item_id: int):
    current_app.logger.debug(f"Entering homepage_events_delete handler for ID {item_id}")
    row = Event.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        current_app.logger.info(f"Event ID {item_id} deleted successfully")
        flash("Event deleted.", "info")
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error(f"Error deleting event ID {item_id}: {exc}")
        flash("Could not delete event.", "danger")
    return redirect(url_for("admin.homepage_events"))


# =========================
# Courses catalog CMS
# =========================
@admin_bp.route("/courses/page-content", methods=["GET", "POST"])
@admin_required
def courses_page_content():
    keys = [
        ("hero_heading", "Hero heading"),
        ("hero_subtitle", "Hero subtitle"),
        ("meta_description", "Meta description (SEO)"),
        ("meta_keywords", "Meta keywords (SEO)"),
    ]
    if request.method == "POST":
        try:
            for key, _label in keys:
                val = (request.form.get(key, "") or "").strip()
                row = CoursesPageContent.query.filter_by(key=key).first()
                if row is None:
                    row = CoursesPageContent(key=key, value=val)
                else:
                    row.value = val
                db.session.add(row)
            db.session.commit()
            flash("Courses page content saved.", "success")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Could not save.", "danger")
        return redirect(url_for("admin.courses_page_content"))
    values = {k: "" for k, _ in keys}
    try:
        for row in CoursesPageContent.query.all():
            if row.key in values:
                values[row.key] = row.value or ""
    except Exception:
        pass
    return render_template("admin/courses_page_content.html", keys=keys, values=values)


@admin_bp.route("/courses/learning-paths", methods=["GET", "POST"])
@admin_required
def course_learning_paths():
    per_page = 25
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None
    edit_item = CourseLearningPath.query.get_or_404(edit_id) if edit_id else None
    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        item_id = int(item_id_raw) if item_id_raw.isdigit() else None
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        steps = request.form.get("steps", "").strip()
        display_order_raw = request.form.get("display_order", "0")
        is_active = request.form.get("is_active") == "1"
        try:
            display_order = max(0, int(display_order_raw or 0))
        except (TypeError, ValueError):
            display_order = 0
        if len(title) < 2:
            flash("Title is required.", "danger")
            return redirect(url_for("admin.course_learning_paths", q=q, page=page, edit=item_id or ""))
        try:
            row = CourseLearningPath.query.get_or_404(item_id) if item_id else CourseLearningPath()
            row.title = title
            row.description = description
            row.steps = steps
            row.display_order = display_order
            row.is_active = is_active
            db.session.add(row)
            db.session.commit()
            flash("Learning path saved.", "success")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Could not save learning path.", "danger")
        return redirect(url_for("admin.course_learning_paths"))
    query = CourseLearningPath.query
    if q:
        query = query.filter(CourseLearningPath.title.ilike(f"%{q}%"))
    total = query.count()
    items = (
        query.order_by(CourseLearningPath.display_order.asc(), CourseLearningPath.id.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/course_learning_paths.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )


@admin_bp.post("/courses/learning-paths/<int:item_id>/delete")
@admin_required
def course_learning_paths_delete(item_id: int):
    row = CourseLearningPath.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        flash("Learning path deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete.", "danger")
    return redirect(url_for("admin.course_learning_paths"))


@admin_bp.route("/courses/showcase-projects", methods=["GET", "POST"])
@admin_required
def course_showcase_projects():
    per_page = 24
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None
    edit_item = CourseShowcaseProject.query.get_or_404(edit_id) if edit_id else None
    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        item_id = int(item_id_raw) if item_id_raw.isdigit() else None
        title = request.form.get("title", "").strip() or "Project"
        description = request.form.get("description", "").strip()
        technologies = request.form.get("technologies", "").strip()
        display_order_raw = request.form.get("display_order", "0")
        is_active = request.form.get("is_active") == "1"
        try:
            display_order = max(0, int(display_order_raw or 0))
        except (TypeError, ValueError):
            display_order = 0
        try:
            row = CourseShowcaseProject.query.get_or_404(item_id) if item_id else CourseShowcaseProject(title=title, image_path="")
            row.title = title
            row.description = description
            row.technologies = technologies
            row.display_order = display_order
            row.is_active = is_active
            img = request.files.get("image")
            if img and img.filename:
                row.image_path = _upload_ai_lab_asset(
                    img,
                    subdir="courses/showcase",
                    allowed_exts=ALLOWED_AI_IMAGE_EXTENSIONS,
                )
            if not item_id and not (row.image_path or "").strip():
                raise ValueError("Please upload an image when creating a new showcase project.")
            db.session.add(row)
            db.session.commit()
            flash("Showcase project saved.", "success")
        except (ValueError, SQLAlchemyError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else "Could not save project.", "danger")
        return redirect(url_for("admin.course_showcase_projects"))
    query = CourseShowcaseProject.query
    if q:
        query = query.filter(CourseShowcaseProject.title.ilike(f"%{q}%"))
    total = query.count()
    items = (
        query.order_by(CourseShowcaseProject.display_order.asc(), CourseShowcaseProject.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/course_showcase_projects.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )


@admin_bp.post("/courses/showcase-projects/<int:item_id>/delete")
@admin_required
def course_showcase_projects_delete(item_id: int):
    row = CourseShowcaseProject.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        flash("Project deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete.", "danger")
    return redirect(url_for("admin.course_showcase_projects"))


@admin_bp.route("/courses/cert-highlights", methods=["GET", "POST"])
@admin_required
def course_cert_highlights():
    per_page = 25
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None
    edit_item = CourseCertHighlight.query.get_or_404(edit_id) if edit_id else None
    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        item_id = int(item_id_raw) if item_id_raw.isdigit() else None
        title = request.form.get("title", "").strip()
        subtitle = request.form.get("subtitle", "").strip()
        icon = (request.form.get("icon", "🏆") or "🏆").strip()[:16]
        display_order_raw = request.form.get("display_order", "0")
        is_active = request.form.get("is_active") == "1"
        try:
            display_order = max(0, int(display_order_raw or 0))
        except (TypeError, ValueError):
            display_order = 0
        if len(title) < 2:
            flash("Title is required.", "danger")
            return redirect(url_for("admin.course_cert_highlights", q=q, page=page, edit=item_id or ""))
        try:
            row = CourseCertHighlight.query.get_or_404(item_id) if item_id else CourseCertHighlight()
            row.title = title
            row.subtitle = subtitle
            row.icon = icon
            row.display_order = display_order
            row.is_active = is_active
            db.session.add(row)
            db.session.commit()
            flash("Certification card saved.", "success")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Could not save.", "danger")
        return redirect(url_for("admin.course_cert_highlights"))
    query = CourseCertHighlight.query
    if q:
        query = query.filter(CourseCertHighlight.title.ilike(f"%{q}%"))
    total = query.count()
    items = (
        query.order_by(CourseCertHighlight.display_order.asc(), CourseCertHighlight.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/course_cert_highlights.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )


@admin_bp.post("/courses/cert-highlights/<int:item_id>/delete")
@admin_required
def course_cert_highlights_delete(item_id: int):
    row = CourseCertHighlight.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        flash("Deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete.", "danger")
    return redirect(url_for("admin.course_cert_highlights"))


# ==========================================
# Unified About Page Manager (CMS)
# ==========================================

def _upload_about_image(file_storage):
    """Upload and optimize images for the About page sections."""
    if not file_storage or not file_storage.filename:
        return None
    safe_name = secure_filename(file_storage.filename)
    if "." not in safe_name:
        raise ValueError("Invalid image file name.")
    ext = safe_name.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_PRODUCT_IMAGE_EXTENSIONS:
        raise ValueError("Allowed image formats: png, jpg, jpeg, webp, gif.")
    
    upload_rel_dir = os.path.join("uploads", "about")
    upload_abs_dir = os.path.join(current_app.static_folder, upload_rel_dir)
    os.makedirs(upload_abs_dir, exist_ok=True)
    
    # Save with a secure prefix to prevent collisions
    unique_name = f"{uuid4().hex}_{safe_name}"
    abs_path = os.path.join(upload_abs_dir, unique_name)
    file_storage.save(abs_path)
    return f"{upload_rel_dir.replace(os.sep, '/')}/{unique_name}"


@admin_bp.route("/about/manager", methods=["GET", "POST"])
@admin_required
def about_manager():
    """Unified full-page CMS manager for all About page content, configurations, and sections."""
    from datetime import datetime

    def get_content(key: str, default: str = "") -> str:
        row = AboutContent.query.filter_by(key=key).first()
        return (row.value if row and row.value is not None else default) or default

    def set_content(key: str, value: str):
        row = AboutContent.query.filter_by(key=key).first()
        if not row:
            row = AboutContent(key=key, value=value or "")
            db.session.add(row)
        else:
            row.value = value or ""
            row.updated_at = datetime.utcnow()

    # Load version snapshots and activity logs
    versions = AboutVersion.query.order_by(AboutVersion.created_at.desc()).limit(15).all()
    logs = AboutActivityLog.query.order_by(AboutActivityLog.timestamp.desc()).limit(30).all()

    # Handle form submission
    if request.method == "POST":
        action = request.form.get("action", "save")  # 'save' (Draft) or 'publish' (Live)
        
        # Heading validation
        hero_heading = request.form.get("hero_heading", "").strip()
        if not hero_heading:
            flash("About Hero Heading is required.", "danger")
            return redirect(url_for("admin.about_manager"))
            
        if len(hero_heading) < 2 or len(hero_heading) > 160:
            flash("About Hero Heading must be between 2 and 160 characters.", "danger")
            return redirect(url_for("admin.about_manager"))
            
        try:
            # 1. About Hero Section Fields
            set_content("hero_badge_text", request.form.get("hero_badge_text", "").strip())
            set_content("hero_trust_line", request.form.get("hero_trust_line", "").strip())
            set_content("hero_heading", hero_heading)
            set_content("hero_subtitle", request.form.get("hero_subtitle", "").strip())
            set_content("hero_description", request.form.get("hero_description", "").strip())
            
            set_content("hero_primary_btn_text", request.form.get("hero_primary_btn_text", "").strip())
            set_content("hero_primary_btn_link", request.form.get("hero_primary_btn_link", "").strip())
            set_content("hero_secondary_btn_text", request.form.get("hero_secondary_btn_text", "").strip())
            set_content("hero_secondary_btn_link", request.form.get("hero_secondary_btn_link", "").strip())
            
            set_content("hero_stat1_num", request.form.get("hero_stat1_num", "").strip())
            set_content("hero_stat1_lbl", request.form.get("hero_stat1_lbl", "").strip())
            set_content("hero_stat2_num", request.form.get("hero_stat2_num", "").strip())
            set_content("hero_stat2_lbl", request.form.get("hero_stat2_lbl", "").strip())
            set_content("hero_stat3_num", request.form.get("hero_stat3_num", "").strip())
            set_content("hero_stat3_lbl", request.form.get("hero_stat3_lbl", "").strip())
            set_content("hero_stat4_num", request.form.get("hero_stat4_num", "").strip())
            set_content("hero_stat4_lbl", request.form.get("hero_stat4_lbl", "").strip())
            
            set_content("hero_gradient_theme", request.form.get("hero_gradient_theme", "blue-purple").strip())

            # 2. Who We Are Section Fields
            set_content("who_we_are_title", request.form.get("who_we_are_title", "").strip())
            set_content("who_we_are_body", request.form.get("who_we_are_body", "").strip())
            set_content("who_we_are_btn_text", request.form.get("who_we_are_btn_text", "").strip())
            set_content("who_we_are_btn_link", request.form.get("who_we_are_btn_link", "").strip())
            set_content("who_we_are_feature1", request.form.get("who_we_are_feature1", "").strip())
            set_content("who_we_are_feature2", request.form.get("who_we_are_feature2", "").strip())
            set_content("who_we_are_feature3", request.form.get("who_we_are_feature3", "").strip())

            # 3. Mission / Vision Section Fields
            set_content("mission_icon", request.form.get("mission_icon", "🎯").strip())
            set_content("mission_heading", request.form.get("mission_heading", "Our Mission").strip())
            set_content("mission_text", request.form.get("mission_text", "").strip())
            
            set_content("vision_icon", request.form.get("vision_icon", "🚀").strip())
            set_content("vision_heading", request.form.get("vision_heading", "Our Vision").strip())
            set_content("vision_text", request.form.get("vision_text", "").strip())

            # 4. JSON-backed Repeater sections (What We Offer & Why Choose Us)
            set_content("what_we_offer_cards", request.form.get("what_we_offer_cards", "[]").strip())
            set_content("why_choose_us_cards", request.form.get("why_choose_us_cards", "[]").strip())

            # 5. Dynamic SEO Properties
            set_content("seo_meta_title", request.form.get("seo_meta_title", "").strip())
            set_content("seo_meta_description", request.form.get("seo_meta_description", "").strip())
            set_content("seo_keywords", request.form.get("seo_keywords", "").strip())
            set_content("seo_canonical_url", request.form.get("seo_canonical_url", "").strip())
            set_content("seo_schema_markup", request.form.get("seo_schema_markup", "").strip())

            # 6. Global Section Visibility Configuration
            set_content("section_visibilities", request.form.get("section_visibilities", "{}").strip())

            # 7. File uploads
            if "hero_image" in request.files:
                file = request.files["hero_image"]
                if file and file.filename:
                    hero_img_path = _upload_about_image(file)
                    if hero_img_path:
                        set_content("hero_image", hero_img_path)
            
            if "who_we_are_side_image" in request.files:
                file = request.files["who_we_are_side_image"]
                if file and file.filename:
                    side_img_path = _upload_about_image(file)
                    if side_img_path:
                        set_content("who_we_are_side_image", side_img_path)
                        
            if "seo_og_image" in request.files:
                file = request.files["seo_og_image"]
                if file and file.filename:
                    og_img_path = _upload_about_image(file)
                    if og_img_path:
                        set_content("seo_og_image", og_img_path)

            # Update Publication Status
            is_published = "1" if action == "publish" else "0"
            set_content("is_published", is_published)
            
            db.session.commit()

            # Record Activity Logging in Database
            from flask_login import current_user
            admin_email = current_user.email if current_user and getattr(current_user, "is_authenticated", False) else "system"
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
            action_desc = "Published About Page changes to live website" if action == "publish" else "Saved About Page changes as Draft"
            
            log_entry = AboutActivityLog(
                action=action_desc,
                admin_email=admin_email,
                ip_address=ip
            )
            db.session.add(log_entry)
            
            # Versioning - create a restore-snapshot if published
            if action == "publish":
                copy_keys = [
                    "hero_badge_text", "hero_trust_line", "hero_heading", "hero_subtitle", "hero_description",
                    "hero_primary_btn_text", "hero_primary_btn_link", "hero_secondary_btn_text", "hero_secondary_btn_link",
                    "hero_stat1_num", "hero_stat1_lbl", "hero_stat2_num", "hero_stat2_lbl",
                    "hero_stat3_num", "hero_stat3_lbl", "hero_stat4_num", "hero_stat4_lbl",
                    "hero_gradient_theme", "hero_image",
                    "who_we_are_title", "who_we_are_body", "who_we_are_side_image",
                    "who_we_are_btn_text", "who_we_are_btn_link",
                    "who_we_are_feature1", "who_we_are_feature2", "who_we_are_feature3",
                    "mission_icon", "mission_heading", "mission_text",
                    "vision_icon", "vision_heading", "vision_text",
                    "what_we_offer_cards", "why_choose_us_cards",
                    "seo_meta_title", "seo_meta_description", "seo_keywords", "seo_og_image", "seo_canonical_url", "seo_schema_markup",
                    "section_visibilities"
                ]
                snapshot = {}
                for k in copy_keys:
                    snapshot[k] = get_content(k, "")
                
                import json
                version_entry = AboutVersion(
                    version_data=json.dumps(snapshot),
                    published_by=admin_email
                )
                db.session.add(version_entry)
                
            db.session.commit()
            
            msg = "About page successfully published to live site!" if action == "publish" else "About page draft saved successfully."
            flash(msg, "success")
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(f"Error in about_manager POST: {exc}", exc_info=True)
            flash(f"An error occurred: {exc}", "danger")
            
        return redirect(url_for("admin.about_manager"))

    # Load copy settings
    copy_keys = [
        "hero_badge_text", "hero_trust_line", "hero_heading", "hero_subtitle", "hero_description",
        "hero_primary_btn_text", "hero_primary_btn_link", "hero_secondary_btn_text", "hero_secondary_btn_link",
        "hero_stat1_num", "hero_stat1_lbl", "hero_stat2_num", "hero_stat2_lbl",
        "hero_stat3_num", "hero_stat3_lbl", "hero_stat4_num", "hero_stat4_lbl",
        "hero_gradient_theme", "hero_image",
        "who_we_are_title", "who_we_are_body", "who_we_are_side_image",
        "who_we_are_btn_text", "who_we_are_btn_link",
        "who_we_are_feature1", "who_we_are_feature2", "who_we_are_feature3",
        "mission_icon", "mission_heading", "mission_text",
        "vision_icon", "vision_heading", "vision_text",
        "what_we_offer_cards", "why_choose_us_cards",
        "seo_meta_title", "seo_meta_description", "seo_keywords", "seo_og_image", "seo_canonical_url", "seo_schema_markup",
        "section_visibilities", "is_published"
    ]
    
    content = {}
    for k in copy_keys:
        if k == "hero_badge_text":
            content[k] = get_content(k, "AI • Robotics • Electronics")
        elif k == "hero_trust_line":
            content[k] = get_content(k, "India's premier practical tech ecosystem")
        elif k == "hero_heading":
            content[k] = get_content(k, "About Skill Orbit India")
        elif k == "hero_subtitle":
            content[k] = get_content(k, "Empowering Future Tech Innovators through practical, hands-on learning.")
        elif k == "hero_stat1_num":
            content[k] = get_content(k, "5000+")
        elif k == "hero_stat1_lbl":
            content[k] = get_content(k, "Students Trained")
        elif k == "hero_stat2_num":
            content[k] = get_content(k, "120+")
        elif k == "hero_stat2_lbl":
            content[k] = get_content(k, "Workshops")
        elif k == "hero_stat3_num":
            content[k] = get_content(k, "50+")
        elif k == "hero_stat3_lbl":
            content[k] = get_content(k, "School Partners")
        elif k == "hero_stat4_num":
            content[k] = get_content(k, "24×7")
        elif k == "hero_stat4_lbl":
            content[k] = get_content(k, "Support")
        elif k == "hero_gradient_theme":
            content[k] = get_content(k, "blue-purple")
        elif k == "mission_icon":
            content[k] = get_content(k, "🎯")
        elif k == "mission_heading":
            content[k] = get_content(k, "Our Mission")
        elif k == "vision_icon":
            content[k] = get_content(k, "🚀")
        elif k == "vision_heading":
            content[k] = get_content(k, "Our Vision")
        elif k == "what_we_offer_cards":
            content[k] = get_content(k, "[]")
        elif k == "why_choose_us_cards":
            content[k] = get_content(k, "[]")
        elif k == "section_visibilities":
            content[k] = get_content(k, "{}")
        elif k == "is_published":
            content[k] = get_content(k, "0")
        else:
            content[k] = get_content(k, "")

    # Load dynamic lists
    team = AboutTeamMember.query.order_by(AboutTeamMember.display_order.asc(), AboutTeamMember.id.desc()).all()
    timeline = AboutTimelineEntry.query.order_by(AboutTimelineEntry.display_order.asc(), AboutTimelineEntry.id.asc()).all()
    gallery = AboutGalleryImage.query.order_by(AboutGalleryImage.display_order.asc(), AboutGalleryImage.id.desc()).all()
    partners = AboutPartnerLogo.query.order_by(AboutPartnerLogo.display_order.asc(), AboutPartnerLogo.id.desc()).all()
    recognition = AboutRecognition.query.order_by(AboutRecognition.display_order.asc(), AboutRecognition.id.desc()).all()
    counters = AboutCounter.query.order_by(AboutCounter.display_order.asc(), AboutCounter.id.desc()).all()
    testimonials = AboutTestimonial.query.order_by(AboutTestimonial.display_order.asc(), AboutTestimonial.id.desc()).all()

    # Determine last updated
    last_updated_row = AboutContent.query.order_by(AboutContent.updated_at.desc()).first()
    last_updated = last_updated_row.updated_at if last_updated_row else None

    return render_template(
        "admin/about_manager.html",
        content=content,
        team=team,
        timeline=timeline,
        gallery=gallery,
        partners=partners,
        recognition=recognition,
        counters=counters,
        testimonials=testimonials,
        versions=versions,
        logs=logs,
        last_updated=last_updated
    )


@admin_bp.post("/about/restore/<int:version_id>")
@admin_required
def about_restore_version(version_id: int):
    """Restore About Page copies from a historical snapshot."""
    version = AboutVersion.query.get_or_404(version_id)
    try:
        import json
        snapshot = json.loads(version.version_data)
        
        def set_content(key: str, value: str):
            row = AboutContent.query.filter_by(key=key).first()
            if not row:
                row = AboutContent(key=key, value=value or "")
                db.session.add(row)
            else:
                row.value = value or ""
                row.updated_at = datetime.utcnow()
                
        for k, v in snapshot.items():
            set_content(k, v)
            
        # Log version restore
        from flask_login import current_user
        admin_email = current_user.email if current_user and getattr(current_user, "is_authenticated", False) else "system"
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
        
        log_entry = AboutActivityLog(
            action=f"Restored About Page to version from {version.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            admin_email=admin_email,
            ip_address=ip
        )
        db.session.add(log_entry)
        db.session.commit()
        flash(f"About Page copy successfully restored to historical version!", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"Failed to restore About Page version: {exc}")
        flash(f"Failed to restore version: {exc}", "danger")
        
    return redirect(url_for("admin.about_manager"))


@admin_bp.post("/about/delete-image/<image_field>")
@admin_required
def about_delete_image(image_field: str):
    """Deletes uploaded hero or story images from disk and database."""
    allowed_fields = {"hero_image", "who_we_are_side_image", "seo_og_image"}
    if image_field not in allowed_fields:
        flash("Invalid operation.", "danger")
        return redirect(url_for("admin.about_manager"))
        
    row = AboutContent.query.filter_by(key=image_field).first()
    if row and row.value:
        filepath = os.path.join(current_app.static_folder, row.value)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                current_app.logger.warning(f"Could not remove file {filepath}: {e}")
        
        row.value = ""
        try:
            db.session.commit()
            flash("Image deleted successfully.", "info")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Database update failed.", "danger")
            
    return redirect(url_for("admin.about_manager"))


@admin_bp.post("/about/reorder")
@admin_required
def about_reorder():
    """Bulk update display orders for dynamic list managers (Timeline, Team, Gallery, etc.)."""
    try:
        data = request.get_json() or {}
        model_name = data.get("model")
        ids = data.get("ids", [])
        
        model_map = {
            "team": AboutTeamMember,
            "timeline": AboutTimelineEntry,
            "gallery": AboutGalleryImage,
            "partners": AboutPartnerLogo,
            "recognition": AboutRecognition,
            "counters": AboutCounter,
            "testimonials": AboutTestimonial
        }
        
        model_cls = model_map.get(model_name)
        if not model_cls:
            return jsonify({"success": False, "error": "Invalid model name"}), 400
            
        for index, item_id in enumerate(ids):
            row = model_cls.query.get(int(item_id))
            if row:
                row.display_order = index
                
        db.session.commit()
        return jsonify({"success": True})
    except Exception as exc:
        db.session.rollback()
        return jsonify({"success": False, "error": str(exc)}), 500


# =========================
# Homepage CMS Manager
# =========================

@admin_bp.route("/homepage/manager", methods=["GET", "POST"])
@admin_required
def homepage_manager():
    """Unified full-page CMS manager for all Homepage content, configurations, sections, theme, and animations."""
    from datetime import datetime

    def get_content(key: str, default: str = "") -> str:
        row = HomeContent.query.filter_by(key=key).first()
        return (row.value if row and row.value is not None else default) or default

    def set_content(key: str, value: str):
        row = HomeContent.query.filter_by(key=key).first()
        if not row:
            row = HomeContent(key=key, value=value or "")
            db.session.add(row)
        else:
            row.value = value or ""
            row.updated_at = datetime.utcnow()

    # Load version snapshots and activity logs
    versions = HomeVersion.query.order_by(HomeVersion.created_at.desc()).limit(15).all()
    logs = HomeActivityLog.query.order_by(HomeActivityLog.timestamp.desc()).limit(30).all()

    # Handle form submission
    if request.method == "POST":
        action = request.form.get("action", "save")  # 'save' (Draft) or 'publish' (Live)
        
        # Heading validation
        hero_heading = request.form.get("hero_heading", "").strip()
        if not hero_heading:
            flash("Homepage Hero Heading is required.", "danger")
            return redirect(url_for("admin.homepage_manager"))
            
        if len(hero_heading) < 2 or len(hero_heading) > 160:
            flash("Homepage Hero Heading must be between 2 and 160 characters.", "danger")
            return redirect(url_for("admin.homepage_manager"))
            
        try:
            # 1. Hero Section Content & Config
            set_content("hero_badge_text", request.form.get("hero_badge_text", "").strip())
            set_content("hero_badge_subtext", request.form.get("hero_badge_subtext", "").strip())
            set_content("hero_heading", hero_heading)
            set_content("hero_description", request.form.get("hero_description", "").strip())
            set_content("hero_primary_btn_text", request.form.get("hero_primary_btn_text", "").strip())
            set_content("hero_primary_btn_link", request.form.get("hero_primary_btn_link", "").strip())
            set_content("hero_secondary_btn_text", request.form.get("hero_secondary_btn_text", "").strip())
            set_content("hero_secondary_btn_link", request.form.get("hero_secondary_btn_link", "").strip())
            set_content("hero_tertiary_btn_text", request.form.get("hero_tertiary_btn_text", "").strip())
            set_content("hero_tertiary_btn_link", request.form.get("hero_tertiary_btn_link", "").strip())
            set_content("hero_layout", request.form.get("hero_layout", "default").strip())
            set_content("hero_ai_lab_title", request.form.get("hero_ai_lab_title", "").strip())
            set_content("hero_ai_lab_description", request.form.get("hero_ai_lab_description", "").strip())

            # 2. Section Visibilities Configuration
            set_content("section_visibilities", request.form.get("section_visibilities", "{}").strip())

            # 3. Repeaters stored as JSON text
            set_content("stats_kpis", request.form.get("stats_kpis", "[]").strip())
            set_content("trusted_partners", request.form.get("trusted_partners", "[]").strip())
            set_content("featured_courses", request.form.get("featured_courses", "[]").strip())
            
            # AI Lab Showcase content
            set_content("ai_lab_heading", request.form.get("ai_lab_heading", "").strip())
            set_content("ai_lab_description", request.form.get("ai_lab_description", "").strip())
            set_content("ai_lab_equipment", request.form.get("ai_lab_equipment", "[]").strip())
            set_content("ai_lab_cta_text", request.form.get("ai_lab_cta_text", "").strip())
            set_content("ai_lab_cta_link", request.form.get("ai_lab_cta_link", "").strip())

            # Repeaters lists
            set_content("internships_list", request.form.get("internships_list", "[]").strip())
            set_content("services_list", request.form.get("services_list", "[]").strip())
            set_content("learning_paths", request.form.get("learning_paths", "[]").strip())
            set_content("testimonials_list", request.form.get("testimonials_list", "[]").strip())
            set_content("projects_list", request.form.get("projects_list", "[]").strip())
            set_content("events_list", request.form.get("events_list", "[]").strip())
            set_content("achievements_list", request.form.get("achievements_list", "[]").strip())
            set_content("faculty_list", request.form.get("faculty_list", "[]").strip())
            set_content("cta_banners", request.form.get("cta_banners", "[]").strip())
            set_content("faqs_list", request.form.get("faqs_list", "[]").strip())

            # Footer Promo
            set_content("footer_promo_text", request.form.get("footer_promo_text", "").strip())
            set_content("footer_promo_btn_text", request.form.get("footer_promo_btn_text", "").strip())
            set_content("footer_promo_btn_link", request.form.get("footer_promo_btn_link", "").strip())
            set_content("footer_promo_badge", request.form.get("footer_promo_badge", "").strip())

            # SEO
            set_content("seo_meta_title", request.form.get("seo_meta_title", "").strip())
            set_content("seo_meta_description", request.form.get("seo_meta_description", "").strip())
            set_content("seo_keywords", request.form.get("seo_keywords", "").strip())
            set_content("seo_canonical_url", request.form.get("seo_canonical_url", "").strip())
            set_content("seo_schema_markup", request.form.get("seo_schema_markup", "").strip())

            # Theme Settings
            set_content("theme_primary_color", request.form.get("theme_primary_color", "#4F46E5").strip())
            set_content("theme_secondary_color", request.form.get("theme_secondary_color", "#06B6D4").strip())
            set_content("theme_gradient_theme", request.form.get("theme_gradient_theme", "blue-purple").strip())
            set_content("theme_card_radius", request.form.get("theme_card_radius", "22px").strip())
            set_content("theme_shadows", request.form.get("theme_shadows", "glow").strip())
            set_content("theme_typography", request.form.get("theme_typography", "Outfit").strip())
            set_content("theme_section_spacing", request.form.get("theme_section_spacing", "medium").strip())
            set_content("theme_dark_mode", request.form.get("theme_dark_mode", "1").strip())

            # Animations
            set_content("anim_scroll", request.form.get("anim_scroll", "1").strip())
            set_content("anim_hover", request.form.get("anim_hover", "1").strip())
            set_content("anim_parallax", request.form.get("anim_parallax", "1").strip())
            set_content("anim_counter_speed", request.form.get("anim_counter_speed", "1500").strip())
            set_content("anim_transition_speed", request.form.get("anim_transition_speed", "600").strip())
            set_content("anim_floating_effects", request.form.get("anim_floating_effects", "1").strip())
            set_content("anim_speed", request.form.get("anim_speed", "normal").strip())

            # File uploads
            upload_fields = [
                "hero_image", "hero_ai_lab_image", "hero_robotics_image", "hero_workshop_image",
                "hero_student_activity_image", "ai_lab_image", "footer_promo_image",
                "seo_og_image", "seo_twitter_image"
            ]
            for f in upload_fields:
                if f in request.files:
                    file = request.files[f]
                    if file and file.filename:
                        img_path = _upload_hero_image(file)
                        if img_path:
                            set_content(f, img_path)

            # Publish status flag
            is_published = "1" if action == "publish" else "0"
            set_content("is_published", is_published)
            
            db.session.commit()

            # Record Activity Logging in Database
            from flask_login import current_user
            admin_email = current_user.email if current_user and getattr(current_user, "is_authenticated", False) else "system"
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
            action_desc = "Published Homepage changes to live website" if action == "publish" else "Saved Homepage changes as Draft"
            
            log_entry = HomeActivityLog(
                action=action_desc,
                admin_email=admin_email,
                ip_address=ip
            )
            db.session.add(log_entry)

            # Ensure we sync with legacys to maintain backward compatibility
            hero = HomePageHero.query.first()
            if not hero:
                hero = HomePageHero()
                db.session.add(hero)
            
            hero.badge_text = get_content("hero_badge_text", "AI • Robotics • Electronics")
            hero.badge_subtext = get_content("hero_badge_subtext", "India's learning orbit")
            hero.heading = hero_heading
            hero.description = get_content("hero_description", "")
            hero.primary_button_text = get_content("hero_primary_btn_text", "Explore Courses")
            hero.primary_button_link = get_content("hero_primary_btn_link", "/courses")
            hero.secondary_button_text = get_content("hero_secondary_btn_text", "Book Free Demo")
            hero.secondary_button_link = get_content("hero_secondary_btn_link", "/ai-lab#enquiry")
            hero.tertiary_button_text = get_content("hero_tertiary_btn_text", "Watch Video")
            hero.tertiary_button_link = get_content("hero_tertiary_btn_link", "/courses")
            
            hero.hero_image = get_content("hero_image", "")
            hero.ai_lab_image = get_content("hero_ai_lab_image", "")
            hero.robotics_image = get_content("hero_robotics_image", "")
            hero.workshop_image = get_content("hero_workshop_image", "")
            hero.student_activity_image = get_content("hero_student_activity_image", "")
            
            hero.ai_lab_card_title = get_content("hero_ai_lab_title", "AI & Robotics Lab Atmosphere")
            hero.ai_lab_card_description = get_content("hero_ai_lab_description", "Experience cutting-edge...")
            
            # Pull first 4 KPIs/stats if available to sync with legacy
            import json
            try:
                stats_list = json.loads(get_content("stats_kpis", "[]"))
                if len(stats_list) >= 1:
                    hero.kpi_1_label = stats_list[0].get("number", "5000+")
                    hero.kpi_1_text = stats_list[0].get("label", "Students")
                if len(stats_list) >= 2:
                    hero.kpi_2_label = stats_list[1].get("number", "120+")
                    hero.kpi_2_text = stats_list[1].get("label", "Workshops")
                if len(stats_list) >= 3:
                    hero.kpi_3_label = stats_list[2].get("number", "50+")
                    hero.kpi_3_text = stats_list[2].get("label", "Schools")
                if len(stats_list) >= 4:
                    hero.kpi_4_label = stats_list[3].get("number", "24×7")
                    hero.kpi_4_text = stats_list[3].get("label", "Support")
            except Exception:
                pass
            
            hero.is_published = (action == "publish")
            hero.is_draft = (action == "save")
            hero.published_at = datetime.utcnow() if action == "publish" else hero.published_at
            
            # Versioning - create a restore-snapshot if published
            if action == "publish":
                copy_keys = [
                    "hero_badge_text", "hero_badge_subtext", "hero_heading", "hero_description",
                    "hero_primary_btn_text", "hero_primary_btn_link", "hero_secondary_btn_text", "hero_secondary_btn_link",
                    "hero_tertiary_btn_text", "hero_tertiary_btn_link", "hero_layout", "hero_ai_lab_title", "hero_ai_lab_description",
                    "hero_image", "hero_ai_lab_image", "hero_robotics_image", "hero_workshop_image", "hero_student_activity_image",
                    "stats_kpis", "trusted_partners", "featured_courses",
                    "ai_lab_heading", "ai_lab_description", "ai_lab_image", "ai_lab_video", "ai_lab_equipment", "ai_lab_cta_text", "ai_lab_cta_link",
                    "internships_list", "services_list", "learning_paths", "testimonials_list", "projects_list", "events_list", "achievements_list", "faculty_list",
                    "cta_banners", "faqs_list", "footer_promo_text", "footer_promo_btn_text", "footer_promo_btn_link", "footer_promo_image", "footer_promo_badge",
                    "seo_meta_title", "seo_meta_description", "seo_keywords", "seo_canonical_url", "seo_og_image", "seo_twitter_image", "seo_schema_markup",
                    "theme_primary_color", "theme_secondary_color", "theme_gradient_theme", "theme_card_radius", "theme_shadows", "theme_typography", "theme_section_spacing", "theme_dark_mode",
                    "anim_scroll", "anim_hover", "anim_parallax", "anim_counter_speed", "anim_transition_speed", "anim_floating_effects", "anim_speed",
                    "section_visibilities"
                ]
                snapshot = {}
                for k in copy_keys:
                    snapshot[k] = get_content(k, "")
                
                version_entry = HomeVersion(
                    version_data=json.dumps(snapshot),
                    published_by=admin_email
                )
                db.session.add(version_entry)
                
            db.session.commit()
            msg = "Homepage successfully published to live site!" if action == "publish" else "Homepage draft saved successfully."
            flash(msg, "success")
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(f"Error in homepage_manager POST: {exc}", exc_info=True)
            flash(f"An error occurred: {exc}", "danger")
            
        return redirect(url_for("admin.homepage_manager"))

    # Load copy settings
    copy_keys = [
        "hero_badge_text", "hero_badge_subtext", "hero_heading", "hero_description",
        "hero_primary_btn_text", "hero_primary_btn_link", "hero_secondary_btn_text", "hero_secondary_btn_link",
        "hero_tertiary_btn_text", "hero_tertiary_btn_link", "hero_layout", "hero_ai_lab_title", "hero_ai_lab_description",
        "hero_image", "hero_ai_lab_image", "hero_robotics_image", "hero_workshop_image", "hero_student_activity_image",
        "stats_kpis", "trusted_partners", "featured_courses",
        "ai_lab_heading", "ai_lab_description", "ai_lab_image", "ai_lab_video", "ai_lab_equipment", "ai_lab_cta_text", "ai_lab_cta_link",
        "internships_list", "services_list", "learning_paths", "testimonials_list", "projects_list", "events_list", "achievements_list", "faculty_list",
        "cta_banners", "faqs_list", "footer_promo_text", "footer_promo_btn_text", "footer_promo_btn_link", "footer_promo_image", "footer_promo_badge",
        "seo_meta_title", "seo_meta_description", "seo_keywords", "seo_canonical_url", "seo_og_image", "seo_twitter_image", "seo_schema_markup",
        "theme_primary_color", "theme_secondary_color", "theme_gradient_theme", "theme_card_radius", "theme_shadows", "theme_typography", "theme_section_spacing", "theme_dark_mode",
        "anim_scroll", "anim_hover", "anim_parallax", "anim_counter_speed", "anim_transition_speed", "anim_floating_effects", "anim_speed",
        "section_visibilities", "is_published"
    ]
    
    content = {}
    for k in copy_keys:
        if k == "hero_badge_text":
            content[k] = get_content(k, "AI • Robotics • Electronics")
        elif k == "hero_badge_subtext":
            content[k] = get_content(k, "India's learning orbit")
        elif k == "hero_heading":
            content[k] = get_content(k, "Premium AI + Robotics Learning Platform")
        elif k == "hero_description":
            content[k] = get_content(k, "Learn AI, Robotics, IoT, Embedded Systems and build real projects. Shop curated kits, earn verified certificates, and access internship pathways — built for outcomes, not just content.")
        elif k == "hero_primary_btn_text":
            content[k] = get_content(k, "Explore Courses")
        elif k == "hero_primary_btn_link":
            content[k] = get_content(k, "/courses")
        elif k == "hero_secondary_btn_text":
            content[k] = get_content(k, "Book Free Demo")
        elif k == "hero_secondary_btn_link":
            content[k] = get_content(k, "/ai-lab#enquiry")
        elif k == "hero_tertiary_btn_text":
            content[k] = get_content(k, "Watch Video")
        elif k == "hero_tertiary_btn_link":
            content[k] = get_content(k, "/courses")
        elif k == "hero_layout":
            content[k] = get_content(k, "default")
        elif k == "hero_ai_lab_title":
            content[k] = get_content(k, "AI & Robotics Lab Atmosphere")
        elif k == "hero_ai_lab_description":
            content[k] = get_content(k, "Experience cutting-edge AI and robotics learning environment.")
        elif k == "stats_kpis":
            content[k] = get_content(k, '[{"number": "5000+", "label": "Students", "icon": "🎓", "speed": "1500"}, {"number": "120+", "label": "Workshops", "icon": "⚡", "speed": "1500"}, {"number": "50+", "label": "Schools", "icon": "🏫", "speed": "1500"}, {"number": "24×7", "label": "Support", "icon": "📞", "speed": "1500"}]')
        elif k == "trusted_partners":
            content[k] = get_content(k, '[{"name": "Arduino", "logo": "", "link": ""}, {"name": "NVIDIA", "logo": "", "link": ""}, {"name": "Raspberry Pi", "logo": "", "link": ""}, {"name": "Microsoft", "logo": "", "link": ""}, {"name": "AWS", "logo": "", "link": ""}, {"name": "ESPRESSIF", "logo": "", "link": ""}]')
        elif k == "featured_courses":
            content[k] = get_content(k, "[]")
        elif k == "ai_lab_heading":
            content[k] = get_content(k, "AI Lab Setup for Schools & Colleges")
        elif k == "ai_lab_description":
            content[k] = get_content(k, "Premium NEP-aligned labs with hardware + curriculum + teacher enablement.")
        elif k == "ai_lab_equipment":
            content[k] = get_content(k, '["Complete AI Lab Setup", "Robotics Kits", "IoT Modules", "Teacher Training", "Curriculum Support", "Installation & Maintenance"]')
        elif k == "ai_lab_cta_text":
            content[k] = get_content(k, "Request proposal")
        elif k == "ai_lab_cta_link":
            content[k] = get_content(k, "/ai-lab#enquiry")
        elif k == "internships_list":
            content[k] = get_content(k, "[]")
        elif k == "services_list":
            content[k] = get_content(k, "[]")
        elif k == "learning_paths":
            content[k] = get_content(k, "[]")
        elif k == "testimonials_list":
            content[k] = get_content(k, "[]")
        elif k == "projects_list":
            content[k] = get_content(k, '[{"title": "Line Follower Robot", "description": "Robotics foundations with sensors.", "tech_stack": "Arduino, IR Sensors", "demo_link": "", "github_link": "", "is_featured": "1"}, {"title": "AI Face Detection", "description": "Computer vision demo pipeline.", "tech_stack": "Python, OpenCV", "demo_link": "", "github_link": "", "is_featured": "1"}, {"title": "Smart Home Automation", "description": "IoT + automation workflows.", "tech_stack": "ESP32, Blynk", "demo_link": "", "github_link": "", "is_featured": "1"}, {"title": "Gesture Control Robot", "description": "Control + vision interaction.", "tech_stack": "Arduino, MPU6050", "demo_link": "", "github_link": "", "is_featured": "1"}, {"title": "Obstacle Avoidance Bot", "description": "Navigation + sensor fusion.", "tech_stack": "Arduino, Ultrasonic Sensor", "demo_link": "", "github_link": "", "is_featured": "1"}]')
        elif k == "events_list":
            content[k] = get_content(k, "[]")
        elif k == "achievements_list":
            content[k] = get_content(k, "[]")
        elif k == "faculty_list":
            content[k] = get_content(k, "[]")
        elif k == "cta_banners":
            content[k] = get_content(k, "[]")
        elif k == "faqs_list":
            content[k] = get_content(k, "[]")
        elif k == "footer_promo_text":
            content[k] = get_content(k, "Ready to orbit your career?")
        elif k == "footer_promo_btn_text":
            content[k] = get_content(k, "Create free account")
        elif k == "footer_promo_btn_link":
            content[k] = get_content(k, "/auth/signup")
        elif k == "footer_promo_badge":
            content[k] = get_content(k, "Join thousands building hardware skills with guided paths and employer-ready proof.")
        elif k == "seo_meta_title":
            content[k] = get_content(k, "Skill Orbit India — Learn, Build, Certify")
        elif k == "seo_meta_description":
            content[k] = get_content(k, "Skill Orbit India: practical tech courses, curated electronics kits, verified certificates, internships, IT services, and AI lab setup — built for outcomes, not just content.")
        elif k == "seo_keywords":
            content[k] = get_content(k, "Skill Orbit India, tech courses, electronics store, certificates, internships, IT services, AI lab, online learning India")
        elif k == "theme_primary_color":
            content[k] = get_content(k, "#4F46E5")
        elif k == "theme_secondary_color":
            content[k] = get_content(k, "#06B6D4")
        elif k == "theme_gradient_theme":
            content[k] = get_content(k, "blue-purple")
        elif k == "theme_card_radius":
            content[k] = get_content(k, "22px")
        elif k == "theme_shadows":
            content[k] = get_content(k, "glow")
        elif k == "theme_typography":
            content[k] = get_content(k, "Outfit")
        elif k == "theme_section_spacing":
            content[k] = get_content(k, "medium")
        elif k == "theme_dark_mode":
            content[k] = get_content(k, "1")
        elif k == "anim_scroll":
            content[k] = get_content(k, "1")
        elif k == "anim_hover":
            content[k] = get_content(k, "1")
        elif k == "anim_parallax":
            content[k] = get_content(k, "1")
        elif k == "anim_counter_speed":
            content[k] = get_content(k, "1500")
        elif k == "anim_transition_speed":
            content[k] = get_content(k, "600")
        elif k == "anim_floating_effects":
            content[k] = get_content(k, "1")
        elif k == "anim_speed":
            content[k] = get_content(k, "normal")
        elif k == "section_visibilities":
            content[k] = get_content(k, "{}")
        elif k == "is_published":
            content[k] = get_content(k, "0")
        else:
            content[k] = get_content(k, "")

    # Load dynamic options from database to let admin select featured products, courses, internships, and events
    courses = Course.query.order_by(Course.title.asc()).all()
    events = Event.query.order_by(Event.name.asc()).all()
    products = Product.query.filter(Product.is_deleted.isnot(True)).order_by(Product.name.asc()).all()
    internships = Internship.query.order_by(Internship.title.asc()).all()
    testimonials = HomeTestimonial.query.order_by(HomeTestimonial.name.asc()).all()

    # Determine last updated
    last_updated_row = HomeContent.query.order_by(HomeContent.updated_at.desc()).first()
    last_updated = last_updated_row.updated_at if last_updated_row else None

    return render_template(
        "admin/homepage_manager.html",
        content=content,
        courses=courses,
        events=events,
        products=products,
        internships=internships,
        testimonials=testimonials,
        versions=versions,
        logs=logs,
        last_updated=last_updated
    )


@admin_bp.post("/homepage/restore/<int:version_id>")
@admin_required
def homepage_restore_version(version_id: int):
    """Restore Homepage configurations from a historical snapshot."""
    version = HomeVersion.query.get_or_404(version_id)
    try:
        import json
        snapshot = json.loads(version.version_data)
        
        def set_content(key: str, value: str):
            row = HomeContent.query.filter_by(key=key).first()
            if not row:
                row = HomeContent(key=key, value=value or "")
                db.session.add(row)
            else:
                row.value = value or ""
                row.updated_at = datetime.utcnow()
                
        for k, v in snapshot.items():
            set_content(k, v)
            
        # Log version restore
        from flask_login import current_user
        admin_email = current_user.email if current_user and getattr(current_user, "is_authenticated", False) else "system"
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
        
        log_entry = HomeActivityLog(
            action=f"Restored Homepage to version from {version.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            admin_email=admin_email,
            ip_address=ip
        )
        db.session.add(log_entry)
        
        # Sync with legacy HomePageHero table
        hero = HomePageHero.query.first()
        if hero:
            hero.badge_text = snapshot.get("hero_badge_text", "")
            hero.badge_subtext = snapshot.get("hero_badge_subtext", "")
            hero.heading = snapshot.get("hero_heading", "")
            hero.description = snapshot.get("hero_description", "")
            hero.primary_button_text = snapshot.get("hero_primary_btn_text", "")
            hero.primary_button_link = snapshot.get("hero_primary_btn_link", "")
            hero.secondary_button_text = snapshot.get("hero_secondary_btn_text", "")
            hero.secondary_button_link = snapshot.get("hero_secondary_btn_link", "")
            hero.tertiary_button_text = snapshot.get("hero_tertiary_btn_text", "")
            hero.tertiary_button_link = snapshot.get("hero_tertiary_btn_link", "")
            
            hero.hero_image = snapshot.get("hero_image", "")
            hero.ai_lab_image = snapshot.get("hero_ai_lab_image", "")
            hero.robotics_image = snapshot.get("hero_robotics_image", "")
            hero.workshop_image = snapshot.get("hero_workshop_image", "")
            hero.student_activity_image = snapshot.get("hero_student_activity_image", "")
            
            hero.ai_lab_card_title = snapshot.get("hero_ai_lab_title", "")
            hero.ai_lab_card_description = snapshot.get("hero_ai_lab_description", "")
            
            try:
                stats_list = json.loads(snapshot.get("stats_kpis", "[]"))
                if len(stats_list) >= 1:
                    hero.kpi_1_label = stats_list[0].get("number", "5000+")
                    hero.kpi_1_text = stats_list[0].get("label", "Students")
                if len(stats_list) >= 2:
                    hero.kpi_2_label = stats_list[1].get("number", "120+")
                    hero.kpi_2_text = stats_list[1].get("label", "Workshops")
                if len(stats_list) >= 3:
                    hero.kpi_3_label = stats_list[2].get("number", "50+")
                    hero.kpi_3_text = stats_list[2].get("label", "Schools")
                if len(stats_list) >= 4:
                    hero.kpi_4_label = stats_list[3].get("number", "24×7")
                    hero.kpi_4_text = stats_list[3].get("label", "Support")
            except Exception:
                pass
            
            hero.is_published = True
            hero.is_draft = False
            
        db.session.commit()
        flash("Homepage copy successfully restored to historical version!", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"Failed to restore Homepage version: {exc}")
        flash(f"Failed to restore version: {exc}", "danger")
        
    return redirect(url_for("admin.homepage_manager"))


@admin_bp.post("/homepage/delete-image/<image_field>")
@admin_required
def homepage_delete_image(image_field: str):
    """Deletes uploaded homepage images from disk and database."""
    allowed_fields = {
        "hero_image", "hero_ai_lab_image", "hero_robotics_image", "hero_workshop_image",
        "hero_student_activity_image", "ai_lab_image", "footer_promo_image",
        "seo_og_image", "seo_twitter_image"
    }
    if image_field not in allowed_fields:
        flash("Invalid operation.", "danger")
        return redirect(url_for("admin.homepage_manager"))
        
    row = HomeContent.query.filter_by(key=image_field).first()
    if row and row.value:
        filepath = os.path.join(current_app.static_folder, row.value)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                current_app.logger.warning(f"Could not remove file {filepath}: {e}")
        
        row.value = ""
        
        # Legacy synchronization
        hero = HomePageHero.query.first()
        if hero:
            if image_field == "hero_image": hero.hero_image = ""
            elif image_field == "hero_ai_lab_image": hero.ai_lab_image = ""
            elif image_field == "hero_robotics_image": hero.robotics_image = ""
            elif image_field == "hero_workshop_image": hero.workshop_image = ""
            elif image_field == "hero_student_activity_image": hero.student_activity_image = ""

        try:
            db.session.commit()
            flash("Image deleted successfully.", "info")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Database update failed.", "danger")
            
    return redirect(url_for("admin.homepage_manager"))


# =========================
# About Page CMS
# =========================
@admin_bp.route("/about/content", methods=["GET", "POST"])
@admin_required
def about_content():
    """Edit About page key-value copy (hero/story/mission/vision)."""
    keys = [
        ("hero_heading", "Hero heading"),
        ("hero_subtitle", "Hero subtitle"),
        ("who_we_are_title", "Who we are title"),
        ("who_we_are_body", "Who we are body"),
        ("mission_text", "Mission text"),
        ("vision_text", "Vision text"),
    ]
    if request.method == "POST":
        current_app.logger.info(f"Incoming POST form data on /admin/about/content: {request.form}")
        current_app.logger.info(f"Session state: User ID = {session.get('user_id')}, Session Keys = {list(session.keys())}")

        # Robust input validation
        validation_errors = []
        hero_heading = request.form.get("hero_heading", "").strip()
        if not hero_heading:
            validation_errors.append("Hero heading is required.")
        elif len(hero_heading) < 2:
            validation_errors.append("Hero heading must be at least 2 characters.")
        elif len(hero_heading) > 160:
            validation_errors.append(f"Hero heading exceeds database limit of 160 characters (got {len(hero_heading)}).")

        if validation_errors:
            err_msg = f"Validation failed: {', '.join(validation_errors)}"
            current_app.logger.warning(err_msg)
            flash(err_msg, "danger")
            return redirect(url_for("admin.about_content"))

        try:
            for key, _label in keys:
                val = (request.form.get(key, "") or "").strip()
                row = AboutContent.query.filter_by(key=key).first()
                if row is None:
                    row = AboutContent(key=key, value=val)
                else:
                    row.value = val
                db.session.add(row)
            db.session.commit()
            current_app.logger.info("Successfully updated About page key-value CMS content.")
            flash("About content saved successfully.", "success")
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(f"Error saving About page CMS content: {exc}", exc_info=True)
            flash("Could not save About content due to a database session or system error.", "danger")
        return redirect(url_for("admin.about_content"))

    values = {k: "" for k, _ in keys}
    last_updated = None
    try:
        for row in AboutContent.query.all():
            if row.key in values:
                values[row.key] = row.value or ""
        
        latest_row = AboutContent.query.order_by(AboutContent.updated_at.desc()).first()
        if latest_row:
            last_updated = latest_row.updated_at
    except Exception as exc:
        current_app.logger.error(f"Error reading About page content: {exc}")

    return render_template(
        "admin/about_content.html",
        keys=keys,
        values=values,
        last_updated=last_updated,
    )


@admin_bp.route("/about/team", methods=["GET", "POST"])
@admin_required
def about_team():
    per_page = 20
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None
    edit_item = AboutTeamMember.query.get_or_404(edit_id) if edit_id else None

    if request.method == "POST":
        current_app.logger.info(f"Incoming POST form data on /admin/about/team: {request.form}")
        current_app.logger.info(f"Session state: User ID = {session.get('user_id')}, Session Keys = {list(session.keys())}")

        item_id_raw = request.form.get("item_id", "").strip()
        item_id = int(item_id_raw) if item_id_raw.isdigit() else None
        name = request.form.get("name", "").strip()
        role = request.form.get("role", "").strip()
        bio = request.form.get("bio", "").strip()
        linkedin_url = request.form.get("linkedin_url", "").strip()
        github_url = request.form.get("github_url", "").strip()
        instagram_url = request.form.get("instagram_url", "").strip()
        display_order_raw = request.form.get("display_order", "0").strip()
        is_active = request.form.get("is_active") == "1"

        # Robust input validation
        validation_errors = []
        if not name:
            validation_errors.append("Team member name is required.")
        elif len(name) < 2:
            validation_errors.append("Team member name must be at least 2 characters.")
        elif len(name) > 160:
            validation_errors.append(f"Team member name exceeds database limit of 160 characters (got {len(name)}).")

        if not role:
            validation_errors.append("Team member role is required.")
        elif len(role) < 2:
            validation_errors.append("Team member role must be at least 2 characters.")
        elif len(role) > 160:
            validation_errors.append(f"Team member role exceeds database limit of 160 characters (got {len(role)}).")

        if linkedin_url:
            if len(linkedin_url) > 255:
                validation_errors.append(f"LinkedIn URL exceeds database limit of 255 characters (got {len(linkedin_url)}).")
            if not re.match(r'^https?://[^\s/$.?#].[^\s]*$', linkedin_url):
                validation_errors.append("LinkedIn URL must start with a valid HTTP or HTTPS protocol scheme.")

        if github_url:
            if len(github_url) > 255:
                validation_errors.append(f"GitHub URL exceeds database limit of 255 characters (got {len(github_url)}).")
            if not re.match(r'^https?://[^\s/$.?#].[^\s]*$', github_url):
                validation_errors.append("GitHub URL must start with a valid HTTP or HTTPS protocol scheme.")

        if instagram_url:
            if len(instagram_url) > 255:
                validation_errors.append(f"Instagram URL exceeds database limit of 255 characters (got {len(instagram_url)}).")
            if not re.match(r'^https?://[^\s/$.?#].[^\s]*$', instagram_url):
                validation_errors.append("Instagram URL must start with a valid HTTP or HTTPS protocol scheme.")

        try:
            display_order = int(display_order_raw or 0)
            if display_order < 0:
                validation_errors.append("Display order must be a non-negative integer.")
        except (TypeError, ValueError):
            validation_errors.append(f"Display order must be a valid integer (got '{display_order_raw}').")

        img = request.files.get("image")
        if img and img.filename:
            # Validate image extension
            safe_filename_val = secure_filename(img.filename)
            if "." not in safe_filename_val:
                validation_errors.append("Invalid filename structure for profile image.")
            else:
                ext = safe_filename_val.rsplit(".", 1)[1].lower()
                if ext not in ALLOWED_AI_IMAGE_EXTENSIONS:
                    validation_errors.append(f"File extension '{ext}' not allowed. Allowed types: {', '.join(sorted(ALLOWED_AI_IMAGE_EXTENSIONS))}.")
                
                # Verify file size limit is within 5MB (5 * 1024 * 1024)
                try:
                    img.seek(0, os.SEEK_END)
                    size_bytes = img.tell()
                    img.seek(0)  # Reset cursor
                    if size_bytes > 5 * 1024 * 1024:
                        validation_errors.append(f"Profile image exceeds the maximum 5MB size limit (got {size_bytes / (1024 * 1024):.2f}MB).")
                    current_app.logger.info(f"Verified uploaded profile image: filename='{safe_filename_val}', size={size_bytes} bytes")
                except Exception as file_err:
                    current_app.logger.error(f"Failed to check file size of team member upload: {file_err}", exc_info=True)
                    validation_errors.append("Could not safely verify profile image upload file size.")

        if validation_errors:
            err_msg = f"Validation failed: {', '.join(validation_errors)}"
            current_app.logger.warning(err_msg)
            flash(err_msg, "danger")
            return redirect(url_for("admin.about_team", q=q, page=page, edit=item_id or ""))

        try:
            row = AboutTeamMember.query.get_or_404(item_id) if item_id else AboutTeamMember()
            row.name = name
            row.role = role
            row.bio = bio
            row.linkedin_url = linkedin_url
            row.github_url = github_url
            row.instagram_url = instagram_url
            row.display_order = display_order
            row.is_active = is_active

            if img and img.filename:
                row.image_path = _upload_ai_lab_asset(
                    img,
                    subdir=os.path.join("about", "team").replace("\\", "/"),
                    allowed_exts=ALLOWED_AI_IMAGE_EXTENSIONS,
                )
            db.session.add(row)
            db.session.commit()
            current_app.logger.info(f"Successfully saved team member ID {row.id}: Name='{row.name}', Role='{row.role}'")
            flash("Team member saved successfully.", "success")
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(f"Error saving team member: {exc}", exc_info=True)
            flash("Could not save team member due to a system or database error.", "danger")
        return redirect(url_for("admin.about_team"))

    query = AboutTeamMember.query
    if q:
        query = query.filter(or_(AboutTeamMember.name.ilike(f"%{q}%"), AboutTeamMember.role.ilike(f"%{q}%")))
    total = query.count()
    items = (
        query.order_by(AboutTeamMember.display_order.asc(), AboutTeamMember.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/about_team.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )


@admin_bp.post("/about/team/<int:item_id>/delete")
@admin_required
def about_team_delete(item_id: int):
    current_app.logger.info(f"Attempting to delete team member ID: {item_id}")
    row = AboutTeamMember.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        current_app.logger.info(f"Successfully deleted team member ID: {item_id}")
        flash("Team member deleted successfully.", "info")
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error(f"Error deleting team member ID {item_id}: {exc}", exc_info=True)
        flash("Could not delete team member.", "danger")
    return redirect(url_for("admin.about_team"))


@admin_bp.route("/about/timeline", methods=["GET", "POST"])
@admin_required
def about_timeline():
    per_page = 25
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None
    edit_item = AboutTimelineEntry.query.get_or_404(edit_id) if edit_id else None

    if request.method == "POST":
        try:
            # Production-grade logging of incoming POST payload and session state
            current_app.logger.info(f"Incoming POST form data on /admin/about/timeline: {dict(request.form)}")
            current_app.logger.info(f"Session state: User ID = {session.get('_user_id')}, Session Keys = {list(session.keys())}")
            
            item_id_raw = request.form.get("item_id", "").strip()
            item_id = int(item_id_raw) if item_id_raw.isdigit() else None
            year = request.form.get("year", "").strip()
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            display_order_raw = request.form.get("display_order", "0").strip()
            is_active = request.form.get("is_active") == "1"
        except Exception as e:
            current_app.logger.error(f"Failed to parse timeline request data: {e}", exc_info=True)
            flash("Malformed form data or invalid request.", "danger")
            return redirect(url_for("admin.about_timeline"))

        # Robust input validation
        validation_errors = []
        if not year:
            validation_errors.append("Year is required.")
        elif not year.isdigit():
            validation_errors.append(f"Year must contain only digits (got '{year}').")
        elif len(year) < 4 or len(year) > 8:
            validation_errors.append(f"Year must be between 4 and 8 characters (got {len(year)}).")

        if not title:
            validation_errors.append("Timeline title is required.")
        elif len(title) < 2:
            validation_errors.append("Timeline title must be at least 2 characters.")
        elif len(title) > 160:
            validation_errors.append(f"Timeline title exceeds database limit of 160 characters (got {len(title)}).")

        try:
            display_order = int(display_order_raw or 0)
            if display_order < 0:
                validation_errors.append("Display order must be a non-negative integer.")
        except (TypeError, ValueError):
            validation_errors.append(f"Display order must be a valid integer (got '{display_order_raw}').")

        if validation_errors:
            error_msg = " | ".join(validation_errors)
            current_app.logger.warning(f"Validation failed for timeline entry: {error_msg}")
            flash(f"Validation failed: {error_msg}", "danger")
            return redirect(url_for("admin.about_timeline", q=q, page=page, edit=item_id or ""))

        try:
            row = AboutTimelineEntry.query.get_or_404(item_id) if item_id else AboutTimelineEntry()
            row.year = year
            row.title = title
            row.description = description
            row.display_order = display_order
            row.is_active = is_active
            
            db.session.add(row)
            db.session.commit()
            
            current_app.logger.info(f"Successfully saved timeline entry ID {row.id}: Year='{year}', Title='{title}'")
            flash("Timeline entry saved successfully.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            current_app.logger.error(f"Database error saving timeline entry: {exc}", exc_info=True)
            import traceback
            traceback.print_exc()
            flash("Could not save timeline entry to database due to database transaction limits.", "danger")
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(f"Unexpected error saving timeline entry: {exc}", exc_info=True)
            import traceback
            traceback.print_exc()
            flash("An unexpected error occurred while saving the timeline details.", "danger")
        return redirect(url_for("admin.about_timeline"))

    query = AboutTimelineEntry.query
    if q:
        query = query.filter(or_(AboutTimelineEntry.year.ilike(f"%{q}%"), AboutTimelineEntry.title.ilike(f"%{q}%")))
    total = query.count()
    items = (
        query.order_by(AboutTimelineEntry.display_order.asc(), AboutTimelineEntry.id.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/about_timeline.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )


@admin_bp.post("/about/timeline/<int:item_id>/delete")
@admin_required
def about_timeline_delete(item_id: int):
    current_app.logger.info(f"Attempting to delete timeline entry ID: {item_id}")
    row = AboutTimelineEntry.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        current_app.logger.info(f"Successfully deleted timeline entry ID: {item_id}")
        flash("Timeline entry deleted successfully.", "info")
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error(f"Database error deleting timeline entry: {exc}", exc_info=True)
        flash("Could not delete timeline entry.", "danger")
    return redirect(url_for("admin.about_timeline"))


@admin_bp.route("/about/gallery", methods=["GET", "POST"])
@admin_required
def about_gallery():
    per_page = 24
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None
    edit_item = AboutGalleryImage.query.get_or_404(edit_id) if edit_id else None

    if request.method == "POST":
        try:
            # Production-grade logging of incoming POST payload and session state
            current_app.logger.info(f"Incoming POST form data on /admin/about/gallery: {dict(request.form)}")
            current_app.logger.info(f"Session state: User ID = {session.get('_user_id')}, Session Keys = {list(session.keys())}")
            
            item_id_raw = request.form.get("item_id", "").strip()
            item_id = int(item_id_raw) if item_id_raw.isdigit() else None
            title = request.form.get("title", "").strip()
            category = request.form.get("category", "").strip()
            display_order_raw = request.form.get("display_order", "0").strip()
            is_active = request.form.get("is_active") == "1"
        except Exception as e:
            current_app.logger.error(f"Failed to parse gallery request data: {e}", exc_info=True)
            flash("Malformed form data or invalid request.", "danger")
            return redirect(url_for("admin.about_gallery"))

        # Robust input validation
        validation_errors = []
        if not title:
            validation_errors.append("Gallery title is required.")
        elif len(title) < 2:
            validation_errors.append("Gallery title must be at least 2 characters.")
        elif len(title) > 160:
            validation_errors.append(f"Gallery title exceeds database limit of 160 characters (got {len(title)}).")

        if not category:
            validation_errors.append("Category is required.")
        elif len(category) < 2:
            validation_errors.append("Category must be at least 2 characters.")
        elif len(category) > 80:
            validation_errors.append(f"Category name exceeds database limit of 80 characters (got {len(category)}).")

        try:
            display_order = int(display_order_raw or 0)
            if display_order < 0:
                validation_errors.append("Display order must be a non-negative integer.")
        except (TypeError, ValueError):
            validation_errors.append(f"Display order must be a valid integer (got '{display_order_raw}').")

        img = request.files.get("image")
        
        # Verify image requirements (required for creation, optional for edits)
        if not item_id and (not img or not img.filename):
            validation_errors.append("An image file is required for new gallery entries.")

        if img and img.filename:
            # Validate image extension
            safe_filename_val = secure_filename(img.filename)
            if "." not in safe_filename_val:
                validation_errors.append("Invalid filename structure for gallery image.")
            else:
                ext = safe_filename_val.rsplit(".", 1)[1].lower()
                if ext not in ALLOWED_AI_IMAGE_EXTENSIONS:
                    validation_errors.append(f"File extension '{ext}' not allowed. Allowed types: {', '.join(sorted(ALLOWED_AI_IMAGE_EXTENSIONS))}.")
                
                # Verify file size is within 5MB (5 * 1024 * 1024)
                try:
                    img.seek(0, os.SEEK_END)
                    size_bytes = img.tell()
                    img.seek(0)  # Reset cursor
                    if size_bytes > 5 * 1024 * 1024:
                        validation_errors.append(f"Image file exceeds the maximum 5MB size limit (got {size_bytes / (1024 * 1024):.2f}MB).")
                    current_app.logger.info(f"Verified uploaded image: filename='{safe_filename_val}', size={size_bytes} bytes")
                except Exception as file_err:
                    current_app.logger.error(f"Failed to check file size of gallery upload: {file_err}", exc_info=True)
                    validation_errors.append("Could not safely verify image upload file size.")

        if validation_errors:
            error_msg = " | ".join(validation_errors)
            current_app.logger.warning(f"Validation failed for gallery item: {error_msg}")
            flash(f"Validation failed: {error_msg}", "danger")
            return redirect(url_for("admin.about_gallery", q=q, page=page, edit=item_id or ""))

        try:
            row = AboutGalleryImage.query.get_or_404(item_id) if item_id else AboutGalleryImage(title=title, image_path="")
            row.title = title
            row.category = category
            row.display_order = display_order
            row.is_active = is_active
            
            if img and img.filename:
                row.image_path = _upload_ai_lab_asset(
                    img,
                    subdir=os.path.join("about", "gallery").replace("\\", "/"),
                    allowed_exts=ALLOWED_AI_IMAGE_EXTENSIONS,
                )
            
            if not row.image_path:
                raise ValueError("Image path is missing.")
                
            db.session.add(row)
            db.session.commit()
            
            current_app.logger.info(f"Successfully saved gallery image ID {row.id}: Title='{title}', Category='{category}'")
            flash("Gallery image saved successfully.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            current_app.logger.error(f"Database error saving gallery image: {exc}", exc_info=True)
            import traceback
            traceback.print_exc()
            flash("Could not save gallery image to database due to database transaction limits.", "danger")
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(f"Unexpected error saving gallery image: {exc}", exc_info=True)
            import traceback
            traceback.print_exc()
            flash("An unexpected error occurred while saving the gallery details.", "danger")
        return redirect(url_for("admin.about_gallery"))

    query = AboutGalleryImage.query
    if q:
        query = query.filter(AboutGalleryImage.title.ilike(f"%{q}%"))
    total = query.count()
    items = (
        query.order_by(AboutGalleryImage.display_order.asc(), AboutGalleryImage.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/about_gallery.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )


@admin_bp.post("/about/gallery/<int:item_id>/delete")
@admin_required
def about_gallery_delete(item_id: int):
    current_app.logger.info(f"Attempting to delete gallery image ID: {item_id}")
    row = AboutGalleryImage.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        current_app.logger.info(f"Successfully deleted gallery image ID: {item_id}")
        flash("Gallery image deleted successfully.", "info")
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error(f"Database error deleting gallery image: {exc}", exc_info=True)
        flash("Could not delete gallery image.", "danger")
    return redirect(url_for("admin.about_gallery"))


@admin_bp.route("/about/partners", methods=["GET", "POST"])
@admin_required
def about_partners():
    per_page = 24
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None
    edit_item = AboutPartnerLogo.query.get_or_404(edit_id) if edit_id else None

    if request.method == "POST":
        try:
            # Production-grade logging of incoming POST payload and session state
            current_app.logger.info(f"Incoming POST form data on /admin/about/partners: {dict(request.form)}")
            current_app.logger.info(f"Session state: User ID = {session.get('_user_id')}, Session Keys = {list(session.keys())}")
            
            item_id_raw = request.form.get("item_id", "").strip()
            item_id = int(item_id_raw) if item_id_raw.isdigit() else None
            name = request.form.get("name", "").strip()
            url = request.form.get("url", "").strip()
            display_order_raw = request.form.get("display_order", "0").strip()
            is_active = request.form.get("is_active") == "1"
        except Exception as e:
            current_app.logger.error(f"Failed to parse partner request data: {e}", exc_info=True)
            flash("Malformed form data or invalid request.", "danger")
            return redirect(url_for("admin.about_partners"))

        # Robust input validation
        validation_errors = []
        if not name:
            validation_errors.append("Partner name is required.")
        elif len(name) < 2:
            validation_errors.append("Partner name must be at least 2 characters.")
        elif len(name) > 120:
            validation_errors.append(f"Partner name exceeds database limit of 120 characters (got {len(name)}).")

        if url:
            if len(url) > 255:
                validation_errors.append(f"URL exceeds database limit of 255 characters (got {len(url)}).")
            # Enforce valid URL formats (http:// or https://)
            if not re.match(r'^https?://[^\s/$.?#].[^\s]*$', url):
                validation_errors.append("URL must start with a valid HTTP or HTTPS protocol scheme.")

        try:
            display_order = int(display_order_raw or 0)
            if display_order < 0:
                validation_errors.append("Display order must be a non-negative integer.")
        except (TypeError, ValueError):
            validation_errors.append(f"Display order must be a valid integer (got '{display_order_raw}').")

        img = request.files.get("logo")
        if img and img.filename:
            # Validate logo extension
            safe_filename_val = secure_filename(img.filename)
            if "." not in safe_filename_val:
                validation_errors.append("Invalid filename structure for optional logo asset.")
            else:
                ext = safe_filename_val.rsplit(".", 1)[1].lower()
                if ext not in ALLOWED_AI_IMAGE_EXTENSIONS:
                    validation_errors.append(f"File extension '{ext}' not allowed. Allowed types: {', '.join(sorted(ALLOWED_AI_IMAGE_EXTENSIONS))}.")
                
                # Verify file size is within 5MB (5 * 1024 * 1024)
                try:
                    img.seek(0, os.SEEK_END)
                    size_bytes = img.tell()
                    img.seek(0)  # Reset cursor
                    if size_bytes > 5 * 1024 * 1024:
                        validation_errors.append(f"Logo file exceeds the maximum 5MB size limit (got {size_bytes / (1024 * 1024):.2f}MB).")
                    current_app.logger.info(f"Verified uploaded logo: filename='{safe_filename_val}', size={size_bytes} bytes")
                except Exception as file_err:
                    current_app.logger.error(f"Failed to check file size of logo upload: {file_err}", exc_info=True)
                    validation_errors.append("Could not safely verify logo upload file size.")

        if validation_errors:
            error_msg = " | ".join(validation_errors)
            current_app.logger.warning(f"Validation failed for partner item: {error_msg}")
            flash(f"Validation failed: {error_msg}", "danger")
            return redirect(url_for("admin.about_partners", q=q, page=page, edit=item_id or ""))

        try:
            row = AboutPartnerLogo.query.get_or_404(item_id) if item_id else AboutPartnerLogo()
            row.name = name
            row.url = url
            row.display_order = display_order
            row.is_active = is_active
            
            if img and img.filename:
                row.logo_path = _upload_ai_lab_asset(
                    img,
                    subdir=os.path.join("about", "partners").replace("\\", "/"),
                    allowed_exts=ALLOWED_AI_IMAGE_EXTENSIONS,
                )
            db.session.add(row)
            db.session.commit()
            
            current_app.logger.info(f"Successfully saved partner ID {row.id}: Name='{name}', Order={display_order}")
            flash("Partner saved successfully.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            current_app.logger.error(f"Database error saving partner: {exc}", exc_info=True)
            import traceback
            traceback.print_exc()
            flash("Could not save partner to database due to database transaction limits.", "danger")
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(f"Unexpected error saving partner: {exc}", exc_info=True)
            import traceback
            traceback.print_exc()
            flash("An unexpected error occurred while saving the partner details.", "danger")
        return redirect(url_for("admin.about_partners"))

    query = AboutPartnerLogo.query
    if q:
        query = query.filter(AboutPartnerLogo.name.ilike(f"%{q}%"))
    total = query.count()
    items = (
        query.order_by(AboutPartnerLogo.display_order.asc(), AboutPartnerLogo.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/about_partners.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )


@admin_bp.post("/about/partners/<int:item_id>/delete")
@admin_required
def about_partners_delete(item_id: int):
    current_app.logger.info(f"Attempting to delete partner ID: {item_id}")
    row = AboutPartnerLogo.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        current_app.logger.info(f"Successfully deleted partner ID: {item_id}")
        flash("Partner deleted successfully.", "info")
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error(f"Database error deleting partner ID {item_id}: {exc}", exc_info=True)
        import traceback
        traceback.print_exc()
        flash("Could not delete partner from database.", "danger")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"Unexpected error deleting partner ID {item_id}: {exc}", exc_info=True)
        import traceback
        traceback.print_exc()
        flash("An unexpected error occurred while deleting the partner logo.", "danger")
    return redirect(url_for("admin.about_partners"))


@admin_bp.route("/about/testimonials", methods=["GET", "POST"])
@admin_required
def about_testimonials():
    per_page = 20
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None
    edit_item = AboutTestimonial.query.get_or_404(edit_id) if edit_id else None

    if request.method == "POST":
        try:
            # Production-grade logging of incoming POST payload and session state
            current_app.logger.info(f"Incoming POST form data on /admin/about/testimonials: {dict(request.form)}")
            current_app.logger.info(f"Session state: User ID = {session.get('_user_id')}, Session Keys = {list(session.keys())}")
            
            item_id_raw = request.form.get("item_id", "").strip()
            item_id = int(item_id_raw) if item_id_raw.isdigit() else None
            name = request.form.get("name", "").strip()
            city = request.form.get("city", "").strip()
            course_name = request.form.get("course_name", "").strip()
            feedback = request.form.get("feedback", "").strip()
            rating_raw = request.form.get("rating", "5").strip()
            display_order_raw = request.form.get("display_order", "0").strip()
            is_active = request.form.get("is_active") == "1"
        except Exception as e:
            current_app.logger.error(f"Failed to parse testimonial request data: {e}", exc_info=True)
            flash("Malformed form data or invalid request.", "danger")
            return redirect(url_for("admin.about_testimonials"))

        # Robust input validation
        validation_errors = []
        if not name:
            validation_errors.append("Name is required.")
        elif len(name) < 2:
            validation_errors.append("Name must be at least 2 characters.")
        elif len(name) > 160:
            validation_errors.append(f"Name exceeds database limit of 160 characters (got {len(name)}).")

        if len(city) > 120:
            validation_errors.append(f"City exceeds database limit of 120 characters (got {len(city)}).")

        if len(course_name) > 200:
            validation_errors.append(f"Course name exceeds database limit of 200 characters (got {len(course_name)}).")

        if not feedback:
            validation_errors.append("Feedback content is required.")
        elif len(feedback) < 5:
            validation_errors.append("Feedback must be at least 5 characters.")

        try:
            rating = int(rating_raw or 5)
            if rating < 1 or rating > 5:
                validation_errors.append("Rating must be an integer between 1 and 5.")
        except (TypeError, ValueError):
            validation_errors.append(f"Rating must be a valid integer (got '{rating_raw}').")

        try:
            display_order = int(display_order_raw or 0)
            if display_order < 0:
                validation_errors.append("Display order must be a non-negative integer.")
        except (TypeError, ValueError):
            validation_errors.append(f"Display order must be a valid integer (got '{display_order_raw}').")

        if validation_errors:
            error_msg = " | ".join(validation_errors)
            current_app.logger.warning(f"Validation failed for testimonial: {error_msg}")
            flash(f"Validation failed: {error_msg}", "danger")
            return redirect(url_for("admin.about_testimonials", q=q, page=page, edit=item_id or ""))

        try:
            row = AboutTestimonial.query.get_or_404(item_id) if item_id else AboutTestimonial()
            row.name = name
            row.city = city
            row.course_name = course_name
            row.feedback = feedback
            row.rating = rating
            row.display_order = display_order
            row.is_active = is_active
            
            img = request.files.get("image")
            if img and img.filename:
                row.image_path = _upload_ai_lab_asset(
                    img,
                    subdir=os.path.join("about", "testimonials").replace("\\", "/"),
                    allowed_exts=ALLOWED_AI_IMAGE_EXTENSIONS,
                )
            db.session.add(row)
            db.session.commit()
            
            current_app.logger.info(f"Successfully saved testimonial ID {row.id}: Name='{name}', Rating={rating}")
            flash("Testimonial saved successfully.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            current_app.logger.error(f"Database error saving testimonial: {exc}", exc_info=True)
            import traceback
            traceback.print_exc()
            flash("Could not save testimonial to database due to an integrity issue.", "danger")
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(f"Unexpected error saving testimonial: {exc}", exc_info=True)
            import traceback
            traceback.print_exc()
            flash("An unexpected error occurred while saving the testimonial.", "danger")
        return redirect(url_for("admin.about_testimonials"))

    query = AboutTestimonial.query
    if q:
        query = query.filter(AboutTestimonial.name.ilike(f"%{q}%"))
    total = query.count()
    items = (
        query.order_by(AboutTestimonial.display_order.asc(), AboutTestimonial.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/about_testimonials.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )


@admin_bp.post("/about/testimonials/<int:item_id>/delete")
@admin_required
def about_testimonials_delete(item_id: int):
    current_app.logger.info(f"Attempting to delete testimonial ID: {item_id}")
    row = AboutTestimonial.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        current_app.logger.info(f"Successfully deleted testimonial ID: {item_id}")
        flash("Testimonial deleted successfully.", "info")
    except SQLAlchemyError as exc:
        db.session.rollback()
        current_app.logger.error(f"Database error deleting testimonial ID {item_id}: {exc}", exc_info=True)
        import traceback
        traceback.print_exc()
        flash("Could not delete testimonial from database.", "danger")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"Unexpected error deleting testimonial ID {item_id}: {exc}", exc_info=True)
        import traceback
        traceback.print_exc()
        flash("An unexpected error occurred while deleting the testimonial.", "danger")
    return redirect(url_for("admin.about_testimonials"))


@admin_bp.route("/about/recognition", methods=["GET", "POST"])
@admin_required
def about_recognition():
    per_page = 25
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None
    edit_item = AboutRecognition.query.get_or_404(edit_id) if edit_id else None

    if request.method == "POST":
        try:
            # Production-grade log for incoming payload
            # Clean logging that safely prints emojis (Unicode) using standard dictionary logging.
            current_app.logger.info(f"Incoming POST form data on /admin/about/recognition: {dict(request.form)}")
            
            item_id_raw = request.form.get("item_id", "").strip()
            item_id = int(item_id_raw) if item_id_raw.isdigit() else None
            
            title = request.form.get("title", "").strip()
            subtitle = request.form.get("subtitle", "").strip()
            icon = request.form.get("icon", "✅").strip() or "✅"
            display_order_raw = request.form.get("display_order", "0").strip()
            is_active = request.form.get("is_active") == "1"
        except Exception as e:
            current_app.logger.error(f"Failed to parse request data: {e}", exc_info=True)
            flash("Malformed form data or invalid request.", "danger")
            return redirect(url_for("admin.about_recognition"))

        # Robust input validation
        validation_errors = []
        if not title:
            validation_errors.append("Title cannot be empty.")
        elif len(title) < 2:
            validation_errors.append("Title must be at least 2 characters.")
        elif len(title) > 160:
            validation_errors.append(f"Title exceeds the limit of 160 characters (got {len(title)}).")

        if len(subtitle) > 200:
            validation_errors.append(f"Subtitle exceeds the limit of 200 characters (got {len(subtitle)}).")

        if len(icon) > 16:
            validation_errors.append(f"Icon/Emoji exceeds the limit of 16 characters (got {len(icon)}).")

        try:
            display_order = int(display_order_raw or 0)
            if display_order < 0:
                validation_errors.append("Display order must be a non-negative integer.")
        except (TypeError, ValueError):
            validation_errors.append(f"Display order must be a valid integer (got '{display_order_raw}').")

        if validation_errors:
            error_msg = " | ".join(validation_errors)
            current_app.logger.warning(f"Validation failed for recognition badge: {error_msg}")
            flash(f"Validation failed: {error_msg}", "danger")
            return redirect(url_for("admin.about_recognition", q=q, page=page, edit=item_id or ""))

        try:
            row = AboutRecognition.query.get_or_404(item_id) if item_id else AboutRecognition()
            row.title = title
            row.subtitle = subtitle
            row.icon = icon
            row.display_order = display_order
            row.is_active = is_active
            
            db.session.add(row)
            db.session.commit()
            
            current_app.logger.info(f"Successfully saved recognition badge ID {row.id}: Title='{title}', Icon='{icon}'")
            flash("Recognition item saved successfully.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            current_app.logger.error(f"Database error saving recognition badge: {exc}", exc_info=True)
            import traceback
            traceback.print_exc()
            flash("Could not save recognition item to database.", "danger")
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(f"Unexpected error saving recognition badge: {exc}", exc_info=True)
            import traceback
            traceback.print_exc()
            flash("An unexpected error occurred while saving.", "danger")
        return redirect(url_for("admin.about_recognition"))

    query = AboutRecognition.query
    if q:
        query = query.filter(AboutRecognition.title.ilike(f"%{q}%"))
    total = query.count()
    items = (
        query.order_by(AboutRecognition.display_order.asc(), AboutRecognition.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/about_recognition.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )


@admin_bp.post("/about/recognition/<int:item_id>/delete")
@admin_required
def about_recognition_delete(item_id: int):
    row = AboutRecognition.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        flash("Recognition item deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete recognition item.", "danger")
    return redirect(url_for("admin.about_recognition"))


@admin_bp.route("/about/counters", methods=["GET", "POST"])
@admin_required
def about_counters():
    per_page = 25
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None
    edit_item = AboutCounter.query.get_or_404(edit_id) if edit_id else None

    if request.method == "POST":
        try:
            current_app.logger.info(f"Incoming POST form data on /admin/about/counters: {dict(request.form)}")
            
            item_id_raw = request.form.get("item_id", "").strip()
            item_id = int(item_id_raw) if item_id_raw.isdigit() else None
            
            label = request.form.get("label", "").strip()
            value_raw = request.form.get("value", "0").strip()
            suffix = request.form.get("suffix", "+").strip()
            icon = request.form.get("icon", "✨").strip() or "✨"
            display_order_raw = request.form.get("display_order", "0").strip()
            is_active = request.form.get("is_active") == "1"
        except Exception as e:
            current_app.logger.error(f"Failed to parse counter request data: {e}", exc_info=True)
            flash("Malformed form data or invalid request.", "danger")
            return redirect(url_for("admin.about_counters"))

        # Robust input validation
        validation_errors = []
        if not label:
            validation_errors.append("Label cannot be empty.")
        elif len(label) < 2:
            validation_errors.append("Label must be at least 2 characters.")
        elif len(label) > 120:
            validation_errors.append(f"Label exceeds the limit of 120 characters (got {len(label)}).")

        try:
            value = int(value_raw or 0)
            if value < 0:
                validation_errors.append("Value must be a non-negative integer.")
        except (TypeError, ValueError):
            validation_errors.append(f"Value must be a valid integer (got '{value_raw}').")

        if len(suffix) > 16:
            validation_errors.append(f"Suffix exceeds the limit of 16 characters (got {len(suffix)}).")

        if len(icon) > 16:
            validation_errors.append(f"Icon exceeds the limit of 16 characters (got {len(icon)}).")

        try:
            display_order = int(display_order_raw or 0)
            if display_order < 0:
                validation_errors.append("Display order must be a non-negative integer.")
        except (TypeError, ValueError):
            validation_errors.append(f"Display order must be a valid integer (got '{display_order_raw}').")

        if validation_errors:
            error_msg = " | ".join(validation_errors)
            current_app.logger.warning(f"Validation failed for achievement counter: {error_msg}")
            flash(f"Validation failed: {error_msg}", "danger")
            return redirect(url_for("admin.about_counters", q=q, page=page, edit=item_id or ""))

        try:
            row = AboutCounter.query.get_or_404(item_id) if item_id else AboutCounter()
            row.label = label
            row.value = value
            row.suffix = suffix
            row.icon = icon
            row.display_order = display_order
            row.is_active = is_active
            
            db.session.add(row)
            db.session.commit()
            
            current_app.logger.info(f"Successfully saved achievement counter ID {row.id}: Label='{label}', Icon='{icon}'")
            flash("Counter saved successfully.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            current_app.logger.error(f"Database error saving achievement counter: {exc}", exc_info=True)
            import traceback
            traceback.print_exc()
            flash("Could not save counter to database.", "danger")
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(f"Unexpected error saving achievement counter: {exc}", exc_info=True)
            import traceback
            traceback.print_exc()
            flash("An unexpected error occurred while saving.", "danger")
        return redirect(url_for("admin.about_counters"))

    query = AboutCounter.query
    if q:
        query = query.filter(AboutCounter.label.ilike(f"%{q}%"))
    total = query.count()
    items = (
        query.order_by(AboutCounter.display_order.asc(), AboutCounter.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/about_counters.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )


@admin_bp.post("/about/counters/<int:item_id>/delete")
@admin_required
def about_counters_delete(item_id: int):
    row = AboutCounter.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        flash("Counter deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete counter.", "danger")
    return redirect(url_for("admin.about_counters"))


@admin_bp.route("/ai-lab/hardware", methods=["GET", "POST"])
@admin_required
def ai_lab_hardware():
    per_page = 20
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()

    edit_id = None
    if edit_id_raw:
        try:
            edit_id = int(edit_id_raw)
        except (TypeError, ValueError):
            edit_id = None

    item_to_edit = None
    if edit_id:
        item_to_edit = AILabHardwareItem.query.get_or_404(edit_id)

    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        item_id = None
        if item_id_raw:
            try:
                item_id = int(item_id_raw)
            except (TypeError, ValueError):
                item_id = None

        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        display_order_raw = request.form.get("display_order", "0")
        is_active = request.form.get("is_active") == "1"

        try:
            display_order = max(0, int(display_order_raw or 0))
        except (TypeError, ValueError):
            display_order = 0

        if len(name) < 2:
            flash("Hardware name must be at least 2 characters.", "danger")
            return redirect(url_for("admin.ai_lab_hardware", q=q, page=page, edit=item_id or ""))

        try:
            if item_id:
                row = AILabHardwareItem.query.get_or_404(item_id)
            else:
                row = AILabHardwareItem()

            row.name = name
            row.category = category
            row.description = description
            row.display_order = display_order
            row.is_active = is_active

            icon_file = request.files.get("icon")
            if icon_file and icon_file.filename:
                row.icon_path = _upload_ai_lab_asset(
                    icon_file,
                    subdir=os.path.join("hardware", "icons").replace("\\", "/"),
                    allowed_exts=ALLOWED_AI_IMAGE_EXTENSIONS,
                )

            db.session.add(row)
            db.session.commit()
            flash("Hardware item saved.", "success")
        except (ValueError, SQLAlchemyError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else "Could not save hardware item.", "danger")

        return redirect(url_for("admin.ai_lab_hardware", q=q, page=1))

    query = AILabHardwareItem.query
    if q:
        query = query.filter(or_(AILabHardwareItem.name.ilike(f"%{q}%"), AILabHardwareItem.category.ilike(f"%{q}%")))

    total = query.count()
    items = (
        query.order_by(AILabHardwareItem.display_order.asc(), AILabHardwareItem.id.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/ai_lab_hardware.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=item_to_edit,
    )


@admin_bp.post("/ai-lab/hardware/<int:item_id>/delete")
@admin_required
def ai_lab_hardware_delete(item_id: int):
    row = AILabHardwareItem.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        flash("Hardware item deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete hardware item.", "danger")
    return redirect(url_for("admin.ai_lab_hardware"))


@admin_bp.route("/ai-lab/curriculum", methods=["GET", "POST"])
@admin_required
def ai_lab_curriculum():
    per_page = 20
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None

    edit_item = AILabCurriculumBlock.query.get_or_404(edit_id) if edit_id else None

    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        item_id = int(item_id_raw) if item_id_raw.isdigit() else None

        level = request.form.get("level", "").strip()
        title = request.form.get("title", "").strip()
        focus_areas = request.form.get("focus_areas", "").strip()
        duration = request.form.get("duration", "").strip()
        display_order_raw = request.form.get("display_order", "0")
        is_active = request.form.get("is_active") == "1"

        try:
            display_order = max(0, int(display_order_raw or 0))
        except (TypeError, ValueError):
            display_order = 0

        if len(level) < 3 or len(title) < 2:
            flash("Level and title are required.", "danger")
            return redirect(url_for("admin.ai_lab_curriculum", q=q, page=page, edit=item_id or ""))

        try:
            if item_id:
                row = AILabCurriculumBlock.query.get_or_404(item_id)
            else:
                row = AILabCurriculumBlock()

            row.level = level
            row.title = title
            row.focus_areas = focus_areas
            row.duration = duration
            row.display_order = display_order
            row.is_active = is_active
            db.session.add(row)
            db.session.commit()
            flash("Curriculum block saved.", "success")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Could not save curriculum block.", "danger")

        return redirect(url_for("admin.ai_lab_curriculum", q=q, page=1))

    query = AILabCurriculumBlock.query
    if q:
        query = query.filter(or_(AILabCurriculumBlock.level.ilike(f"%{q}%"), AILabCurriculumBlock.title.ilike(f"%{q}%")))

    total = query.count()
    items = (
        query.order_by(AILabCurriculumBlock.display_order.asc(), AILabCurriculumBlock.id.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/ai_lab_curriculum.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )


@admin_bp.post("/ai-lab/curriculum/<int:item_id>/delete")
@admin_required
def ai_lab_curriculum_delete(item_id: int):
    row = AILabCurriculumBlock.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        flash("Curriculum block deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete curriculum block.", "danger")
    return redirect(url_for("admin.ai_lab_curriculum"))


@admin_bp.route("/ai-lab/projects", methods=["GET", "POST"])
@admin_required
def ai_lab_projects():
    per_page = 20
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None

    edit_item = AILabProject.query.get_or_404(edit_id) if edit_id else None

    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        item_id = int(item_id_raw) if item_id_raw.isdigit() else None

        title = request.form.get("title", "").strip()
        difficulty = request.form.get("difficulty", "").strip()
        technologies = request.form.get("technologies", "").strip()
        description = request.form.get("description", "").strip()
        display_order_raw = request.form.get("display_order", "0")
        is_active = request.form.get("is_active") == "1"

        try:
            display_order = max(0, int(display_order_raw or 0))
        except (TypeError, ValueError):
            display_order = 0

        if len(title) < 2:
            flash("Project title must be at least 2 characters.", "danger")
            return redirect(url_for("admin.ai_lab_projects", q=q, page=page, edit=item_id or ""))

        try:
            if item_id:
                row = AILabProject.query.get_or_404(item_id)
            else:
                row = AILabProject()

            row.title = title
            row.difficulty = difficulty or "Beginner"
            row.technologies = technologies
            row.description = description
            row.display_order = display_order
            row.is_active = is_active

            media_file = request.files.get("media")
            if media_file and media_file.filename:
                row.media_path = _upload_ai_lab_asset(
                    media_file,
                    subdir=os.path.join("projects", "media").replace("\\", "/"),
                    allowed_exts=ALLOWED_AI_MEDIA_EXTENSIONS,
                )

            db.session.add(row)
            db.session.commit()
            flash("Project saved.", "success")
        except (ValueError, SQLAlchemyError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else "Could not save project.", "danger")

        return redirect(url_for("admin.ai_lab_projects", q=q, page=1))

    query = AILabProject.query
    if q:
        query = query.filter(AILabProject.title.ilike(f"%{q}%"))

    total = query.count()
    items = (
        query.order_by(AILabProject.display_order.asc(), AILabProject.id.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/ai_lab_projects.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )


@admin_bp.post("/ai-lab/projects/<int:item_id>/delete")
@admin_required
def ai_lab_projects_delete(item_id: int):
    row = AILabProject.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        flash("Project deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete project.", "danger")
    return redirect(url_for("admin.ai_lab_projects"))


@admin_bp.route("/ai-lab/testimonials", methods=["GET", "POST"])
@admin_required
def ai_lab_testimonials():
    per_page = 20
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None

    edit_item = AILabTestimonial.query.get_or_404(edit_id) if edit_id else None

    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        item_id = int(item_id_raw) if item_id_raw.isdigit() else None

        name = request.form.get("name", "").strip()
        role = request.form.get("role", "").strip()
        organization = request.form.get("organization", "").strip()
        quote = request.form.get("quote", "").strip()
        rating_raw = request.form.get("rating", "5")
        display_order_raw = request.form.get("display_order", "0")
        is_active = request.form.get("is_active") == "1"

        try:
            rating = min(5, max(1, int(rating_raw or 5)))
        except (TypeError, ValueError):
            rating = 5

        try:
            display_order = max(0, int(display_order_raw or 0))
        except (TypeError, ValueError):
            display_order = 0

        if len(name) < 2 or len(quote) < 5:
            flash("Name and quote are required.", "danger")
            return redirect(url_for("admin.ai_lab_testimonials", q=q, page=page, edit=item_id or ""))

        try:
            if item_id:
                row = AILabTestimonial.query.get_or_404(item_id)
            else:
                row = AILabTestimonial()

            row.name = name
            row.role = role
            row.organization = organization
            row.quote = quote
            row.rating = rating
            row.display_order = display_order
            row.is_active = is_active

            logo_file = request.files.get("logo")
            if logo_file and logo_file.filename:
                row.logo_path = _upload_ai_lab_asset(
                    logo_file,
                    subdir=os.path.join("testimonials", "logos").replace("\\", "/"),
                    allowed_exts=ALLOWED_AI_IMAGE_EXTENSIONS,
                )

            db.session.add(row)
            db.session.commit()
            flash("Testimonial saved.", "success")
        except (ValueError, SQLAlchemyError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else "Could not save testimonial.", "danger")

        return redirect(url_for("admin.ai_lab_testimonials", q=q, page=1))

    query = AILabTestimonial.query
    if q:
        query = query.filter(AILabTestimonial.name.ilike(f"%{q}%"))

    total = query.count()
    items = (
        query.order_by(AILabTestimonial.display_order.asc(), AILabTestimonial.id.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/ai_lab_testimonials.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )


@admin_bp.post("/ai-lab/testimonials/<int:item_id>/delete")
@admin_required
def ai_lab_testimonials_delete(item_id: int):
    row = AILabTestimonial.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        flash("Testimonial deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete testimonial.", "danger")
    return redirect(url_for("admin.ai_lab_testimonials"))


@admin_bp.route("/ai-lab/faqs", methods=["GET", "POST"])
@admin_required
def ai_lab_faqs():
    per_page = 20
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None

    edit_item = AILabFAQ.query.get_or_404(edit_id) if edit_id else None

    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        item_id = int(item_id_raw) if item_id_raw.isdigit() else None

        question = request.form.get("question", "").strip()
        answer = request.form.get("answer", "").strip()
        category = request.form.get("category", "").strip()
        display_order_raw = request.form.get("display_order", "0")
        is_active = request.form.get("is_active") == "1"

        try:
            display_order = max(0, int(display_order_raw or 0))
        except (TypeError, ValueError):
            display_order = 0

        if len(question) < 5 or len(answer) < 5:
            flash("Question and answer are required.", "danger")
            return redirect(url_for("admin.ai_lab_faqs", q=q, page=page, edit=item_id or ""))

        try:
            if item_id:
                row = AILabFAQ.query.get_or_404(item_id)
            else:
                row = AILabFAQ()

            row.question = question
            row.answer = answer
            row.category = category
            row.display_order = display_order
            row.is_active = is_active
            db.session.add(row)
            db.session.commit()
            flash("FAQ saved.", "success")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Could not save FAQ.", "danger")

        return redirect(url_for("admin.ai_lab_faqs", q=q, page=1))

    query = AILabFAQ.query
    if q:
        query = query.filter(AILabFAQ.question.ilike(f"%{q}%"))

    total = query.count()
    items = (
        query.order_by(AILabFAQ.display_order.asc(), AILabFAQ.id.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return render_template(
        "admin/ai_lab_faqs.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )


@admin_bp.post("/ai-lab/faqs/<int:item_id>/delete")
@admin_required
def ai_lab_faqs_delete(item_id: int):
    row = AILabFAQ.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        flash("FAQ deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete FAQ.", "danger")
    return redirect(url_for("admin.ai_lab_faqs"))


@admin_bp.route("/ai-lab/brochure", methods=["GET", "POST"])
@admin_required
def ai_lab_brochure():
    brochure = AILabBrochure.query.order_by(AILabBrochure.created_at.desc(), AILabBrochure.id.desc()).first()

    if request.method == "POST":
        title = request.form.get("title", "").strip() or "AI & Robotics Lab Brochure"
        pdf_file = request.files.get("brochure")

        if not pdf_file or not pdf_file.filename:
            flash("Please upload a brochure PDF.", "danger")
            return redirect(url_for("admin.ai_lab_brochure"))

        try:
            row = AILabBrochure()
            row.title = title
            row.file_path = _upload_ai_lab_asset(
                pdf_file,
                subdir=os.path.join("brochures", "pdf").replace("\\", "/"),
                allowed_exts=ALLOWED_AI_PDF_EXTENSIONS,
            )
            row.is_active = True

            # Keep only the latest active brochure.
            AILabBrochure.query.update({AILabBrochure.is_active: False})
            db.session.add(row)
            db.session.commit()
            flash("Brochure uploaded.", "success")
        except (ValueError, SQLAlchemyError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else "Could not upload brochure.", "danger")

        return redirect(url_for("admin.ai_lab_brochure"))

    return render_template("admin/ai_lab_brochure.html", brochure=brochure)


@admin_bp.post("/ai-lab/gallery/<int:item_id>/delete")
@admin_required
def ai_lab_gallery_delete(item_id: int):
    row = AILabGalleryImage.query.get_or_404(item_id)
    try:
        db.session.delete(row)
        db.session.commit()
        flash("Gallery image deleted.", "info")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete gallery image.", "danger")
    return redirect(url_for("admin.ai_lab_gallery"))


@admin_bp.route("/ai-lab/gallery", methods=["GET", "POST"])
@admin_required
def ai_lab_gallery():
    per_page = 20
    q = request.args.get("q", "").strip()
    page_raw = request.args.get("page", "1")
    try:
        page = max(1, int(page_raw))
    except (TypeError, ValueError):
        page = 1
    edit_id_raw = request.args.get("edit", "").strip()
    edit_id = int(edit_id_raw) if edit_id_raw.isdigit() else None

    edit_item = AILabGalleryImage.query.get_or_404(edit_id) if edit_id else None

    if request.method == "POST":
        item_id_raw = request.form.get("item_id", "").strip()
        item_id = int(item_id_raw) if item_id_raw.isdigit() else None

        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        caption = request.form.get("caption", "").strip()
        display_order_raw = request.form.get("display_order", "0")
        is_active = request.form.get("is_active") == "1"

        try:
            display_order = max(0, int(display_order_raw or 0))
        except (TypeError, ValueError):
            display_order = 0

        if len(title) < 2:
            flash("Gallery title must be at least 2 characters.", "danger")
            return redirect(url_for("admin.ai_lab_gallery", q=q, page=page, edit=item_id or ""))

        try:
            if item_id:
                row = AILabGalleryImage.query.get_or_404(item_id)
            else:
                row = AILabGalleryImage()

            row.title = title
            row.category = category
            row.caption = caption
            row.display_order = display_order
            row.is_active = is_active

            image_file = request.files.get("image")
            if image_file and image_file.filename:
                row.image_path = _upload_ai_lab_asset(
                    image_file,
                    subdir=os.path.join("gallery").replace("\\", "/"),
                    allowed_exts=ALLOWED_AI_IMAGE_EXTENSIONS,
                )

            db.session.add(row)
            db.session.commit()
            flash("Gallery item saved.", "success")
        except (ValueError, SQLAlchemyError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else "Could not save gallery item.", "danger")

        return redirect(url_for("admin.ai_lab_gallery", q=q, page=1))

    query = AILabGalleryImage.query
    if q:
        query = query.filter(or_(AILabGalleryImage.title.ilike(f"%{q}%"), AILabGalleryImage.category.ilike(f"%{q}%")))

    total = query.count()
    items = (
        query.order_by(AILabGalleryImage.display_order.asc(), AILabGalleryImage.id.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return render_template(
        "admin/ai_lab_gallery.html",
        items=items,
        total=total,
        per_page=per_page,
        page=page,
        q=q,
        edit_item=edit_item,
    )

@admin_bp.route("/homepage-hero", methods=["GET", "POST"])
@admin_required
def homepage_hero():
    """Manage homepage hero section content and visuals."""
    hero = HomePageHero.query.first()
    if not hero:
        hero = HomePageHero()
        db.session.add(hero)
        db.session.commit()

    if request.method == "POST":
        try:
            # Update text content
            hero.badge_text = request.form.get("badge_text", hero.badge_text).strip()
            hero.badge_subtext = request.form.get("badge_subtext", hero.badge_subtext).strip()
            hero.heading = request.form.get("heading", hero.heading).strip()
            hero.description = request.form.get("description", hero.description).strip()
            
            # Update button text and links
            hero.primary_button_text = request.form.get("primary_button_text", hero.primary_button_text).strip()
            hero.primary_button_link = request.form.get("primary_button_link", hero.primary_button_link).strip()
            hero.secondary_button_text = request.form.get("secondary_button_text", hero.secondary_button_text).strip()
            hero.secondary_button_link = request.form.get("secondary_button_link", hero.secondary_button_link).strip()
            hero.tertiary_button_text = request.form.get("tertiary_button_text", hero.tertiary_button_text).strip()
            hero.tertiary_button_link = request.form.get("tertiary_button_link", hero.tertiary_button_link).strip()
            
            # Update right card content
            hero.ai_lab_card_title = request.form.get("ai_lab_card_title", hero.ai_lab_card_title).strip()
            hero.ai_lab_card_description = request.form.get("ai_lab_card_description", hero.ai_lab_card_description).strip()
            
            # Update card features
            hero.card_feature_1_title = request.form.get("card_feature_1_title", hero.card_feature_1_title).strip()
            hero.card_feature_1_desc = request.form.get("card_feature_1_desc", hero.card_feature_1_desc).strip()
            hero.card_feature_2_title = request.form.get("card_feature_2_title", hero.card_feature_2_title).strip()
            hero.card_feature_2_desc = request.form.get("card_feature_2_desc", hero.card_feature_2_desc).strip()
            
            # Update KPIs
            hero.kpi_1_label = request.form.get("kpi_1_label", hero.kpi_1_label).strip()
            hero.kpi_1_text = request.form.get("kpi_1_text", hero.kpi_1_text).strip()
            hero.kpi_2_label = request.form.get("kpi_2_label", hero.kpi_2_label).strip()
            hero.kpi_2_text = request.form.get("kpi_2_text", hero.kpi_2_text).strip()
            hero.kpi_3_label = request.form.get("kpi_3_label", hero.kpi_3_label).strip()
            hero.kpi_3_text = request.form.get("kpi_3_text", hero.kpi_3_text).strip()
            hero.kpi_4_label = request.form.get("kpi_4_label", hero.kpi_4_label).strip()
            hero.kpi_4_text = request.form.get("kpi_4_text", hero.kpi_4_text).strip()
            
            # Handle image uploads
            hero_img = request.files.get("hero_image")
            if hero_img and hero_img.filename:
                try:
                    hero.hero_image = _upload_hero_image(hero_img)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    return redirect(url_for("admin.homepage_hero"))
            
            ai_lab_img = request.files.get("ai_lab_image")
            if ai_lab_img and ai_lab_img.filename:
                try:
                    hero.ai_lab_image = _upload_hero_image(ai_lab_img)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    return redirect(url_for("admin.homepage_hero"))
            
            robotics_img = request.files.get("robotics_image")
            if robotics_img and robotics_img.filename:
                try:
                    hero.robotics_image = _upload_hero_image(robotics_img)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    return redirect(url_for("admin.homepage_hero"))
            
            workshop_img = request.files.get("workshop_image")
            if workshop_img and workshop_img.filename:
                try:
                    hero.workshop_image = _upload_hero_image(workshop_img)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    return redirect(url_for("admin.homepage_hero"))
            
            student_img = request.files.get("student_activity_image")
            if student_img and student_img.filename:
                try:
                    hero.student_activity_image = _upload_hero_image(student_img)
                except ValueError as exc:
                    flash(str(exc), "danger")
                    return redirect(url_for("admin.homepage_hero"))
            
            # Handle publish/save draft
            is_publish = request.form.get("action") == "publish"
            hero.is_published = is_publish
            hero.is_draft = not is_publish
            if is_publish:
                from datetime import datetime
                hero.published_at = datetime.utcnow()
            
            db.session.commit()
            flash("Homepage hero content saved and published!" if is_publish else "Homepage hero content saved as draft.", "success")
        except SQLAlchemyError as exc:
            db.session.rollback()
            flash("Could not save homepage hero content. Please try again.", "danger")
        
        return redirect(url_for("admin.homepage_hero"))
    
    return render_template("admin/homepage_hero.html", hero=hero)


@admin_bp.post("/homepage-hero/delete-image/<image_field>")
@admin_required
def homepage_hero_delete_image(image_field):
    """Delete a hero image."""
    valid_fields = [
        "hero_image", "ai_lab_image", "robotics_image", 
        "workshop_image", "student_activity_image"
    ]
    
    if image_field not in valid_fields:
        flash("Invalid image field.", "danger")
        return redirect(url_for("admin.homepage_hero"))
    
    hero = HomePageHero.query.first()
    if not hero:
        flash("Homepage hero not found.", "danger")
        return redirect(url_for("admin.homepage_hero"))
    
    try:
        setattr(hero, image_field, None)
        db.session.commit()
        flash("Image deleted.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not delete image.", "danger")
    
    return redirect(url_for("admin.homepage_hero"))


# ==========================================
# CENTRALIZED STORE CMS / STORE MANAGER
# ==========================================

@admin_bp.get("/store/manager")
@admin_required
def store_manager():
    from models.store import StoreCategory, StoreSubcategory, Coupon, ProductReview, Order, Product, InventoryHistory
    import json
    
    # Fetch lists
    products = Product.query.filter(or_(Product.is_deleted.is_(False), Product.is_deleted.is_(None))).order_by(Product.id.desc()).all()
    categories = StoreCategory.query.order_by(StoreCategory.display_order.asc()).all()
    subcategories = StoreSubcategory.query.order_by(StoreSubcategory.display_order.asc()).all()
    coupons = Coupon.query.order_by(Coupon.id.desc()).all()
    reviews = ProductReview.query.order_by(ProductReview.created_at.desc()).all()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    
    # Calculate stats
    total_revenue = db.session.query(db.func.sum(Order.total_inr)).filter(Order.payment_status == "paid").scalar() or 0
    total_orders = Order.query.count()
    active_products = Product.query.filter(or_(Product.is_deleted.is_(False), Product.is_deleted.is_(None)), Product.status == "published").count()
    
    # Low stock calculation
    low_stock_items = []
    for p in products:
        if p.stock <= p.low_stock_threshold:
            low_stock_items.append(p)
            
    pending_reviews_count = ProductReview.query.filter_by(status="pending").count()
    
    # Render specifications & features parsed as JSON lists for the forms
    product_specs_dict = {}
    product_features_dict = {}
    for p in products:
        try:
            product_specs_dict[p.id] = json.loads(p.specifications or "[]")
        except Exception:
            product_specs_dict[p.id] = []
            
        try:
            product_features_dict[p.id] = json.loads(p.features or "[]")
        except Exception:
            product_features_dict[p.id] = []
    
    # Prepare JSON-serializable product representations for client-side modals
    product_jsons = {}
    for p in products:
        try:
            gallery = []
            for gi in getattr(p, 'gallery_images', []) or []:
                gallery.append({
                    'id': gi.id,
                    'image_url': gi.image_url,
                })
        except Exception:
            gallery = []

        product_jsons[p.id] = {
            'id': p.id,
            'name': p.name,
            'slug': p.slug,
            'sku': p.sku,
            'category': p.category,
            'subcategory': p.subcategory,
            'brand': p.brand,
            'tags': p.tags,
            'price_inr': p.price_inr,
            'discount_price_inr': p.discount_price_inr,
            'gst_percent': p.gst_percent,
            'stock': p.stock,
            'low_stock_threshold': p.low_stock_threshold,
            'status': p.status,
            'is_featured': bool(p.is_featured),
            'is_trending': bool(p.is_trending),
            'is_new_arrival': bool(p.is_new_arrival),
            'short_description': p.short_description,
            'description': p.description,
            'warranty': p.warranty,
            'video_url': p.video_url,
            'seo_title': p.seo_title,
            'seo_description': p.seo_description,
            'seo_keywords': p.seo_keywords,
            'gallery_images': gallery,
            'image_url': p.image_url,
        }

    categories_json = {c.id: c.to_dict() for c in categories}
    subcategories_json = {s.id: s.to_dict() for s in subcategories}
    coupons_json = {c.id: c.to_dict() for c in coupons}
    orders_json = {o.id: o.to_dict() for o in orders}
            
    return render_template(
        "admin/store_manager.html",
        products=products,
        product_jsons=product_jsons,
        categories=categories,
        subcategories=subcategories,
        categories_json=categories_json,
        subcategories_json=subcategories_json,
        coupons=coupons,
        reviews=reviews,
        orders=orders,
        coupons_json=coupons_json,
        orders_json=orders_json,
        total_revenue=total_revenue,
        total_orders=total_orders,
        active_products=active_products,
        low_stock_count=len(low_stock_items),
        low_stock_items=low_stock_items,
        pending_reviews_count=pending_reviews_count,
        product_specs=product_specs_dict,
        product_features=product_features_dict
    )


@admin_bp.post("/store/product/create")
@admin_required
def store_product_create():
    from models.store import Product, ProductGalleryImage, InventoryHistory
    import json
    
    name = request.form.get("name", "").strip()
    if len(name) < 2:
        flash("Product name must be at least 2 characters.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    slug = request.form.get("slug", "").strip()
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        
    # Check for slug uniqueness
    existing = Product.query.filter_by(slug=slug).first()
    if existing:
        slug = f"{slug}-{uuid4().hex[:6]}"
        
    try:
        price_inr = max(1, int(request.form.get("price_inr", 1)))
        discount_price_inr = int(request.form.get("discount_price_inr", 0) or 0)
        stock = max(0, int(request.form.get("stock", 0)))
        low_stock_threshold = max(0, int(request.form.get("low_stock_threshold", 5)))
        gst_percent = float(request.form.get("gst_percent", 18.0) or 18.0)
    except (TypeError, ValueError):
        flash("Numerical values supplied are invalid.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    category = request.form.get("category", "").strip()
    if not category:
        flash("Category is required.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    # Process Specifications
    spec_keys = request.form.getlist("spec_key[]")
    spec_vals = request.form.getlist("spec_value[]")
    specs = []
    for k, v in zip(spec_keys, spec_vals):
        if k.strip() or v.strip():
            specs.append({"key": k.strip(), "value": v.strip()})
            
    # Process Features
    feature_items = request.form.getlist("feature[]")
    features = [f.strip() for f in feature_items if f.strip()]
    
    image_file = request.files.get("image")
    try:
        uploaded_path = _upload_product_image(image_file) if image_file else None
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin.store_manager"))
        
    product = Product(
        name=name,
        slug=slug,
        description=request.form.get("description", "").strip(),
        short_description=request.form.get("short_description", "").strip(),
        price_inr=price_inr,
        discount_price_inr=discount_price_inr,
        stock=stock,
        low_stock_threshold=low_stock_threshold,
        category=category,
        subcategory=request.form.get("subcategory", "").strip(),
        brand=request.form.get("brand", "").strip(),
        sku=request.form.get("sku", "").strip() or f"SO-{uuid4().hex[:8].upper()}",
        tags=request.form.get("tags", "").strip(),
        gst_percent=gst_percent,
        status=request.form.get("status", "published").strip(),
        is_featured=request.form.get("is_featured") == "1",
        is_trending=request.form.get("is_trending") == "1",
        is_new_arrival=request.form.get("is_new_arrival") == "1",
        specifications=json.dumps(specs),
        features=json.dumps(features),
        warranty=request.form.get("warranty", "").strip(),
        video_url=request.form.get("video_url", "").strip(),
        seo_title=request.form.get("seo_title", "").strip(),
        seo_description=request.form.get("seo_description", "").strip(),
        seo_keywords=request.form.get("seo_keywords", "").strip(),
        seo_canonical_url=request.form.get("seo_canonical_url", "").strip(),
        seo_og_image=request.form.get("seo_og_image", "").strip(),
        seo_schema=request.form.get("seo_schema", "").strip(),
        image_url=uploaded_path or "/static/images/default_product.svg"
    )
    
    try:
        db.session.add(product)
        db.session.flush()
        
        # Log stock creation history
        db.session.add(InventoryHistory(
            product_id=product.id,
            quantity_changed=stock,
            reason="Product registered in CMS"
        ))
        
        # Handle multiple gallery uploads
        gallery_files = request.files.getlist("gallery_images[]")
        for idx, f in enumerate(gallery_files):
            if f and f.filename:
                g_path = _upload_product_image(f)
                if g_path:
                    db.session.add(ProductGalleryImage(
                        product_id=product.id,
                        image_url=g_path,
                        display_order=idx
                    ))
                    
        db.session.commit()
        flash("Product registered successfully inside Unified Store CMS.", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"Error creating product: {exc}")
        flash(f"Could not register product. Error: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/product/<int:product_id>/edit")
@admin_required
def store_product_edit(product_id):
    from models.store import Product, ProductGalleryImage, InventoryHistory
    import json
    
    product = Product.query.get_or_404(product_id)
    name = request.form.get("name", "").strip()
    if len(name) < 2:
        flash("Product name must be at least 2 characters.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    slug = request.form.get("slug", "").strip()
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        
    # Check for slug uniqueness (excluding self)
    existing = Product.query.filter(Product.slug == slug, Product.id != product.id).first()
    if existing:
        slug = f"{slug}-{uuid4().hex[:6]}"
        
    try:
        price_inr = max(1, int(request.form.get("price_inr", 1)))
        discount_price_inr = int(request.form.get("discount_price_inr", 0) or 0)
        new_stock = max(0, int(request.form.get("stock", 0)))
        low_stock_threshold = max(0, int(request.form.get("low_stock_threshold", 5)))
        gst_percent = float(request.form.get("gst_percent", 18.0) or 18.0)
    except (TypeError, ValueError):
        flash("Numerical values supplied are invalid.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    category = request.form.get("category", "").strip()
    if not category:
        flash("Category is required.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    # Process Specifications
    spec_keys = request.form.getlist("spec_key[]")
    spec_vals = request.form.getlist("spec_value[]")
    specs = []
    for k, v in zip(spec_keys, spec_vals):
        if k.strip() or v.strip():
            specs.append({"key": k.strip(), "value": v.strip()})
            
    # Process Features
    feature_items = request.form.getlist("feature[]")
    features = [f.strip() for f in feature_items if f.strip()]
    
    # Image management
    image_file = request.files.get("image")
    if image_file and image_file.filename:
        try:
            product.image_url = _upload_product_image(image_file)
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.store_manager"))
            
    # Check stock change for logs
    stock_difference = new_stock - product.stock
    if stock_difference != 0:
        db.session.add(InventoryHistory(
            product_id=product.id,
            quantity_changed=stock_difference,
            reason="Admin manual stock correction via CMS Editor"
        ))
        
    # Update properties
    product.name = name
    product.slug = slug
    product.description = request.form.get("description", "").strip()
    product.short_description = request.form.get("short_description", "").strip()
    product.price_inr = price_inr
    product.discount_price_inr = discount_price_inr
    product.stock = new_stock
    product.low_stock_threshold = low_stock_threshold
    product.category = category
    product.subcategory = request.form.get("subcategory", "").strip()
    product.brand = request.form.get("brand", "").strip()
    product.sku = request.form.get("sku", "").strip() or product.sku
    product.tags = request.form.get("tags", "").strip()
    product.gst_percent = gst_percent
    product.status = request.form.get("status", "published").strip()
    product.is_featured = request.form.get("is_featured") == "1"
    product.is_trending = request.form.get("is_trending") == "1"
    product.is_new_arrival = request.form.get("is_new_arrival") == "1"
    product.specifications = json.dumps(specs)
    product.features = json.dumps(features)
    product.warranty = request.form.get("warranty", "").strip()
    product.video_url = request.form.get("video_url", "").strip()
    product.seo_title = request.form.get("seo_title", "").strip()
    product.seo_description = request.form.get("seo_description", "").strip()
    product.seo_keywords = request.form.get("seo_keywords", "").strip()
    product.seo_canonical_url = request.form.get("seo_canonical_url", "").strip()
    product.seo_og_image = request.form.get("seo_og_image", "").strip()
    product.seo_schema = request.form.get("seo_schema", "").strip()
    
    try:
        # Check gallery additions
        gallery_files = request.files.getlist("gallery_images[]")
        for idx, f in enumerate(gallery_files):
            if f and f.filename:
                g_path = _upload_product_image(f)
                if g_path:
                    db.session.add(ProductGalleryImage(
                        product_id=product.id,
                        image_url=g_path,
                        display_order=10 + idx
                    ))
                    
        # Check thumbnail deletion requests
        deleted_thumb_ids = request.form.getlist("delete_gallery_image_ids[]")
        for thumb_id in deleted_thumb_ids:
            try:
                t_row = ProductGalleryImage.query.get(int(thumb_id))
                if t_row and t_row.product_id == product.id:
                    db.session.delete(t_row)
            except Exception:
                pass
                
        db.session.commit()
        flash("Product changes saved successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"Error editing product: {exc}")
        flash(f"Could not update product: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/product/<int:product_id>/duplicate")
@admin_required
def store_product_duplicate(product_id):
    from models.store import Product, ProductGalleryImage, InventoryHistory
    
    original = Product.query.get_or_404(product_id)
    
    # Create duplicate
    duplicate = Product(
        name=f"{original.name} (Copy)",
        slug=f"{original.slug or 'product'}-copy-{uuid4().hex[:6]}",
        description=original.description,
        short_description=original.short_description,
        price_inr=original.price_inr,
        discount_price_inr=original.discount_price_inr,
        stock=0,  # Seed duplicated with 0 stock to prevent errors
        low_stock_threshold=original.low_stock_threshold,
        category=original.category,
        subcategory=original.subcategory,
        brand=original.brand,
        sku=f"COPY-{uuid4().hex[:6].upper()}-{original.sku or ''}"[:100],
        tags=original.tags,
        gst_percent=original.gst_percent,
        status="published",
        is_featured=False,
        is_trending=False,
        is_new_arrival=False,
        specifications=original.specifications,
        features=original.features,
        warranty=original.warranty,
        video_url=original.video_url,
        image_url=original.image_url,
        seo_title=original.seo_title,
        seo_description=original.seo_description,
        seo_keywords=original.seo_keywords
    )
    
    try:
        db.session.add(duplicate)
        db.session.flush()
        
        # Log stock creation
        db.session.add(InventoryHistory(
            product_id=duplicate.id,
            quantity_changed=0,
            reason="Duplicated from product ID #" + str(original.id)
        ))
        
        # Clone gallery images
        for g_img in original.gallery_images:
            db.session.add(ProductGalleryImage(
                product_id=duplicate.id,
                image_url=g_img.image_url,
                display_order=g_img.display_order
            ))
            
        db.session.commit()
        flash(f"Duplicated '{original.name}' successfully. Adjust duplicate stock and status.", "success")
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f"Error duplicating product: {exc}")
        flash(f"Failed to duplicate product: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


# ==========================================
# CATEGORIES CMS
# ==========================================

@admin_bp.post("/store/category/create")
@admin_required
def store_category_create():
    from models.store import StoreCategory
    
    name = request.form.get("name", "").strip()
    if not name:
        flash("Category name is required.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    slug = request.form.get("slug", "").strip()
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        
    # Check uniqueness
    if StoreCategory.query.filter_by(slug=slug).first():
        slug = f"{slug}-{uuid4().hex[:4]}"
        
    try:
        display_order = int(request.form.get("display_order", 0) or 0)
    except (TypeError, ValueError):
        display_order = 0
        
    # Upload banner and icon if present
    banner_file = request.files.get("banner_image")
    icon_file = request.files.get("icon_image")
    banner_url = ""
    icon_url = ""
    
    try:
        if banner_file and banner_file.filename:
            banner_url = _upload_product_image(banner_file)
        if icon_file and icon_file.filename:
            icon_url = _upload_product_image(icon_file)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin.store_manager"))
        
    category = StoreCategory(
        name=name,
        slug=slug,
        banner_url=banner_url or "/static/images/default_category.svg",
        icon_url=icon_url or "/static/images/default_category.svg",
        description=request.form.get("description", "").strip(),
        seo_title=request.form.get("seo_title", "").strip(),
        seo_description=request.form.get("seo_description", "").strip(),
        display_order=display_order
    )
    
    try:
        db.session.add(category)
        db.session.commit()
        flash("Category created successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not create category: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/category/<int:category_id>/edit")
@admin_required
def store_category_edit(category_id):
    from models.store import StoreCategory
    
    category = StoreCategory.query.get_or_404(category_id)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Category name cannot be empty.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    slug = request.form.get("slug", "").strip()
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        
    # Check uniqueness (excluding self)
    existing = StoreCategory.query.filter(StoreCategory.slug == slug, StoreCategory.id != category.id).first()
    if existing:
        slug = f"{slug}-{uuid4().hex[:4]}"
        
    try:
        display_order = int(request.form.get("display_order", 0) or 0)
    except (TypeError, ValueError):
        display_order = category.display_order
        
    banner_file = request.files.get("banner_image")
    icon_file = request.files.get("icon_image")
    
    try:
        if banner_file and banner_file.filename:
            category.banner_url = _upload_product_image(banner_file)
        if icon_file and icon_file.filename:
            category.icon_url = _upload_product_image(icon_file)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin.store_manager"))
        
    category.name = name
    category.slug = slug
    category.description = request.form.get("description", "").strip()
    category.seo_title = request.form.get("seo_title", "").strip()
    category.seo_description = request.form.get("seo_description", "").strip()
    category.display_order = display_order
    
    try:
        db.session.commit()
        flash("Category updated successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not update category: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/category/<int:category_id>/delete")
@admin_required
def store_category_delete(category_id):
    from models.store import StoreCategory
    
    category = StoreCategory.query.get_or_404(category_id)
    try:
        db.session.delete(category)
        db.session.commit()
        flash("Category deleted successfully.", "info")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not delete category (it may be linked to subcategories/products): {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


# ==========================================
# SUBCATEGORIES CMS
# ==========================================

@admin_bp.post("/store/subcategory/create")
@admin_required
def store_subcategory_create():
    from models.store import StoreSubcategory
    
    name = request.form.get("name", "").strip()
    category_id = request.form.get("category_id")
    if not name or not category_id:
        flash("Subcategory name and parent Category are required.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    slug = request.form.get("slug", "").strip()
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        
    try:
        display_order = int(request.form.get("display_order", 0) or 0)
    except (TypeError, ValueError):
        display_order = 0
        
    banner_file = request.files.get("banner_image")
    banner_url = ""
    try:
        if banner_file and banner_file.filename:
            banner_url = _upload_product_image(banner_file)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin.store_manager"))
        
    sub = StoreSubcategory(
        name=name,
        slug=slug,
        category_id=int(category_id),
        banner_url=banner_url,
        description=request.form.get("description", "").strip(),
        display_order=display_order
    )
    
    try:
        db.session.add(sub)
        db.session.commit()
        flash("Subcategory created successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not create subcategory: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/subcategory/<int:subcategory_id>/edit")
@admin_required
def store_subcategory_edit(subcategory_id):
    from models.store import StoreSubcategory
    
    sub = StoreSubcategory.query.get_or_404(subcategory_id)
    name = request.form.get("name", "").strip()
    category_id = request.form.get("category_id")
    if not name or not category_id:
        flash("Subcategory name and parent Category are required.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    slug = request.form.get("slug", "").strip()
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        
    try:
        display_order = int(request.form.get("display_order", 0) or 0)
    except (TypeError, ValueError):
        display_order = sub.display_order
        
    banner_file = request.files.get("banner_image")
    try:
        if banner_file and banner_file.filename:
            sub.banner_url = _upload_product_image(banner_file)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin.store_manager"))
        
    sub.name = name
    sub.slug = slug
    sub.category_id = int(category_id)
    sub.description = request.form.get("description", "").strip()
    sub.display_order = display_order
    
    try:
        db.session.commit()
        flash("Subcategory updated successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not update subcategory: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/subcategory/<int:subcategory_id>/delete")
@admin_required
def store_subcategory_delete(subcategory_id):
    from models.store import StoreSubcategory
    
    sub = StoreSubcategory.query.get_or_404(subcategory_id)
    try:
        db.session.delete(sub)
        db.session.commit()
        flash("Subcategory deleted successfully.", "info")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not delete subcategory: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


# ==========================================
# COUPON CMS
# ==========================================

@admin_bp.post("/store/coupon/create")
@admin_required
def store_coupon_create():
    from models.store import Coupon
    from datetime import datetime
    
    code = request.form.get("code", "").strip().upper()
    discount_type = request.form.get("discount_type", "percentage").strip()
    try:
        discount_value = int(request.form.get("discount_value", 0))
        min_purchase_amount = int(request.form.get("min_purchase_amount", 0) or 0)
        usage_limit = int(request.form.get("usage_limit", 0) or 0)
    except (TypeError, ValueError):
        flash("Numerical coupon values are invalid.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    expiry_str = request.form.get("expiry_date", "")
    if not code or not expiry_str:
        flash("Coupon code and expiry date are required.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    try:
        expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
    except ValueError:
        flash("Expiry date format must be YYYY-MM-DD.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    product_id = request.form.get("product_id")
    p_id = int(product_id) if product_id and product_id.strip() else None
    
    # Check duplicate
    if Coupon.query.filter_by(code=code).first():
        flash("A coupon campaign with this code already exists.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    coupon = Coupon(
        code=code,
        discount_type=discount_type,
        discount_value=discount_value,
        expiry_date=expiry_date,
        usage_limit=usage_limit,
        min_purchase_amount=min_purchase_amount,
        is_active=True,
        product_id=p_id
    )
    
    try:
        db.session.add(coupon)
        db.session.commit()
        flash("Coupon campaign launched successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not launch coupon: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/coupon/<int:coupon_id>/edit")
@admin_required
def store_coupon_edit(coupon_id):
    from models.store import Coupon
    from datetime import datetime
    
    coupon = Coupon.query.get_or_404(coupon_id)
    discount_type = request.form.get("discount_type", "percentage").strip()
    try:
        discount_value = int(request.form.get("discount_value", 0))
        min_purchase_amount = int(request.form.get("min_purchase_amount", 0) or 0)
        usage_limit = int(request.form.get("usage_limit", 0) or 0)
    except (TypeError, ValueError):
        flash("Numerical coupon values are invalid.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    expiry_str = request.form.get("expiry_date", "")
    if not expiry_str:
        flash("Expiry date is required.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    try:
        expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
    except ValueError:
        flash("Expiry date format must be YYYY-MM-DD.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    product_id = request.form.get("product_id")
    p_id = int(product_id) if product_id and product_id.strip() else None
    
    coupon.discount_type = discount_type
    coupon.discount_value = discount_value
    coupon.expiry_date = expiry_date
    coupon.usage_limit = usage_limit
    coupon.min_purchase_amount = min_purchase_amount
    coupon.product_id = p_id
    coupon.is_active = request.form.get("is_active") == "1"
    
    try:
        db.session.commit()
        flash("Coupon campaign parameters updated.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not update coupon parameters: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/coupon/<int:coupon_id>/toggle")
@admin_required
def store_coupon_toggle(coupon_id):
    from models.store import Coupon
    
    coupon = Coupon.query.get_or_404(coupon_id)
    coupon.is_active = not coupon.is_active
    try:
        db.session.commit()
        status = "Active" if coupon.is_active else "Inactive"
        flash(f"Coupon {coupon.code} status toggled to {status}.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not toggle status: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/coupon/<int:coupon_id>/delete")
@admin_required
def store_coupon_delete(coupon_id):
    from models.store import Coupon
    
    coupon = Coupon.query.get_or_404(coupon_id)
    try:
        db.session.delete(coupon)
        db.session.commit()
        flash("Coupon campaign removed.", "info")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not remove campaign: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


# ==========================================
# REVIEW MODERATION
# ==========================================

@admin_bp.post("/store/review/<int:review_id>/status")
@admin_required
def store_review_status(review_id):
    from models.store import ProductReview
    
    review = ProductReview.query.get_or_404(review_id)
    status = request.form.get("status", "pending").strip()
    if status not in {"approved", "rejected", "pending"}:
        flash("Invalid review moderation status.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    review.status = status
    try:
        db.session.commit()
        
        # Proactively re-average product rating if review was approved/rejected
        from models.store import Product
        product = Product.query.get(review.product_id)
        if product:
            approved_ratings = [r.rating for r in product.reviews if r.status == "approved"]
            if approved_ratings:
                product.rating = round(sum(approved_ratings) / len(approved_ratings), 1)
            else:
                product.rating = 4.5 # Fallback average
            db.session.commit()
            
        flash(f"Review moderate status updated to {status.upper()}.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not moderate review: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


# ==========================================
# ORDER TIMELINES & SHIPMENT LOGISTICS
# ==========================================

@admin_bp.post("/store/order/<int:order_id>/timeline")
@admin_required
def store_order_timeline(order_id):
    from models.store import Order, OrderStatusTimeline
    
    order = Order.query.get_or_404(order_id)
    status = request.form.get("status", "").strip()
    notes = request.form.get("notes", "").strip()
    tracking_number = request.form.get("tracking_number", "").strip()
    
    if not status:
        flash("Status code transition is required.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    # Update order state
    order.status = status
    if tracking_number:
        order.tracking_number = tracking_number
        
    timeline_entry = OrderStatusTimeline(
        order_id=order.id,
        status=status,
        notes=notes or f"Shipment status transitioned to {status}."
    )
    
    try:
        db.session.add(timeline_entry)
        db.session.commit()
        
        # Notify customer
        notify_user(order.user_id, f"Your order #{order.id} shipment update: status is now {status}. Notes: {notes}")
        
        flash("Order shipping status timeline updated successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not record shipment status: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.get("/store/order/<int:order_id>/invoice")
@admin_required
def store_order_invoice(order_id):
    from models.store import Order
    order = Order.query.get_or_404(order_id)
    
    # Calculate order breakdown
    total_taxable_value = 0
    total_gst_amount = 0
    
    item_breakdowns = []
    for item in order.items:
        # Calculate reverse GST if gst_percent is set on product
        gst_pct = getattr(item.product, "gst_percent", 18.0) or 18.0
        # GST = Price - (Price / (1 + GST_percent / 100))
        subtotal = item.price_inr * item.quantity
        tax_divisor = 1.0 + (gst_pct / 100.0)
        taxable_value = round(subtotal / tax_divisor, 2)
        gst_amt = round(subtotal - taxable_value, 2)
        
        total_taxable_value += taxable_value
        total_gst_amount += gst_amt
        
        item_breakdowns.append({
            "item": item,
            "taxable_value": taxable_value,
            "gst_pct": gst_pct,
            "gst_amount": gst_amt
        })
        
    return render_template(
        "admin/invoice.html",
        order=order,
        items=item_breakdowns,
        total_taxable=round(total_taxable_value, 2),
        total_gst=round(total_gst_amount, 2)
    )


@admin_bp.get("/store/orders/export")
@admin_required
def store_orders_export():
    from models.store import Order
    import csv
    from io import StringIO
    
    orders = Order.query.order_by(Order.created_at.desc()).all()
    
    dest = StringIO()
    writer = csv.writer(dest)
    
    # Header
    writer.writerow([
        "Order ID", "Customer Username", "Email", "Date Created", 
        "Subtotal Amount", "Discount Coupon", "Discount Amount", 
        "Net Total INR", "Payment Status", "Gateway Order ID", 
        "Gateway Payment ID", "Fulfillment Status", "Tracking Number"
    ])
    
    for o in orders:
        writer.writerow([
            o.id,
            o.user.username,
            o.user.email,
            o.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            o.total_inr + o.discount_amount,
            o.coupon_code or "NONE",
            o.discount_amount,
            o.total_inr,
            o.payment_status,
            o.razorpay_order_id or "N/A",
            o.razorpay_payment_id or "N/A",
            o.status,
            o.tracking_number or "N/A"
        ])
        
    response = Response(dest.getvalue(), mimetype="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=store_order_ledger_export.csv"
    return response


# ==========================================
# STORE HOMEPAGE CMS
# ==========================================

@admin_bp.post("/store/homepage/section/create")
@admin_required
def store_homepage_section_create():
    from models.store import StoreHomepageSection
    
    name = request.form.get("name", "").strip()
    slug = request.form.get("slug", "").strip()
    section_type = request.form.get("section_type", "featured_products").strip()
    
    if not name or not slug:
        flash("Section name and slug are required.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    # Auto-generate slug if not provided
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        
    # Check slug uniqueness
    if StoreHomepageSection.query.filter_by(slug=slug).first():
        slug = f"{slug}-{uuid4().hex[:4]}"
        
    try:
        display_order = int(request.form.get("display_order", 0) or 0)
        max_items = int(request.form.get("max_items", 8) or 8)
    except (TypeError, ValueError):
        display_order = 0
        max_items = 8
        
    banner_file = request.files.get("banner_image")
    banner_url = ""
    if banner_file and banner_file.filename:
        try:
            banner_url = _upload_product_image(banner_file)
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.store_manager"))
            
    section = StoreHomepageSection(
        name=name,
        slug=slug,
        section_type=section_type,
        description=request.form.get("description", "").strip(),
        display_order=display_order,
        is_active=request.form.get("is_active") == "1",
        max_items=max_items,
        banner_image_url=banner_url,
        banner_title=request.form.get("banner_title", "").strip(),
        banner_subtitle=request.form.get("banner_subtitle", "").strip(),
        cta_button_text=request.form.get("cta_button_text", "View All").strip(),
        cta_button_url=request.form.get("cta_button_url", "/store").strip(),
        background_color=request.form.get("background_color", "#ffffff").strip(),
        text_color=request.form.get("text_color", "#000000").strip()
    )
    
    try:
        db.session.add(section)
        db.session.commit()
        flash("Homepage section created successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not create section: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/homepage/section/<int:section_id>/edit")
@admin_required
def store_homepage_section_edit(section_id):
    from models.store import StoreHomepageSection
    
    section = StoreHomepageSection.query.get_or_404(section_id)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Section name cannot be empty.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    try:
        display_order = int(request.form.get("display_order", 0) or 0)
        max_items = int(request.form.get("max_items", 8) or 8)
    except (TypeError, ValueError):
        display_order = section.display_order
        max_items = section.max_items
        
    banner_file = request.files.get("banner_image")
    if banner_file and banner_file.filename:
        try:
            section.banner_image_url = _upload_product_image(banner_file)
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.store_manager"))
            
    section.name = name
    section.description = request.form.get("description", "").strip()
    section.display_order = display_order
    section.is_active = request.form.get("is_active") == "1"
    section.max_items = max_items
    section.banner_title = request.form.get("banner_title", "").strip()
    section.banner_subtitle = request.form.get("banner_subtitle", "").strip()
    section.cta_button_text = request.form.get("cta_button_text", "View All").strip()
    section.cta_button_url = request.form.get("cta_button_url", "/store").strip()
    section.background_color = request.form.get("background_color", "#ffffff").strip()
    section.text_color = request.form.get("text_color", "#000000").strip()
    
    try:
        db.session.commit()
        flash("Homepage section updated successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not update section: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/homepage/section/<int:section_id>/delete")
@admin_required
def store_homepage_section_delete(section_id):
    from models.store import StoreHomepageSection
    
    section = StoreHomepageSection.query.get_or_404(section_id)
    try:
        db.session.delete(section)
        db.session.commit()
        flash("Homepage section deleted successfully.", "info")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not delete section: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/homepage/featured/add")
@admin_required
def store_homepage_featured_add():
    from models.store import StoreFeaturedProduct
    
    section_id = request.form.get("section_id")
    product_id = request.form.get("product_id")
    
    if not section_id or not product_id:
        flash("Section and product are required.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    try:
        section_id = int(section_id)
        product_id = int(product_id)
    except (TypeError, ValueError):
        flash("Invalid section or product ID.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    # Check if already featured in this section
    existing = StoreFeaturedProduct.query.filter_by(section_id=section_id, product_id=product_id).first()
    if existing:
        flash("Product already featured in this section.", "info")
        return redirect(url_for("admin.store_manager"))
        
    try:
        # Calculate next display order
        max_order = db.session.query(db.func.max(StoreFeaturedProduct.display_order)).filter_by(section_id=section_id).scalar() or -1
        
        featured = StoreFeaturedProduct(
            section_id=section_id,
            product_id=product_id,
            display_order=max_order + 1,
            highlight_text=request.form.get("highlight_text", "").strip(),
            highlight_color=request.form.get("highlight_color", "#f43f5e").strip()
        )
        
        db.session.add(featured)
        db.session.commit()
        flash("Product added to featured section.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not add featured product: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/homepage/featured/<int:featured_id>/remove")
@admin_required
def store_homepage_featured_remove(featured_id):
    from models.store import StoreFeaturedProduct
    
    featured = StoreFeaturedProduct.query.get_or_404(featured_id)
    try:
        db.session.delete(featured)
        db.session.commit()
        flash("Product removed from featured section.", "info")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not remove featured product: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/homepage/banner/create")
@admin_required
def store_homepage_banner_create():
    from models.store import StoreBanner
    from datetime import datetime
    
    name = request.form.get("name", "").strip()
    placement = request.form.get("placement", "hero").strip()
    start_str = request.form.get("start_date", "")
    end_str = request.form.get("end_date", "")
    
    if not name or not start_str or not end_str:
        flash("Banner name and date range are required.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    banner_file = request.files.get("banner_image")
    if not banner_file or not banner_file.filename:
        flash("Banner image is required.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    try:
        banner_url = _upload_product_image(banner_file)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin.store_manager"))
        
    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_str, "%Y-%m-%d")
    except ValueError:
        flash("Date format must be YYYY-MM-DD.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    try:
        display_order = int(request.form.get("display_order", 0) or 0)
    except (TypeError, ValueError):
        display_order = 0
        
    banner = StoreBanner(
        name=name,
        image_url=banner_url,
        alt_text=request.form.get("alt_text", "").strip(),
        target_url=request.form.get("target_url", "/store").strip(),
        placement=placement,
        display_order=display_order,
        is_active=request.form.get("is_active") == "1",
        start_date=start_date,
        end_date=end_date
    )
    
    try:
        db.session.add(banner)
        db.session.commit()
        flash("Banner created successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not create banner: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/homepage/banner/<int:banner_id>/delete")
@admin_required
def store_homepage_banner_delete(banner_id):
    from models.store import StoreBanner
    
    banner = StoreBanner.query.get_or_404(banner_id)
    try:
        db.session.delete(banner)
        db.session.commit()
        flash("Banner deleted successfully.", "info")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not delete banner: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/homepage/offer/create")
@admin_required
def store_homepage_offer_create():
    from models.store import StorePromotionalOffer
    from datetime import datetime
    import json
    
    title = request.form.get("title", "").strip()
    offer_type = request.form.get("offer_type", "percentage").strip()
    start_str = request.form.get("start_date", "")
    end_str = request.form.get("end_date", "")
    
    if not title or not start_str or not end_str:
        flash("Offer title and date range are required.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    try:
        discount_value = int(request.form.get("discount_value", 0))
        min_purchase = int(request.form.get("min_purchase", 0) or 0)
        max_cap = int(request.form.get("max_discount_cap", 0) or 0)
    except (TypeError, ValueError):
        flash("Numerical values are invalid.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_str, "%Y-%m-%d")
    except ValueError:
        flash("Date format must be YYYY-MM-DD.", "danger")
        return redirect(url_for("admin.store_manager"))
        
    # Handle product scope
    products_scope = request.form.get("products_scope", "all").strip()
    scope_category = ""
    scope_product_ids = "[]"
    
    if products_scope == "category":
        scope_category = request.form.get("scope_category", "").strip()
    elif products_scope == "specific":
        product_ids = request.form.getlist("scope_product_ids[]")
        scope_product_ids = json.dumps([int(p) for p in product_ids if p])
        
    offer = StorePromotionalOffer(
        title=title,
        description=request.form.get("description", "").strip(),
        offer_type=offer_type,
        discount_value=discount_value,
        products_scope=products_scope,
        scope_category=scope_category,
        scope_product_ids=scope_product_ids,
        min_purchase=min_purchase,
        max_discount_cap=max_cap,
        is_active=request.form.get("is_active") == "1",
        start_date=start_date,
        end_date=end_date
    )
    
    try:
        db.session.add(offer)
        db.session.commit()
        flash("Promotional offer created successfully.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not create offer: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


@admin_bp.post("/store/homepage/offer/<int:offer_id>/delete")
@admin_required
def store_homepage_offer_delete(offer_id):
    from models.store import StorePromotionalOffer
    
    offer = StorePromotionalOffer.query.get_or_404(offer_id)
    try:
        db.session.delete(offer)
        db.session.commit()
        flash("Promotional offer deleted successfully.", "info")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not delete offer: {exc}", "danger")
        
    return redirect(url_for("admin.store_manager"))


