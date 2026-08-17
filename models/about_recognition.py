from datetime import datetime

from models import db


class AboutRecognition(db.Model):
    __tablename__ = "about_recognition"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    subtitle = db.Column(db.String(200), default="")
    icon = db.Column(db.String(16), default="✅")
    image_path = db.Column(db.String(255), default="")
    organization = db.Column(db.String(160), default="")
    year = db.Column(db.String(10), default="")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

