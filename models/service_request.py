from datetime import datetime

from models import db


class ServiceRequest(db.Model):
    """Inbound IT / technology service leads from the public website."""

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False)
    service_slug = db.Column(db.String(80), nullable=False)
    service_title = db.Column(db.String(120), nullable=False)
    requirement = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="new")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
