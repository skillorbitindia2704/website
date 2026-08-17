from datetime import datetime

from models import db


class AILabProject(db.Model):
    """Student project showcase items."""

    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    difficulty = db.Column(db.String(40), default="Beginner")
    technologies = db.Column(db.String(255), default="")  # comma/newline separated
    media_path = db.Column(db.String(255), default="")  # image or video thumbnail path
    description = db.Column(db.Text, default="")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def technologies_list(self):
        if not self.technologies:
            return []
        # Supports either comma-separated or newline-separated tech lists.
        raw = self.technologies.replace("\n", ",")
        return [x.strip() for x in raw.split(",") if x.strip()]

