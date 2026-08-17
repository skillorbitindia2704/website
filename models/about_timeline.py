from datetime import datetime

from models import db


class AboutTimelineEntry(db.Model):
    __tablename__ = "about_timeline"

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.String(8), nullable=False)  # "2026"
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    achievement_badge = db.Column(db.String(100), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

