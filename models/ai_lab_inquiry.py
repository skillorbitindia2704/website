from datetime import datetime

from models import db


class AILabInquiry(db.Model):
    """School / college inquiries for AI & robotics lab setup packages."""

    id = db.Column(db.Integer, primary_key=True)
    # NOTE: Keep existing column names for backward compatibility with existing routes/admin pages.
    institution_name = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(120), default="")
    contact_person = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False, index=True)
    package_interest = db.Column(db.String(40), default="")  # basic | advanced | premium | undecided
    # Optional richer inquiry fields (kept nullable/optional for compatibility).
    lab_type = db.Column(db.String(60), default="")  # Basic Lab / Advanced Lab / Premium Lab / Not sure yet
    budget_range = db.Column(db.String(60), default="")
    message = db.Column(db.Text, nullable=False, default="")
    requirements = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="new")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
