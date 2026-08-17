"""LMS tables: modules, live/recorded sessions, file notes, quizzes, progress.

Legacy course fields (live_class JSON, videos, notes, quiz) remain supported.
"""

from datetime import datetime

from sqlalchemy import JSON

from models import db


class CourseModule(db.Model):
    """Course section / module for organizing LMS content."""

    __tablename__ = "course_module"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    sort_order = db.Column(db.Integer, default=0, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course", backref=db.backref("lms_modules", lazy="dynamic"))


class LiveSession(db.Model):
    __tablename__ = "live_session"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    module_id = db.Column(db.Integer, db.ForeignKey("course_module.id"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    meet_url = db.Column(db.String(500), nullable=False, default="")
    scheduled_at = db.Column(db.DateTime, nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default="upcoming")  # upcoming | completed
    session_update = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course", backref=db.backref("live_sessions", lazy="dynamic"))
    module = db.relationship("CourseModule", backref=db.backref("live_sessions", lazy="dynamic"))


class RecordedSession(db.Model):
    __tablename__ = "recorded_session"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False, index=True)
    module_id = db.Column(db.Integer, db.ForeignKey("course_module.id"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    video_path = db.Column(db.String(500), nullable=False, default="")
    resource_files = db.Column(JSON, default=lambda: [])
    is_visible = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course", backref=db.backref("recorded_sessions", lazy="dynamic"))
    module = db.relationship("CourseModule", backref=db.backref("recorded_sessions", lazy="dynamic"))


class CourseNote(db.Model):
    """Uploaded note / resource file (PDF, DOC, etc.)."""

    __tablename__ = "course_note"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False, index=True)
    module_id = db.Column(db.Integer, db.ForeignKey("course_module.id"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    file_path = db.Column(db.String(500), nullable=False, default="")
    is_visible = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course", backref=db.backref("lms_notes", lazy="dynamic"))
    module = db.relationship("CourseModule", backref=db.backref("lms_notes", lazy="dynamic"))


class LmsQuiz(db.Model):
    __tablename__ = "lms_quiz"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False, index=True)
    module_id = db.Column(db.Integer, db.ForeignKey("course_module.id"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False, default="Quiz")
    time_limit_seconds = db.Column(db.Integer, default=0)  # 0 = no limit
    questions_json = db.Column(JSON, default=lambda: [])
    pass_percent = db.Column(db.Integer, default=60)
    is_published = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship("Course", backref=db.backref("lms_quizzes", lazy="dynamic"))
    module = db.relationship("CourseModule", backref=db.backref("lms_quizzes", lazy="dynamic"))


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempt"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("lms_quiz.id"), nullable=False, index=True)
    score = db.Column(db.Integer, nullable=False, default=0)
    max_score = db.Column(db.Integer, nullable=False, default=0)
    passed = db.Column(db.Boolean, default=False, nullable=False)
    duration_seconds = db.Column(db.Integer, default=0)
    details_json = db.Column(JSON, default=lambda: {})
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship("User", backref=db.backref("quiz_attempts", lazy="dynamic"))
    quiz = db.relationship("LmsQuiz", backref=db.backref("attempts", lazy="dynamic"))


class LectureProgress(db.Model):
    __tablename__ = "lecture_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    recorded_session_id = db.Column(db.Integer, db.ForeignKey("recorded_session.id"), nullable=False, index=True)
    progress_pct = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("lecture_progress_rows", lazy="dynamic"))
    lecture = db.relationship("RecordedSession", backref=db.backref("progress_rows", lazy="dynamic"))

    __table_args__ = (db.UniqueConstraint("user_id", "recorded_session_id", name="uq_user_lecture_progress"),)


class LiveSessionAttendance(db.Model):
    __tablename__ = "live_session_attendance"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    live_session_id = db.Column(db.Integer, db.ForeignKey("live_session.id"), nullable=False, index=True)
    marked_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.String(255), default="")

    user = db.relationship("User", backref=db.backref("live_attendance", lazy="dynamic"))
    live_session = db.relationship("LiveSession", backref=db.backref("attendance_rows", lazy="dynamic"))

    __table_args__ = (db.UniqueConstraint("user_id", "live_session_id", name="uq_user_live_session"),)
