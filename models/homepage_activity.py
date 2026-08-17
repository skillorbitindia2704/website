from datetime import datetime
from models import db


class HomeActivityLog(db.Model):
    """Audit logs for actions performed in the Homepage Manager."""

    __tablename__ = "home_activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    action = db.Column(db.String(255), nullable=False)
    admin_email = db.Column(db.String(120), default="")
    ip_address = db.Column(db.String(45), default="")
