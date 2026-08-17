from datetime import datetime

from models import db


class AboutCounter(db.Model):
    __tablename__ = "about_counters"

    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(120), nullable=False)
    value = db.Column(db.Integer, nullable=False, default=0)
    suffix = db.Column(db.String(16), default="+")
    icon = db.Column(db.String(16), default="✨")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

