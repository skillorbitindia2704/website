from datetime import datetime

from models import db


class GoogleIdentity(db.Model):
    """A verified Google account linked to one existing Skill Orbit user."""

    __tablename__ = "google_identity"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    google_sub = db.Column(db.String(255), nullable=False, unique=True, index=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
