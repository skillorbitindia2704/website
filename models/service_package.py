from datetime import datetime

from models import db


class ServicePackage(db.Model):
    """Dynamic public service packages managed from admin."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    slug = db.Column(db.String(140), nullable=False, index=True)
    short_description = db.Column(db.String(255), nullable=False, default="")
    full_description = db.Column(db.Text, nullable=False, default="")
    pricing_text = db.Column(db.String(120), nullable=False, default="")
    features = db.Column(db.Text, nullable=False, default="")
    icon = db.Column(db.String(20), nullable=False, default="🔧")
    image = db.Column(db.String(255), nullable=False, default="")
    button_text = db.Column(db.String(60), nullable=False, default="Request service")
    button_link = db.Column(db.String(255), nullable=False, default="#service-modal")
    category = db.Column(db.String(80), nullable=False, default="")
    badge_text = db.Column(db.String(80), nullable=False, default="")
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_features_list(self):
        if not self.features:
            return []
        return [item.strip() for item in self.features.split("\n") if item.strip()]

