from datetime import datetime

from models import db


class AboutTeamMember(db.Model):
    __tablename__ = "about_team"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    role = db.Column(db.String(160), nullable=False, default="")
    bio = db.Column(db.Text, default="")
    image_path = db.Column(db.String(255), default="")  # uploads/about/team/...
    linkedin_url = db.Column(db.String(255), default="")
    github_url = db.Column(db.String(255), default="")
    instagram_url = db.Column(db.String(255), default="")
    email = db.Column(db.String(120), default="")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

