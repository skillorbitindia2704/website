import os
from uuid import uuid4

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from werkzeug.utils import secure_filename
from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError

from models import db
from models.internship import Internship, InternshipApplication
from utils.decorators import login_required
from utils.notifications import notify_user

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
@login_required
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
    
    try:
        app_item = InternshipApplication(
            internship_id=internship.id,
            user_id=current_user.id,
            cover_letter=cover_letter,
            resume_path=f"/static/uploads/resumes/{file_name}",
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
        except:
            pass
        flash("Failed to save application. Please try again.", "danger")
        return redirect(url_for("internships.listing"))
