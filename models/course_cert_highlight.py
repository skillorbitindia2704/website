from datetime import datetime

from models import db


class CourseCertHighlight(db.Model):
    """Certificate / trust highlights on the courses page."""

    __tablename__ = "course_cert_highlights"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    subtitle = db.Column(db.String(220), default="")
    icon = db.Column(db.String(16), default="🏆")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
