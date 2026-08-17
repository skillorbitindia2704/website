from datetime import datetime
from models import db

class AboutActivityLog(db.Model):
    """Audit logs for operations performed in the About Page Manager."""
    __tablename__ = "about_activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    action = db.Column(db.String(255), nullable=False)
    admin_email = db.Column(db.String(120), default="")
    ip_address = db.Column(db.String(45), default="")
