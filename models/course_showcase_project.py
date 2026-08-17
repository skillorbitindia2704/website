from datetime import datetime

from models import db


class CourseShowcaseProject(db.Model):
    """Student project cards on the courses page."""

    __tablename__ = "course_showcase_projects"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    technologies = db.Column(db.String(255), default="")
    image_path = db.Column(db.String(255), default="")
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def tech_list(self):
        if not self.technologies:
            return []
        return [t.strip() for t in self.technologies.split(",") if t.strip()]
