from datetime import datetime

from models import db


class AILabHardwareItem(db.Model):
    """Hardware items/icons shown on the AI & Robotics Lab page."""

    __tablename__ = "hardware_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(120), default="")
    description = db.Column(db.Text, default="")
    icon_path = db.Column(db.String(255), default="")  # e.g. uploads/ai_lab/icons/xyz.png
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

