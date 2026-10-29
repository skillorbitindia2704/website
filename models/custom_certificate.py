from datetime import date, datetime
from models import db


class CustomCertificate(db.Model):
    """Metadata for manually designed PDF certificates; file contents are stored privately."""
    id = db.Column(db.Integer, primary_key=True)
    certificate_uid = db.Column(db.String(120), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=True, index=True)
    program_type = db.Column(db.String(20), nullable=False, default="course")
    program_ref_id = db.Column(db.Integer, nullable=True)
    program_title = db.Column(db.String(180), nullable=False, default="")
    certificate_title = db.Column(db.String(180), nullable=False, default="Certificate of Completion")
    issued_at = db.Column(db.Date, nullable=False, default=date.today)
    file_path = db.Column(db.String(500), nullable=False)
    certificate_type = db.Column(db.String(30), nullable=False, default="custom_uploaded")
    verification_status = db.Column(db.String(20), nullable=False, default="verified", index=True)
    remarks = db.Column(db.Text, default="")
    created_by_admin_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])
    course = db.relationship("Course", foreign_keys=[course_id])
    created_by_admin = db.relationship("User", foreign_keys=[created_by_admin_id])
