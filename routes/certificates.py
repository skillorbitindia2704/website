import os
import re
import hmac
import hashlib
import secrets
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, unquote
from werkzeug.utils import secure_filename
from typing import Optional

from flask import Blueprint, abort, current_app, render_template, request, send_file, url_for
from flask_login import current_user
from sqlalchemy.orm import joinedload

from models.course import Certificate, Enrollment, Course
from models.custom_certificate import CustomCertificate
from models.internship import Internship
from models.user import User
from models import db
from utils.role_auth import admin_required

cert_bp = Blueprint("certificates", __name__)

# Certificate IDs are UUID strings (36 chars); cap input length for basic abuse resistance.
_MAX_CERT_ID_LEN = 120
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _certificates_base_query():
    return Certificate.query.options(
        joinedload(Certificate.user),
        joinedload(Certificate.course),
    )


def _skills_from_course(course) -> list:
    raw = (course.learning_outcomes or "").strip()
    if not raw:
        return []
    skills = []
    for line in raw.replace("\r", "").split("\n"):
        t = line.strip().lstrip("•-*").strip()
        if t:
            skills.append(t[:160])
    return skills[:14]


def build_certificate_verify_view(cert: Certificate, lookup_id: Optional[str] = None):
    """Safe, read-only view model for public verification templates."""
    enrollment = Enrollment.query.filter_by(user_id=cert.user_id, course_id=cert.course_id).first()
    verify_url = url_for("certificates.verify", uid=cert.certificate_uid, _external=True)
    can_download = bool(
        current_user.is_authenticated
        and (current_user.id == cert.user_id or getattr(current_user, "has_admin_access", False))
    )
    grade = "Pass (quiz cleared)" if (enrollment and enrollment.quiz_passed) else "Completed"
    category = (cert.course.category or "").strip() or "Professional credential"
    instructor = (cert.course.instructor_name or "").strip() or "Skill Orbit Faculty"
    
    # Secure cryptographic hash generation for verification
    secret = current_app.config["SECRET_KEY"].encode("utf-8")
    verification_hash = hmac.new(secret, cert.certificate_uid.encode("utf-8"), hashlib.sha256).hexdigest()
    
    return {
        "verify_url": verify_url,
        "can_download": can_download,
        "skills": _skills_from_course(cert.course),
        "grade": grade,
        "category": category,
        "instructor": instructor,
        "enrollment": enrollment,
        "lookup_id": (lookup_id or cert.certificate_uid or "").strip(),
        "verification_hash": verification_hash,
    }


