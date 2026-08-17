from datetime import datetime

from models import db


class HomeTestimonial(db.Model):
    """Homepage testimonials (separate from AI Lab testimonials)."""

    __tablename__ = "home_testimonials"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    city = db.Column(db.String(120), default="")
    course_completed = db.Column(db.String(200), default="")
    rating = db.Column(db.Integer, default=5)
    quote = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(255), default="")  # uploads/home/testimonials/...
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

