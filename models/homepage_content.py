from datetime import datetime
from models import db


class HomeContent(db.Model):
    """Key-value store for Homepage copy, animations, theme, and SEO settings."""

    __tablename__ = "home_content"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
