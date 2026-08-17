"""Teacher LMS routes (registered on `teacher_bp` from teacher_routes)."""

from __future__ import annotations

import json
from datetime import datetime

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import or_

from models import db
from models.course import Course, Enrollment
from models.lms import CourseModule, CourseNote, LiveSession, LmsQuiz, RecordedSession
from utils.lms_uploads import ALLOWED_DOCS, ALLOWED_IMAGE, ALLOWED_VIDEO, save_upload
from utils.role_auth import teacher_required


def _teacher_course_filter():
    uid = current_user.id
    return or_(Course.teacher_id == uid, Course.teacher_id.is_(None))


def _get_course_for_teacher(course_id: int) -> Course | None:
    return Course.query.filter(Course.id == course_id, _teacher_course_filter()).first()


def register(teacher_bp):
    @teacher_bp.get("/courses")
    @teacher_required
    def teacher_courses():
        courses = (
            Course.query.filter(_teacher_course_filter()).order_by(Course.created_at.desc()).all()
        )
        return render_template("lms/teacher/courses.html", courses=courses)

    @teacher_bp.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
    @teacher_required
    def teacher_edit_course(course_id):
        course = _get_course_for_teacher(course_id)
        if not course:
            flash("Course not found.", "danger")
            return redirect(url_for("teacher.teacher_courses"))
        modules = CourseModule.query.filter_by(course_id=course.id).order_by(CourseModule.sort_order).all()
        if request.method == "POST":
            course.title = request.form.get("title", course.title).strip() or course.title
            course.description = request.form.get("description", "").strip()
            course.instructor_name = request.form.get("instructor_name", "").strip() or course.instructor_name
            course.duration = request.form.get("duration", "").strip() or course.duration
            course.level = request.form.get("level", "").strip() or course.level
            course.price_inr = int(request.form.get("price_inr", course.price_inr) or course.price_inr)
            course.content = request.form.get("content", "").strip()
            course.category = request.form.get("category", "").strip()
            course.prerequisites = request.form.get("prerequisites", "").strip()
            course.learning_outcomes = request.form.get("learning_outcomes", "").strip()
            course.is_published = request.form.get("is_published") == "on"
            if "thumbnail" in request.files:
                path = save_upload(
                    request.files["thumbnail"],
                    "thumb",
                    ALLOWED_IMAGE,
                    3 * 1024 * 1024,
                    prefix="thumb_",
                )
                if path:
                    course.thumbnail_path = path
            db.session.commit()
            flash("Course updated.", "success")
            return redirect(url_for("teacher.teacher_edit_course", course_id=course.id))
        return render_template(
            "lms/teacher/course_edit.html",
            course=course,
            modules=modules,
        )

    @teacher_bp.post("/courses/<int:course_id>/delete")
    @teacher_required
    def teacher_delete_course(course_id):
        course = _get_course_for_teacher(course_id)
        if not course:
            flash("Course not found.", "danger")
            return redirect(url_for("teacher.teacher_courses"))
        if Enrollment.query.filter_by(course_id=course.id).count():
            flash("Cannot delete a course with enrollments. Unpublish it instead.", "danger")
            return redirect(url_for("teacher.teacher_edit_course", course_id=course_id))
        db.session.delete(course)
        db.session.commit()
        flash("Course deleted.", "info")
        return redirect(url_for("teacher.teacher_courses"))

    @teacher_bp.post("/courses/<int:course_id>/modules/add")
    @teacher_required
    def teacher_module_add(course_id):
        course = _get_course_for_teacher(course_id)
        if not course:
            flash("Course not found.", "danger")
            return redirect(url_for("teacher.teacher_courses"))
        title = request.form.get("title", "").strip()
        if len(title) < 2:
            flash("Module title is required.", "danger")
            return redirect(url_for("teacher.teacher_edit_course", course_id=course_id))
        sort_order = int(request.form.get("sort_order", 0) or 0)
        db.session.add(CourseModule(course_id=course.id, title=title, sort_order=sort_order))
        db.session.commit()
        flash("Module added.", "success")
        return redirect(url_for("teacher.teacher_edit_course", course_id=course_id))

    @teacher_bp.post("/courses/<int:course_id>/modules/<int:module_id>/delete")
    @teacher_required
    def teacher_module_delete(course_id, module_id):
        course = _get_course_for_teacher(course_id)
        if not course:
            flash("Course not found.", "danger")
            return redirect(url_for("teacher.teacher_courses"))
        mod = CourseModule.query.filter_by(id=module_id, course_id=course.id).first()
        if mod:
            db.session.delete(mod)
            db.session.commit()
            flash("Module removed.", "info")
        return redirect(url_for("teacher.teacher_edit_course", course_id=course_id))

    @teacher_bp.get("/live-sessions")
    @teacher_required
    def teacher_live_sessions():
        course_ids = [c.id for c in Course.query.filter(_teacher_course_filter()).all()]
        lives = []
        if course_ids:
            lives = (
                LiveSession.query.filter(LiveSession.course_id.in_(course_ids))
                .order_by(LiveSession.scheduled_at.desc(), LiveSession.id.desc())
                .all()
            )
        courses = Course.query.filter(_teacher_course_filter()).order_by(Course.title).all()
        return render_template("lms/teacher/live_sessions.html", lives=lives, courses=courses)

    @teacher_bp.route("/courses/<int:course_id>/live-sessions/new", methods=["GET", "POST"])
    @teacher_required
    def teacher_live_session_new(course_id):
        course = _get_course_for_teacher(course_id)
        if not course:
            flash("Course not found.", "danger")
            return redirect(url_for("teacher.teacher_live_sessions"))
        modules = CourseModule.query.filter_by(course_id=course.id).order_by(CourseModule.sort_order).all()
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            url = request.form.get("meet_url", "").strip()
            if len(title) < 2 or not url:
                flash("Title and meeting link are required.", "danger")
                return redirect(url_for("teacher.teacher_live_session_new", course_id=course_id))
            sched_raw = request.form.get("scheduled_at", "").strip()
            sched = None
            if sched_raw:
                try:
                    sched = datetime.fromisoformat(sched_raw)
                except ValueError:
                    sched = None
            ls = LiveSession(
                course_id=course.id,
                teacher_id=current_user.id,
                module_id=int(request.form.get("module_id") or 0) or None,
                title=title,
                description=request.form.get("description", "").strip(),
                meet_url=url,
                scheduled_at=sched,
                status=request.form.get("status", "upcoming") or "upcoming",
                session_update=request.form.get("session_update", "").strip(),
            )
            db.session.add(ls)
            db.session.commit()
            flash("Live session created.", "success")
            return redirect(url_for("teacher.teacher_live_sessions"))
        return render_template("lms/teacher/live_session_form.html", course=course, modules=modules, session_row=None)

    @teacher_bp.route("/live-sessions/<int:session_id>/edit", methods=["GET", "POST"])
    @teacher_required
    def teacher_live_session_edit(session_id):
        row = LiveSession.query.get_or_404(session_id)
        course = _get_course_for_teacher(row.course_id)
        if not course:
            flash("Access denied.", "danger")
            return redirect(url_for("teacher.teacher_live_sessions"))
        modules = CourseModule.query.filter_by(course_id=course.id).order_by(CourseModule.sort_order).all()
        if request.method == "POST":
            row.title = request.form.get("title", row.title).strip()
            row.meet_url = request.form.get("meet_url", "").strip() or row.meet_url
            row.description = request.form.get("description", "").strip()
            row.session_update = request.form.get("session_update", "").strip()
            row.status = request.form.get("status", row.status) or row.status
            mid = int(request.form.get("module_id") or 0) or None
            row.module_id = mid
            sched_raw = request.form.get("scheduled_at", "").strip()
            if sched_raw:
                try:
                    row.scheduled_at = datetime.fromisoformat(sched_raw)
                except ValueError:
                    pass
            db.session.commit()
            flash("Live session updated.", "success")
            return redirect(url_for("teacher.teacher_live_sessions"))
        return render_template("lms/teacher/live_session_form.html", course=course, modules=modules, session_row=row)

    @teacher_bp.post("/live-sessions/<int:session_id>/delete")
    @teacher_required
    def teacher_live_session_delete(session_id):
        row = LiveSession.query.get_or_404(session_id)
        if not _get_course_for_teacher(row.course_id):
            flash("Access denied.", "danger")
            return redirect(url_for("teacher.teacher_live_sessions"))
        db.session.delete(row)
        db.session.commit()
        flash("Live session deleted.", "info")
        return redirect(url_for("teacher.teacher_live_sessions"))

    @teacher_bp.get("/recorded-sessions")
    @teacher_required
    def teacher_recorded_sessions():
        course_ids = [c.id for c in Course.query.filter(_teacher_course_filter()).all()]
        rows = []
        if course_ids:
            rows = (
                RecordedSession.query.filter(RecordedSession.course_id.in_(course_ids))
                .order_by(RecordedSession.sort_order, RecordedSession.id)
                .all()
            )
        courses = Course.query.filter(_teacher_course_filter()).order_by(Course.title).all()
        return render_template("lms/teacher/recorded_list.html", rows=rows, courses=courses)

    @teacher_bp.route("/courses/<int:course_id>/recorded/new", methods=["GET", "POST"])
    @teacher_required
    def teacher_recorded_new(course_id):
        course = _get_course_for_teacher(course_id)
        if not course:
            flash("Course not found.", "danger")
            return redirect(url_for("teacher.teacher_recorded_sessions"))
        modules = CourseModule.query.filter_by(course_id=course.id).order_by(CourseModule.sort_order).all()
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            if len(title) < 2:
                flash("Title is required.", "danger")
                return redirect(url_for("teacher.teacher_recorded_new", course_id=course_id))
            video_path = ""
            if "video" in request.files:
                video_path = save_upload(
                    request.files["video"],
                    "video",
                    ALLOWED_VIDEO,
                    100 * 1024 * 1024,
                    prefix="rec_",
                ) or ""
            if not video_path:
                flash("Video upload is required.", "danger")
                return redirect(url_for("teacher.teacher_recorded_new", course_id=course_id))
            extras = []
            files = request.files.getlist("resources")
            for f in files:
                p = save_upload(f, "res", ALLOWED_DOCS, 25 * 1024 * 1024, prefix="res_")
                if p:
                    extras.append(p)
            rec = RecordedSession(
                course_id=course.id,
                module_id=int(request.form.get("module_id") or 0) or None,
                title=title,
                description=request.form.get("description", "").strip(),
                video_path=video_path,
                resource_files=extras,
                is_visible=request.form.get("is_visible") == "on",
                sort_order=int(request.form.get("sort_order", 0) or 0),
            )
            db.session.add(rec)
            db.session.commit()
            flash("Recorded lecture saved.", "success")
            return redirect(url_for("teacher.teacher_recorded_sessions"))
        return render_template("lms/teacher/recorded_form.html", course=course, modules=modules, rec=None)

    @teacher_bp.route("/recorded-sessions/<int:rec_id>/edit", methods=["GET", "POST"])
    @teacher_required
    def teacher_recorded_edit(rec_id):
        rec = RecordedSession.query.get_or_404(rec_id)
        course = _get_course_for_teacher(rec.course_id)
        if not course:
            flash("Access denied.", "danger")
            return redirect(url_for("teacher.teacher_recorded_sessions"))
        modules = CourseModule.query.filter_by(course_id=course.id).order_by(CourseModule.sort_order).all()
        if request.method == "POST":
            rec.title = request.form.get("title", rec.title).strip()
            rec.description = request.form.get("description", "").strip()
            rec.is_visible = request.form.get("is_visible") == "on"
            rec.sort_order = int(request.form.get("sort_order", rec.sort_order) or 0)
            rec.module_id = int(request.form.get("module_id") or 0) or None
            if "video" in request.files and request.files["video"].filename:
                path = save_upload(
                    request.files["video"],
                    "video",
                    ALLOWED_VIDEO,
                    100 * 1024 * 1024,
                    prefix="rec_",
                )
                if path:
                    rec.video_path = path
            new_extras = list(rec.resource_files or [])
            files = request.files.getlist("resources")
            for f in files:
                p = save_upload(f, "res", ALLOWED_DOCS, 25 * 1024 * 1024, prefix="res_")
                if p:
                    new_extras.append(p)
            rec.resource_files = new_extras
            db.session.commit()
            flash("Recorded lecture updated.", "success")
            return redirect(url_for("teacher.teacher_recorded_sessions"))
        return render_template("lms/teacher/recorded_form.html", course=course, modules=modules, rec=rec)

    @teacher_bp.post("/recorded-sessions/<int:rec_id>/delete")
    @teacher_required
    def teacher_recorded_delete(rec_id):
        rec = RecordedSession.query.get_or_404(rec_id)
        if not _get_course_for_teacher(rec.course_id):
            flash("Access denied.", "danger")
            return redirect(url_for("teacher.teacher_recorded_sessions"))
        db.session.delete(rec)
        db.session.commit()
        flash("Recorded lecture removed.", "info")
        return redirect(url_for("teacher.teacher_recorded_sessions"))

    @teacher_bp.get("/notes")
    @teacher_required
    def teacher_notes():
        course_ids = [c.id for c in Course.query.filter(_teacher_course_filter()).all()]
        rows = []
        if course_ids:
            rows = (
                CourseNote.query.filter(CourseNote.course_id.in_(course_ids))
                .order_by(CourseNote.sort_order, CourseNote.id)
                .all()
            )
        courses = Course.query.filter(_teacher_course_filter()).order_by(Course.title).all()
        return render_template("lms/teacher/notes_list.html", rows=rows, courses=courses)

    @teacher_bp.route("/courses/<int:course_id>/notes/new", methods=["GET", "POST"])
    @teacher_required
    def teacher_note_new(course_id):
        course = _get_course_for_teacher(course_id)
        if not course:
            flash("Course not found.", "danger")
            return redirect(url_for("teacher.teacher_notes"))
        modules = CourseModule.query.filter_by(course_id=course.id).order_by(CourseModule.sort_order).all()
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            if len(title) < 2:
                flash("Title is required.", "danger")
                return redirect(url_for("teacher.teacher_note_new", course_id=course_id))
            if "file" not in request.files or not request.files["file"].filename:
                flash("File upload is required.", "danger")
                return redirect(url_for("teacher.teacher_note_new", course_id=course_id))
            path = save_upload(request.files["file"], "note", ALLOWED_DOCS, 25 * 1024 * 1024, prefix="note_")
            if not path:
                flash("Unsupported file or file too large.", "danger")
                return redirect(url_for("teacher.teacher_note_new", course_id=course_id))
            note = CourseNote(
                course_id=course.id,
                module_id=int(request.form.get("module_id") or 0) or None,
                title=title,
                description=request.form.get("description", "").strip(),
                file_path=path,
                is_visible=request.form.get("is_visible") == "on",
                sort_order=int(request.form.get("sort_order", 0) or 0),
            )
            db.session.add(note)
            db.session.commit()
            flash("Note uploaded.", "success")
            return redirect(url_for("teacher.teacher_notes"))
        return render_template("lms/teacher/note_form.html", course=course, modules=modules, note=None)

    @teacher_bp.route("/notes/<int:note_id>/edit", methods=["GET", "POST"])
    @teacher_required
    def teacher_note_edit(note_id):
        note = CourseNote.query.get_or_404(note_id)
        course = _get_course_for_teacher(note.course_id)
        if not course:
            flash("Access denied.", "danger")
            return redirect(url_for("teacher.teacher_notes"))
        modules = CourseModule.query.filter_by(course_id=course.id).order_by(CourseModule.sort_order).all()
        if request.method == "POST":
            note.title = request.form.get("title", note.title).strip()
            note.description = request.form.get("description", "").strip()
            note.is_visible = request.form.get("is_visible") == "on"
            note.sort_order = int(request.form.get("sort_order", note.sort_order) or 0)
            note.module_id = int(request.form.get("module_id") or 0) or None
            if "file" in request.files and request.files["file"].filename:
                path = save_upload(request.files["file"], "note", ALLOWED_DOCS, 25 * 1024 * 1024, prefix="note_")
                if path:
                    note.file_path = path
            db.session.commit()
            flash("Note updated.", "success")
            return redirect(url_for("teacher.teacher_notes"))
        return render_template("lms/teacher/note_form.html", course=course, modules=modules, note=note)

    @teacher_bp.post("/notes/<int:note_id>/delete")
    @teacher_required
    def teacher_note_delete(note_id):
        note = CourseNote.query.get_or_404(note_id)
        if not _get_course_for_teacher(note.course_id):
            flash("Access denied.", "danger")
            return redirect(url_for("teacher.teacher_notes"))
        db.session.delete(note)
        db.session.commit()
        flash("Note deleted.", "info")
        return redirect(url_for("teacher.teacher_notes"))

    @teacher_bp.get("/quizzes")
    @teacher_required
    def teacher_quizzes():
        course_ids = [c.id for c in Course.query.filter(_teacher_course_filter()).all()]
        rows = []
        if course_ids:
            rows = (
                LmsQuiz.query.filter(LmsQuiz.course_id.in_(course_ids))
                .order_by(LmsQuiz.sort_order, LmsQuiz.id)
                .all()
            )
        courses = Course.query.filter(_teacher_course_filter()).order_by(Course.title).all()
        return render_template("lms/teacher/quiz_list.html", rows=rows, courses=courses)

    @teacher_bp.route("/courses/<int:course_id>/quizzes/new", methods=["GET", "POST"])
    @teacher_required
    def teacher_quiz_new(course_id):
        course = _get_course_for_teacher(course_id)
        if not course:
            flash("Course not found.", "danger")
            return redirect(url_for("teacher.teacher_quizzes"))
        modules = CourseModule.query.filter_by(course_id=course.id).order_by(CourseModule.sort_order).all()
        if request.method == "POST":
            title = request.form.get("title", "Quiz").strip() or "Quiz"
            raw = request.form.get("questions_json", "").strip()
            try:
                questions = json.loads(raw) if raw else []
            except json.JSONDecodeError:
                questions = []
            if not questions:
                flash("Add at least one MCQ in JSON format.", "danger")
                return redirect(url_for("teacher.teacher_quiz_new", course_id=course_id))
            quiz = LmsQuiz(
                course_id=course.id,
                module_id=int(request.form.get("module_id") or 0) or None,
                title=title,
                time_limit_seconds=int(request.form.get("time_limit_seconds", 0) or 0),
                questions_json=questions,
                pass_percent=int(request.form.get("pass_percent", 60) or 60),
                is_published=request.form.get("is_published") == "on",
                sort_order=int(request.form.get("sort_order", 0) or 0),
            )
            db.session.add(quiz)
            db.session.commit()
            flash("Quiz created.", "success")
            return redirect(url_for("teacher.teacher_quizzes"))
        sample = [
            {
                "question": "Sample question?",
                "options": ["A", "B", "C", "D"],
                "correctAnswer": "A",
            }
        ]
        return render_template(
            "lms/teacher/quiz_form.html",
            course=course,
            modules=modules,
            quiz=None,
            sample_json=json.dumps(sample, indent=2),
        )

    @teacher_bp.route("/quizzes/<int:quiz_id>/edit", methods=["GET", "POST"])
    @teacher_required
    def teacher_quiz_edit(quiz_id):
        quiz = LmsQuiz.query.get_or_404(quiz_id)
        course = _get_course_for_teacher(quiz.course_id)
        if not course:
            flash("Access denied.", "danger")
            return redirect(url_for("teacher.teacher_quizzes"))
        modules = CourseModule.query.filter_by(course_id=course.id).order_by(CourseModule.sort_order).all()
        if request.method == "POST":
            quiz.title = request.form.get("title", quiz.title).strip() or quiz.title
            raw = request.form.get("questions_json", "").strip()
            try:
                questions = json.loads(raw) if raw else quiz.questions_json
            except json.JSONDecodeError:
                questions = quiz.questions_json
            quiz.questions_json = questions
            quiz.time_limit_seconds = int(request.form.get("time_limit_seconds", quiz.time_limit_seconds) or 0)
            quiz.pass_percent = int(request.form.get("pass_percent", quiz.pass_percent) or 60)
            quiz.is_published = request.form.get("is_published") == "on"
            quiz.sort_order = int(request.form.get("sort_order", quiz.sort_order) or 0)
            quiz.module_id = int(request.form.get("module_id") or 0) or None
            db.session.commit()
            flash("Quiz updated.", "success")
            return redirect(url_for("teacher.teacher_quizzes"))
        sample_json = json.dumps(quiz.questions_json or [], indent=2)
        return render_template(
            "lms/teacher/quiz_form.html",
            course=course,
            modules=modules,
            quiz=quiz,
            sample_json=sample_json,
        )

    @teacher_bp.post("/quizzes/<int:quiz_id>/delete")
    @teacher_required
    def teacher_quiz_delete(quiz_id):
        quiz = LmsQuiz.query.get_or_404(quiz_id)
        if not _get_course_for_teacher(quiz.course_id):
            flash("Access denied.", "danger")
            return redirect(url_for("teacher.teacher_quizzes"))
        db.session.delete(quiz)
        db.session.commit()
        flash("Quiz deleted.", "info")
        return redirect(url_for("teacher.teacher_quizzes"))

    @teacher_bp.get("/courses/<int:course_id>/students")
    @teacher_required
    def teacher_course_students(course_id):
        course = _get_course_for_teacher(course_id)
        if not course:
            flash("Course not found.", "danger")
            return redirect(url_for("teacher.teacher_courses"))
        enrolls = Enrollment.query.filter_by(course_id=course.id).order_by(Enrollment.created_at.desc()).all()
        return render_template("lms/teacher/course_students.html", course=course, enrolls=enrolls)
