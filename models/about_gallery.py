from datetime import datetime

from models import db


class AboutGalleryImage(db.Model):
    __tablename__ = "about_gallery"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False, default="Gallery")
    image_path = db.Column(db.String(255), nullable=False)  # uploads/about/gallery/...
    category = db.Column(db.String(80), default="")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

