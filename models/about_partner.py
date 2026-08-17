from datetime import datetime

from models import db


class AboutPartnerLogo(db.Model):
    __tablename__ = "about_partners"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    logo_path = db.Column(db.String(255), default="")  # uploads/about/partners/...
    url = db.Column(db.String(255), default="")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