def _normalize_lookup_id(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    # Allow pasted URLs containing the UUID
    m = _UUID_RE.search(s)
    if m:
        return m.group(0).lower()
    if "://" in s:
        path = unquote(urlparse(s).path).rstrip("/")
        if path:
            return path.rsplit("/", 1)[-1]
    return s


@cert_bp.route("/verify", methods=["GET", "POST"])
def verify_lookup():
    cert = None
    error = None
    lookup_id = ""
    if request.method == "POST":
        lookup_id = _normalize_lookup_id(request.form.get("certificate_id", ""))
    else:
        lookup_id = _normalize_lookup_id(request.args.get("id", ""))

    if request.method == "POST" and not lookup_id:
        error = "Please enter a certificate ID."
    elif lookup_id:
        if len(lookup_id) > _MAX_CERT_ID_LEN:
            error = "Certificate ID is invalid or too long."
        else:
            cert = _certificates_base_query().filter_by(certificate_uid=lookup_id).first()
            if not cert:
                custom = CustomCertificate.query.filter_by(certificate_uid=lookup_id).first()
                if custom:
                    return render_template("certificates/verify_custom.html", cert=custom, vm=_custom_verify_view(custom))
                error = "Certificate Not Found. Please check the ID and try again."

    vm = build_certificate_verify_view(cert, lookup_id=lookup_id) if cert else None
    return render_template(
        "certificates/verify_lookup.html",
        cert=cert,
        error=error,
        lookup_id=lookup_id,
        vm=vm,
    )


@cert_bp.get("/verify/<string:uid>")
def verify(uid: str):
    if len(uid) > _MAX_CERT_ID_LEN:
        abort(404)
    cert = _certificates_base_query().filter_by(certificate_uid=uid).first()
    if cert:
        vm = build_certificate_verify_view(cert, lookup_id=uid)
        return render_template("certificates/verify.html", cert=cert, vm=vm)
    custom = CustomCertificate.query.filter_by(certificate_uid=uid).first_or_404()
    return render_template("certificates/verify_custom.html", cert=custom, vm=_custom_verify_view(custom))


@cert_bp.get("/download/<string:uid>")
def download(uid):
    cert = Certificate.query.filter_by(certificate_uid=uid).first_or_404()
    if not current_user.is_authenticated:
        abort(403)
    if cert.user_id != current_user.id and not current_user.has_admin_access:
        abort(403)
    abs_path = os.path.join(current_app.root_path, cert.pdf_path.lstrip("/").replace("/", os.sep))
    return send_file(abs_path, as_attachment=True)


def _custom_verify_view(cert):
    from flask import url_for
    return {
        "verify_url": url_for("certificates.verify", uid=cert.certificate_uid, _external=True),
        "can_download": bool(current_user.is_authenticated and (
            current_user.id == cert.user_id or getattr(current_user, "has_admin_access", False)
        )),
        "status": cert.verification_status,
    }


def _certificate_storage_root():
    configured = os.getenv("CERTIFICATE_STORAGE_DIR", "").strip()
    root = Path(configured).expanduser() if configured else Path(current_app.instance_path) / "private_certificates"
    return root.resolve()

def _save_custom_pdf(upload):
    if not upload or not upload.filename:
        raise ValueError("Please choose a certificate PDF.")
    if not upload.filename.lower().endswith(".pdf"):
        raise ValueError("Only PDF certificates are supported.")
    if upload.mimetype not in {"application/pdf", "application/octet-stream", "application/x-pdf"}:
        raise ValueError("The uploaded file must have PDF content type.")
    data = upload.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Certificate PDF must be 10 MB or smaller.")
    if not data.startswith(b"%PDF-"):
        raise ValueError("The uploaded file does not appear to be a valid PDF.")
    root = _certificate_storage_root()
    root.mkdir(parents=True, exist_ok=True)
    stored_path = root / (secrets.token_hex(24) + ".pdf")
    stored_path.write_bytes(data)
    return str(stored_path)


@cert_bp.post("/admin/upload-custom")
@admin_required
def upload_custom_certificate():
    from flask import flash, redirect
    stored_path = None
    try:
        learner = User.query.get_or_404(int(request.form.get("user_id", "")))
        if learner.role != "student":
            raise ValueError("Select a registered learner account.")
        program_type = (request.form.get("program_type") or "course").strip().lower()
        allowed_program_types = {"course", "internship", "teacher_training", "workshop", "summer_camp", "bootcamp", "seminar"}
        if program_type not in allowed_program_types:
            raise ValueError("Select a valid Course / Program type.")
        course_id, program_ref_id = None, None
        if program_type == "internship":
            program_id = int(request.form.get("program_id", ""))
            program = Internship.query.get_or_404(program_id)
            program_ref_id, program_title = program.id, program.title
        elif program_type == "course":
            program_id = int(request.form.get("program_id", ""))
            program = Course.query.get_or_404(program_id)
            course_id, program_title = program.id, program.title
        else:
            program_title = (request.form.get("program_title") or "").strip()[:180]
            if not program_title:
                raise ValueError("Enter the name of the selected program.")

        title = (request.form.get("certificate_title") or "Certificate of Completion").strip()[:180]
        uid = (request.form.get("certificate_uid") or "").strip()
        if not uid:
            uid = str(__import__("uuid").uuid4())
        if len(uid) > 120 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,119}", uid):
            raise ValueError("Certificate ID must be 3–120 characters using letters, numbers, dot, underscore or hyphen.")
        if Certificate.query.filter_by(certificate_uid=uid).first() or CustomCertificate.query.filter_by(certificate_uid=uid).first():
            raise ValueError("This Certificate ID already exists. Please use a unique ID.")
        status = request.form.get("verification_status", "verified").lower()
        if status not in {"verified", "pending", "revoked", "disabled"}:
            raise ValueError("Choose a valid verification status.")
        issued_at = date.fromisoformat(request.form.get("issued_at", ""))
        stored_path = _save_custom_pdf(request.files.get("certificate_file"))
        cert = CustomCertificate(
            certificate_uid=uid, user_id=learner.id, course_id=course_id,
            program_type=program_type, program_ref_id=program_ref_id, program_title=program_title,
            certificate_title=title or "Certificate of Completion", issued_at=issued_at,
            file_path=stored_path, verification_status=status,
            remarks=(request.form.get("remarks") or "").strip()[:4000],
            created_by_admin_id=current_user.id,
        )
        db.session.add(cert)
        db.session.commit()
        flash("Custom certificate uploaded and linked to the learner.", "success")
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        if stored_path and os.path.isfile(stored_path):
            os.remove(stored_path)
        flash(str(exc) or "Please check the certificate form.", "danger")
    except Exception:
        db.session.rollback()
        if stored_path and os.path.isfile(stored_path):
            os.remove(stored_path)
        current_app.logger.exception("Custom certificate upload failed")
        flash("Certificate upload failed. Please check the file and try again.", "danger")
    return redirect(url_for("admin.issue_certificate"))


