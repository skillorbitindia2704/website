"""Enrollment progress helpers for LMS + legacy content."""

from models import db
from models.course import Enrollment
from models.lms import LectureProgress, LmsQuiz, QuizAttempt, RecordedSession


def recompute_enrollment_progress(enrollment: Enrollment) -> None:
    """Blend recorded lecture completion with legacy progress_pct (never decrease below legacy)."""
    course = enrollment.course
    if not course:
        return
    lectures = RecordedSession.query.filter_by(course_id=course.id, is_visible=True).all()
    if not lectures:
        return
    done = 0
    for lec in lectures:
        row = LectureProgress.query.filter_by(user_id=enrollment.user_id, recorded_session_id=lec.id).first()
        if row and row.completed:
            done += 1
    pct = int(round(100 * done / max(len(lectures), 1)))
    enrollment.progress_pct = max(enrollment.progress_pct or 0, min(100, pct))


def enrollment_passed_all_lms_quizzes(enrollment: Enrollment) -> bool:
    quizzes = LmsQuiz.query.filter_by(course_id=enrollment.course_id, is_published=True).all()
    if not quizzes:
        return False
    for q in quizzes:
        best = (
            QuizAttempt.query.filter_by(user_id=enrollment.user_id, quiz_id=q.id)
            .order_by(QuizAttempt.passed.desc(), QuizAttempt.score.desc())
            .first()
        )
        if not best or not best.passed:
            return False
    return True


def try_mark_quiz_passed_from_lms(enrollment: Enrollment) -> bool:
    if enrollment_passed_all_lms_quizzes(enrollment):
        enrollment.quiz_passed = True
        return True
    return False
