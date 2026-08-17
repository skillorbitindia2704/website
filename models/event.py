from datetime import datetime

from models import db


class Event(db.Model):
    """Upcoming events/workshops shown on the homepage."""

    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    date_text = db.Column(db.String(80), default="")  # keep simple, editable
    location = db.Column(db.String(160), default="")
    register_url = db.Column(db.String(255), default="")
    mode = db.Column(db.String(40), default="")  # Online / Hybrid / On-site
    image_path = db.Column(db.String(255), default="")  # static-relative uploads/...
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

