from datetime import datetime

from models import db


class AILabBrochure(db.Model):
    """Brochure files uploaded by admin."""

    __tablename__ = "brochures"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False, default="AI & Robotics Lab Brochure")
    file_path = db.Column(db.String(255), nullable=False)  # static/uploads/ai_lab/...
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

