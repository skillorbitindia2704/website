from datetime import datetime

from models import db


class AILabCurriculumBlock(db.Model):
    """Curriculum/roadmap blocks editable from admin."""

    __tablename__ = "curriculum"

    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.String(80), nullable=False)  # Grade 6–8, Grade 9–10, etc.
    title = db.Column(db.String(160), nullable=False)
    focus_areas = db.Column(db.Text, nullable=False, default="")  # newline-separated topics
    duration = db.Column(db.String(80), default="")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def focus_list(self):
        if not self.focus_areas:
            return []
        return [x.strip() for x in self.focus_areas.split("\n") if x.strip()]

