from datetime import datetime

from models import db


class AILabGalleryImage(db.Model):
    """Gallery tiles editable from admin panel."""

    __tablename__ = "gallery_images"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80), default="")  # Robotics Lab Setup, Drone Lab, etc.
    image_path = db.Column(db.String(255), nullable=False)  # uploads/ai_lab/gallery/...
    caption = db.Column(db.String(255), default="")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

