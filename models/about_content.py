from datetime import datetime

from models import db


class AboutContent(db.Model):
    """Key-value store for About page copy/SEO (single page, multiple keys)."""

    __tablename__ = "about_content"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