@cert_bp.get("/download-custom/<string:uid>")
def download_custom_certificate(uid):
    cert = CustomCertificate.query.filter_by(certificate_uid=uid).first_or_404()
    if not current_user.is_authenticated:
        abort(403)
    if cert.user_id != current_user.id and not getattr(current_user, "has_admin_access", False):
        abort(403)
    path = Path(cert.file_path).resolve()
    private_root = _certificate_storage_root()
    if private_root not in path.parents or not path.is_file():
        abort(404)
    return send_file(path, as_attachment=True,
                     download_name=secure_filename(cert.certificate_title) + ".pdf",
                     mimetype="application/pdf")


@cert_bp.get("/view-custom/<string:uid>")
def view_custom_certificate(uid):
    cert = CustomCertificate.query.filter_by(certificate_uid=uid).first_or_404()
    if not current_user.is_authenticated:
        abort(403)
    if cert.user_id != current_user.id and not getattr(current_user, "has_admin_access", False):
        abort(403)
    path = Path(cert.file_path).resolve()
    private_root = _certificate_storage_root()
    if private_root not in path.parents or not path.is_file():
        abort(404)
    return send_file(path, as_attachment=False, download_name=secure_filename(cert.certificate_title) + ".pdf", mimetype="application/pdf")

@cert_bp.post("/admin/custom/<int:certificate_id>/manage")
@admin_required
def manage_custom_certificate(certificate_id):
    from flask import flash, redirect
    cert = CustomCertificate.query.get_or_404(certificate_id)
    status = request.form.get("verification_status", cert.verification_status).lower()
    if status not in {"verified", "pending", "revoked"}:
        flash("Invalid verification status.", "danger")
        return redirect(url_for("admin.issue_certificate"))
    new_uid = (request.form.get("certificate_uid") or cert.certificate_uid).strip()
    if len(new_uid) > 120 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,119}", new_uid):
        flash("Certificate ID must be 3–120 characters using letters, numbers, dot, underscore or hyphen.", "danger")
        return redirect(url_for("admin.issue_certificate"))
    duplicate_system = Certificate.query.filter_by(certificate_uid=new_uid).first()
    duplicate_custom = CustomCertificate.query.filter_by(certificate_uid=new_uid).first()
    if duplicate_system or (duplicate_custom and duplicate_custom.id != cert.id):
        flash("This Certificate ID already exists. Please use a unique ID.", "danger")
        return redirect(url_for("admin.issue_certificate"))
    cert.certificate_uid = new_uid
    cert.verification_status = status
    cert.certificate_title = (request.form.get("certificate_title") or cert.certificate_title).strip()[:180]
    cert.remarks = (request.form.get("remarks") or "").strip()[:4000]
    issued = (request.form.get("issued_at") or "").strip()
    if issued:
        try:
            cert.issued_at = date.fromisoformat(issued)
        except ValueError:
            flash("Invalid issue date.", "danger")
            return redirect(url_for("admin.issue_certificate"))
    replacement = request.files.get("certificate_file")
    new_path = None
    old_path = cert.file_path
    if replacement and replacement.filename:
        try:
            new_path = _save_custom_pdf(replacement)
            cert.file_path = new_path
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin.issue_certificate"))
    try:
        db.session.commit()
        if new_path and old_path and os.path.isfile(old_path):
            os.remove(old_path)
        flash("Custom certificate details updated.", "success")
    except Exception:
        db.session.rollback()
        if new_path and os.path.isfile(new_path):
            os.remove(new_path)
        current_app.logger.exception("Could not update custom certificate")
        flash("Could not save certificate changes.", "danger")
    return redirect(url_for("admin.issue_certificate"))
