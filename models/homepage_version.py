from datetime import datetime
from models import db


class HomeVersion(db.Model):
    """Stores history snapshots of published homepage configurations."""

    __tablename__ = "home_versions"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    version_data = db.Column(db.Text, nullable=False)  # JSON serialized data of all keys
    published_by = db.Column(db.String(120), default="")
