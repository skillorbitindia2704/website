from datetime import datetime

from models import db


class CoursesPageContent(db.Model):
    """Key/value copy for the public courses catalog page."""

    __tablename__ = "courses_page_content"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
