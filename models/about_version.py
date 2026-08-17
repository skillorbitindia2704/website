from datetime import datetime
from models import db

class AboutVersion(db.Model):
    """Stores a history of published About Page CMS configurations."""
    __tablename__ = "about_versions"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    version_data = db.Column(db.Text, nullable=False)  # JSON serialized data of all fields
    published_by = db.Column(db.String(120), default="")
