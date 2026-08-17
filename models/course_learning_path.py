from datetime import datetime

from models import db


class CourseLearningPath(db.Model):
    """Roadmap-style learning path (e.g. AI Engineer)."""

    __tablename__ = "course_learning_paths"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    # Pipe-separated steps, e.g. "Python|ML Basics|Deep Learning|Computer Vision"
    steps = db.Column(db.Text, nullable=False, default="")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def step_list(self):
        if not self.steps:
            return []
        return [s.strip() for s in self.steps.split("|") if s.strip()]
