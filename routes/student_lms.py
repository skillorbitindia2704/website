"""Student LMS routes."""

from __future__ import annotations

from datetime import datetime

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from models import db
from models.course import Certificate, Course, Enrollment
from models.lms import (
    CourseModule,
    CourseNote,
    LectureProgress,
    LiveSession,
    LiveSessionAttendance,
    LmsQuiz,
    QuizAttempt,
    RecordedSession,
)
from utils.certificates import generate_certificate_pdf
from utils.lms_progress import recompute_enrollment_progress, try_mark_quiz_passed_from_lms
from utils.notifications import notify_user
from utils.role_auth import student_required


def _paid_enrollment(course_id: int) -> Enrollment | None:
    en = Enrollment.query.filter_by(user_id=current_user.id, course_id=course_id).first()
    if not en or not en.is_paid:
        return None
    return en


def register(student_bp):
    @student_bp.get("/course/<int:course_id>")
    @student_required
    def student_course_hub(course_id):
        course = Course.query.get_or_404(course_id)
        en = _paid_enrollment(course_id)
        if not en:
            flash("Enroll and complete payment to access this learning hub.", "warning")
            return redirect(url_for("courses.buy_course", course_id=course_id))
        modules = CourseModule.query.filter_by(course_id=course.id).order_by(CourseModule.sort_order).all()
        lives = LiveSession.query.filter_by(course_id=course.id).order_by(LiveSession.scheduled_at.desc(), LiveSession.id.desc()).all()
        recordings = (
            RecordedSession.query.filter_by(course_id=course.id, is_visible=True)
            .order_by(RecordedSession.sort_order, RecordedSession.id)
            .all()
        )
        notes = (
            CourseNote.query.filter_by(course_id=course.id, is_visible=True)
            .order_by(CourseNote.sort_order, CourseNote.id)
            .all()
        )
        quizzes = LmsQuiz.query.filter_by(course_id=course.id, is_published=True).order_by(LmsQuiz.sort_order).all()
        prog_by_lec = {
            r.recorded_session_id: r
            for r in LectureProgress.query.filter_by(user_id=current_user.id).all()
            if r.recorded_session_id in {x.id for x in recordings}
        }
        recompute_enrollment_progress(en)
        db.session.commit()
        return render_template(
            "lms/student/course_hub.html",
            course=course,
            enrollment=en,
            modules=modules,
            lives=lives,
            recordings=recordings,
            notes=notes,
            quizzes=quizzes,
            prog_by_lec=prog_by_lec,
        )

    @student_bp.get("/live-sessions")
    @student_required
    def student_live_sessions():
        enrolls = Enrollment.query.filter_by(user_id=current_user.id, is_paid=True).all()
        cids = [e.course_id for e in enrolls]
        lives = []
        if cids:
            lives = (
                LiveSession.query.filter(LiveSession.course_id.in_(cids), LiveSession.status == "upcoming")
                .order_by(LiveSession.scheduled_at.asc(), LiveSession.id.asc())
                .all()
            )
        return render_template("lms/student/live_sessions.html", lives=lives, enrolls=enrolls)

    @student_bp.post("/live-sessions/<int:session_id>/attend")
    @student_required
    def student_live_attend(session_id):
        ls = LiveSession.query.get_or_404(session_id)
        en = _paid_enrollment(ls.course_id)
        if not en:
            flash("Access denied.", "danger")
            return redirect(url_for("student.student_live_sessions"))
        existing = LiveSessionAttendance.query.filter_by(user_id=current_user.id, live_session_id=ls.id).first()
        if not existing:
            db.session.add(LiveSessionAttendance(user_id=current_user.id, live_session_id=ls.id))
            db.session.commit()
            flash("Attendance recorded. Join the session when it starts.", "success")
        url = (ls.meet_url or "").strip()
        if url.startswith("http://") or url.startswith("https://"):
            return redirect(url)
        flash("Meeting link is not configured yet.", "warning")
        return redirect(url_for("student.student_live_sessions"))

    @student_bp.get("/recorded-sessions")
    @student_required
    def student_recorded_sessions():
        enrolls = Enrollment.query.filter_by(user_id=current_user.id, is_paid=True).all()
        cids = [e.course_id for e in enrolls]
        rows = []
        if cids:
            rows = (
                RecordedSession.query.filter(RecordedSession.course_id.in_(cids), RecordedSession.is_visible == True)
                .order_by(RecordedSession.sort_order, RecordedSession.id)
                .all()
            )
        prog = {p.recorded_session_id: p for p in LectureProgress.query.filter_by(user_id=current_user.id).all()}
        return render_template("lms/student/recorded_list.html", rows=rows, enrolls=enrolls, prog=prog)

    @student_bp.post("/recorded-sessions/<int:rec_id>/progress")
    @student_required
    def student_lecture_progress(rec_id):
        rec = RecordedSession.query.get_or_404(rec_id)
        en = _paid_enrollment(rec.course_id)
        if not en:
            flash("Access denied.", "danger")
            return redirect(url_for("student.student_recorded_sessions"))
        pct = int(request.form.get("progress_pct", 0) or 0)
        pct = max(0, min(100, pct))
        done = request.form.get("completed") == "on" or pct >= 95
        row = LectureProgress.query.filter_by(user_id=current_user.id, recorded_session_id=rec.id).first()
        if not row:
            row = LectureProgress(user_id=current_user.id, recorded_session_id=rec.id, progress_pct=pct, completed=done)
            db.session.add(row)
        else:
            row.progress_pct = max(row.progress_pct, pct)
            row.completed = row.completed or done
        recompute_enrollment_progress(en)
        db.session.commit()
        flash("Progress saved.", "success")
        next_url = request.form.get("next") or url_for("student.student_course_hub", course_id=rec.course_id)
        return redirect(next_url)

    @student_bp.get("/notes")
    @student_required
    def student_notes():
        enrolls = Enrollment.query.filter_by(user_id=current_user.id, is_paid=True).all()
        cids = [e.course_id for e in enrolls]
        rows = []
        if cids:
            rows = (
                CourseNote.query.filter(CourseNote.course_id.in_(cids), CourseNote.is_visible == True)
                .order_by(CourseNote.sort_order, CourseNote.id)
                .all()
            )
        return render_template("lms/student/notes_list.html", rows=rows, enrolls=enrolls)

    @student_bp.route("/quiz/<int:quiz_id>", methods=["GET", "POST"])
    @student_required
    def student_quiz_take(quiz_id):
        quiz = LmsQuiz.query.get_or_404(quiz_id)
        course = Course.query.get_or_404(quiz.course_id)
        en = _paid_enrollment(course.id)
        if not en:
            flash("Purchase the course to take this quiz.", "warning")
            return redirect(url_for("courses.buy_course", course_id=course.id))
        questions = quiz.questions_json or []
        if request.method == "POST":
            score = 0
            for i, q in enumerate(questions):
                sel = (request.form.get(f"sq_{i}") or "").strip()
                correct = (q.get("correctAnswer") or "").strip()
                if sel and correct and sel.lower() == correct.lower():
                    score += 1
            max_score = max(len(questions), 1)
            score_percent = int(round(100 * score / max_score))
            passed = score_percent >= (quiz.pass_percent or 60)
            attempt = QuizAttempt(
                user_id=current_user.id,
                quiz_id=quiz.id,
                score=score_percent,
                max_score=100,
                passed=passed,
                duration_seconds=int(request.form.get("duration_seconds", 0) or 0),
                details_json={"percent": score_percent, "at": datetime.utcnow().isoformat()},
            )
            db.session.add(attempt)
            if passed:
                current_user.points += 5
                current_user.update_badge()
            if try_mark_quiz_passed_from_lms(en):
                if en.progress_pct < 100:
                    en.progress_pct = 100
                existing_cert = Certificate.query.filter_by(user_id=current_user.id, course_id=course.id).first()
                if not existing_cert:
                    uid, pdf_path = generate_certificate_pdf(current_user.full_name, course.title)
                    db.session.add(
                        Certificate(certificate_uid=uid, user_id=current_user.id, course_id=course.id, pdf_path=pdf_path)
                    )
                    notify_user(current_user.id, f"Certificate issued for “{course.title}”.")
                flash("All course quiz requirements met. Certificate unlocked.", "success")
            elif passed:
                flash(f"Score: {score_percent}% — passed.", "success")
            else:
                flash(f"Score: {score_percent}% — keep practicing.", "warning")
            db.session.commit()
            return redirect(url_for("student.student_quiz_take", quiz_id=quiz.id))
        last = (
            QuizAttempt.query.filter_by(user_id=current_user.id, quiz_id=quiz.id)
            .order_by(QuizAttempt.created_at.desc())
            .first()
        )
        return render_template(
            "lms/student/quiz_take.html",
            quiz=quiz,
            course=course,
            enrollment=en,
            questions=questions,
            last_attempt=last,
        )
