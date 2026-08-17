from datetime import datetime

from models import db


class AILabTestimonial(db.Model):
    """Testimonials from principals, students, and workshop feedback."""

    __tablename__ = "testimonials"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    role = db.Column(db.String(160), default="")
    organization = db.Column(db.String(200), default="")
    quote = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, default=5)
    logo_path = db.Column(db.String(255), default="")  # optional logo path
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

