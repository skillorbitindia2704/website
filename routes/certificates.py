import os
import re
import hmac
import hashlib
from typing import Optional

from flask import Blueprint, abort, current_app, render_template, request, send_file, url_for
from flask_login import current_user
from sqlalchemy.orm import joinedload

from models.course import Certificate, Enrollment

cert_bp = Blueprint("certificates", __name__)

# Certificate IDs are UUID strings (36 chars); cap input length for basic abuse resistance.
_MAX_CERT_ID_LEN = 80
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
                error = "No certificate found for this ID. It may be invalid, revoked, or mistyped."

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
    cert = _certificates_base_query().filter_by(certificate_uid=uid).first_or_404()
    vm = build_certificate_verify_view(cert, lookup_id=uid)
    return render_template("certificates/verify.html", cert=cert, vm=vm)


@cert_bp.get("/download/<string:uid>")
def download(uid):
    cert = Certificate.query.filter_by(certificate_uid=uid).first_or_404()
    if not current_user.is_authenticated:
        abort(403)
    if cert.user_id != current_user.id and not current_user.has_admin_access:
        abort(403)
    abs_path = os.path.join(current_app.root_path, cert.pdf_path.lstrip("/").replace("/", os.sep))
    return send_file(abs_path, as_attachment=True)
