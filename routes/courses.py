import os
import re
from datetime import datetime
from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, Response, session, url_for
from flask_login import current_user
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError

from models import db
from models.course import Certificate, Course, CoursePayment, Enrollment
from models.course_cert_highlight import CourseCertHighlight
from models.course_learning_path import CourseLearningPath
from models.course_showcase_project import CourseShowcaseProject
from models.courses_page_content import CoursesPageContent
from models.event import Event
from models.lms import (
    LectureProgress,
    LiveSession,
    LiveSessionAttendance,
    LmsQuiz,
    QuizAttempt,
    RecordedSession,
)
from utils.decorators import login_required
from utils.certificates import generate_certificate_pdf
from utils.lms_helpers import build_lms_context
from utils.lms_progress import recompute_enrollment_progress, try_mark_quiz_passed_from_lms
from utils.notifications import notify_user
from utils.payments import create_razorpay_order, verify_razorpay_signature
from utils.security_helpers import rate_limit

courses_bp = Blueprint("courses", __name__)


def _maybe_issue_certificate(enrollment, course):
    if enrollment.quiz_passed and enrollment.progress_pct < 100:
        enrollment.progress_pct = 100
    if not enrollment.quiz_passed:
        return
    existing_cert = Certificate.query.filter_by(user_id=current_user.id, course_id=course.id).first()
    if existing_cert:
        return
    uid, pdf_path = generate_certificate_pdf(current_user.full_name, course.title)
    db.session.add(Certificate(certificate_uid=uid, user_id=current_user.id, course_id=course.id, pdf_path=pdf_path))
    notify_user(current_user.id, f"Certificate issued for “{course.title}”. Verify ID: {uid[:8]}…")


def _courses_copy(key: str, default: str = "") -> str:
    try:
        row = CoursesPageContent.query.filter_by(key=key).first()
        return (row.value if row and row.value is not None else default) or default
    except Exception:
        return default


def _parse_int(val, default=None):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


@courses_bp.get("/")
def list_courses():
    """Public course catalog; purchase and learning still require login."""
    q = Course.query
    if not current_user.is_authenticated or getattr(current_user, "role", None) == "student":
        q = q.filter(Course.is_published.is_(True))

    search = (request.args.get("q") or "").strip()
    cat = (request.args.get("category") or "").strip()
    level = (request.args.get("level") or "").strip()
    duration = (request.args.get("duration") or "").strip()
    price_band = (request.args.get("price") or "").strip()

    if search:
        like = f"%{search}%"
        q = q.filter(or_(Course.title.ilike(like), Course.description.ilike(like), Course.category.ilike(like)))
    if cat:
        q = q.filter(Course.category.ilike(f"%{cat}%"))
    if level:
        q = q.filter(Course.level.ilike(f"%{level}%"))
    if duration:
        q = q.filter(Course.duration.ilike(f"%{duration}%"))
    if price_band == "free":
        q = q.filter(Course.price_inr == 0)
    elif price_band == "under1k":
        q = q.filter(Course.price_inr > 0, Course.price_inr < 1000)
    elif price_band == "1k5k":
        q = q.filter(Course.price_inr >= 1000, Course.price_inr <= 5000)
    elif price_band == "5kplus":
        q = q.filter(Course.price_inr > 5000)

    courses = (
        q.order_by(Course.is_featured.desc(), Course.catalog_display_order.asc(), Course.created_at.desc()).all()
    )

    enrollment_by_course = {}
    if current_user.is_authenticated:
        for e in Enrollment.query.filter_by(user_id=current_user.id).all():
            enrollment_by_course[e.course_id] = e

    paid_counts_rows = (
        db.session.query(Enrollment.course_id, func.count(Enrollment.id))
        .filter(Enrollment.is_paid.is_(True))
        .group_by(Enrollment.course_id)
        .all()
    )
    paid_enrollment_by_course = {cid: cnt for cid, cnt in paid_counts_rows}

    learning_paths = []
    showcase_projects = []
    cert_highlights = []
    events = []
    try:
        learning_paths = (
            CourseLearningPath.query.filter_by(is_active=True)
            .order_by(CourseLearningPath.display_order.asc(), CourseLearningPath.id.asc())
            .limit(12)
            .all()
        )
        showcase_projects = (
            CourseShowcaseProject.query.filter_by(is_active=True)
            .order_by(CourseShowcaseProject.display_order.asc(), CourseShowcaseProject.id.desc())
            .limit(12)
            .all()
        )
        cert_highlights = (
            CourseCertHighlight.query.filter_by(is_active=True)
            .order_by(CourseCertHighlight.display_order.asc(), CourseCertHighlight.id.desc())
            .limit(12)
            .all()
        )
        events = (
            Event.query.filter_by(is_active=True)
            .order_by(Event.display_order.asc(), Event.id.desc())
            .limit(8)
            .all()
        )
    except Exception:
        pass

    categories = (
        db.session.query(Course.category)
        .filter(Course.is_published.is_(True), Course.category != "", Course.category.isnot(None))
        .distinct()
        .order_by(Course.category.asc())
        .all()
    )
    category_list = sorted({c[0].strip() for c in categories if c and c[0]})

    page_copy = {
        "hero_heading": _courses_copy(
            "hero_heading",
            "Master AI, Robotics & Future Technologies Through Practical Learning",
        ),
        "hero_subtitle": _courses_copy(
            "hero_subtitle",
            "Industry-aligned courses with real projects, expert mentors, and verified certificates.",
        ),
        "meta_description": _courses_copy(
            "meta_description",
            "Browse AI courses, robotics training, IoT, embedded systems, Arduino, ESP32, and STEM programs "
            "with hands-on projects and verified certificates at Skill Orbit India.",
        ),
        "meta_keywords": _courses_copy(
            "meta_keywords",
            "AI courses, robotics training, IoT courses, embedded systems, Arduino learning, Python for AI, "
            "STEM education, AI internship, Skill Orbit India",
        ),
    }

    return render_template(
        "courses/listing.html",
        courses=courses,
        enrollment_by_course=enrollment_by_course,
        paid_enrollment_by_course=paid_enrollment_by_course,
        learning_paths=learning_paths,
        showcase_projects=showcase_projects,
        cert_highlights=cert_highlights,
        events=events,
        category_list=category_list,
        page_copy=page_copy,
        filter_q=search,
        filter_category=cat,
        filter_level=level,
        filter_duration=duration,
        filter_price=price_band,
    )


@courses_bp.post("/enroll/<int:course_id>")
@login_required
def enroll(course_id):
    return redirect(url_for("courses.buy_course", course_id=course_id))


@courses_bp.get("/buy/<int:course_id>")
@login_required
def buy_course(course_id):
    course = Course.query.get_or_404(course_id)
    if getattr(course, "is_published", None) is False:
        flash("This course is not available.", "warning")
        return redirect(url_for("courses.list_courses"))
    enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=course.id).first()
    if enrollment and enrollment.is_paid:
        return redirect(url_for("courses.learn", course_id=course.id))
    if not enrollment:
        enrollment = Enrollment(user_id=current_user.id, course_id=course.id, progress_pct=0, is_paid=False)
        db.session.add(enrollment)
        db.session.flush()
    if not enrollment.razorpay_order_id:
        rp_order = create_razorpay_order(course.price_inr, f"course_{course.id}_user_{current_user.id}")
        if not rp_order:
            flash("Payment gateway is not configured. Please contact support.", "danger")
            db.session.rollback()
            return redirect(url_for("courses.list_courses"))
        enrollment.razorpay_order_id = rp_order.get("id", "")
        db.session.add(
            CoursePayment(
                user_id=current_user.id,
                course_id=course.id,
                amount_inr=course.price_inr,
                razorpay_order_id=enrollment.razorpay_order_id,
                status="created",
            )
        )
        db.session.commit()
    return render_template(
        "courses/payment.html",
        course=course,
        enrollment=enrollment,
        razorpay_key_id=current_app.config.get("RAZORPAY_KEY_ID", ""),
    )


@courses_bp.post("/verify-payment/<int:course_id>")
@login_required
@rate_limit(limit=5, period=60)
def verify_course_payment(course_id):
    course = Course.query.get_or_404(course_id)
    enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=course.id).first()
    if not enrollment or not enrollment.razorpay_order_id:
        flash("Payment session not found. Please try buying the course again.", "warning")
        return redirect(url_for("courses.buy_course", course_id=course.id))
    rz_order_id = request.form.get("razorpay_order_id", "").strip()
    rz_payment_id = request.form.get("razorpay_payment_id", "").strip()
    rz_signature = request.form.get("razorpay_signature", "").strip()
    if not rz_order_id or not rz_payment_id or not rz_signature:
        flash("Missing payment verification details.", "danger")
        return redirect(url_for("courses.buy_course", course_id=course.id))
    if rz_order_id != enrollment.razorpay_order_id:
        flash("Payment order mismatch.", "danger")
        return redirect(url_for("courses.buy_course", course_id=course.id))
    is_valid = verify_razorpay_signature(rz_order_id, rz_payment_id, rz_signature)
    payment_row = CoursePayment.query.filter_by(
        user_id=current_user.id, course_id=course.id, razorpay_order_id=rz_order_id
    ).first()
    try:
        if not is_valid:
            if payment_row:
                payment_row.status = "failed_signature"
            db.session.commit()
            flash("Payment verification failed. Please contact support if amount was debited.", "danger")
            return redirect(url_for("courses.buy_course", course_id=course.id))
        enrollment.is_paid = True
        enrollment.razorpay_payment_id = rz_payment_id
        if payment_row:
            payment_row.status = "captured"
            payment_row.razorpay_payment_id = rz_payment_id
            payment_row.razorpay_signature = rz_signature
        current_user.points += 10
        current_user.update_badge()
        notify_user(current_user.id, f"Payment successful for “{course.title}”. Course unlocked.")
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not finalize payment. Please try again.", "danger")
        return redirect(url_for("courses.buy_course", course_id=course.id))
    flash("Payment successful. You can now access the course.", "success")
    return redirect(url_for("courses.learn", course_id=course.id))


@courses_bp.route("/learn/<int:course_id>", methods=["GET", "POST"])
@login_required
def learn(course_id):
    course = Course.query.get_or_404(course_id)
    enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=course.id).first()
    if not enrollment or not enrollment.is_paid:
        flash("Please purchase this course to access lessons.", "warning")
        return redirect(url_for("courses.buy_course", course_id=course.id))

    if request.method == "POST":
        action = (request.form.get("action") or "").strip()
        try:
            if action == "progress":
                enrollment.progress_pct = min(100, (enrollment.progress_pct or 0) + 20)
                db.session.commit()
                flash("Progress updated.", "success")
            elif action == "join_live":
                ls_id = int(request.form.get("live_session_id") or 0)
                ls = LiveSession.query.get_or_404(ls_id)
                if ls.course_id != course.id:
                    flash("Invalid session.", "danger")
                else:
                    existing = LiveSessionAttendance.query.filter_by(
                        user_id=current_user.id, live_session_id=ls.id
                    ).first()
                    if not existing:
                        db.session.add(LiveSessionAttendance(user_id=current_user.id, live_session_id=ls.id))
                    db.session.commit()
                    flash("Attendance recorded.", "success")
            elif action == "mark_lecture":
                rid = int(request.form.get("recorded_session_id") or 0)
                rec = RecordedSession.query.get_or_404(rid)
                if rec.course_id != course.id:
                    flash("Invalid lecture.", "danger")
                else:
                    row = LectureProgress.query.filter_by(
                        user_id=current_user.id, recorded_session_id=rec.id
                    ).first()
                    if not row:
                        db.session.add(
                            LectureProgress(
                                user_id=current_user.id,
                                recorded_session_id=rec.id,
                                progress_pct=100,
                                completed=True,
                            )
                        )
                    else:
                        row.progress_pct = max(row.progress_pct or 0, 100)
                        row.completed = True
                    recompute_enrollment_progress(enrollment)
                    db.session.commit()
                    flash("Marked as watched.", "success")
            elif action == "quiz_lms":
                quiz_id = int(request.form.get("quiz_id") or 0)
                quiz = LmsQuiz.query.get_or_404(quiz_id)
                if quiz.course_id != course.id:
                    flash("Invalid quiz.", "danger")
                else:
                    now_ts = datetime.utcnow().timestamp()
                    session_key = f"quiz_start_time_{quiz.id}"
                    start_ts = session.pop(session_key, None)
                    
                    if start_ts is None:
                        elapsed = int(request.form.get("duration_seconds", 0) or 10)
                    else:
                        elapsed = int(now_ts - start_ts)
                        
                    # 1. Reject suspiciously fast submissions (suspicious timing manipulation)
                    questions = quiz.questions_json or []
                    if len(questions) > 1 and elapsed < 2:
                        flash("Quiz submission rejected due to suspected rapid timing abuse.", "danger")
                        return redirect(url_for("courses.learn", course_id=course.id))
                        
                    # 2. Enforce time limits strictly on the server-side with a 15-second grace window for latency
                    if quiz.time_limit_seconds > 0 and elapsed > (quiz.time_limit_seconds + 15):
                        db.session.add(
                            QuizAttempt(
                                user_id=current_user.id,
                                quiz_id=quiz.id,
                                score=0,
                                max_score=100,
                                passed=False,
                                duration_seconds=elapsed,
                                details_json={"percent": 0, "timeout": True},
                            )
                        )
                        db.session.commit()
                        flash("Quiz failed: time limit exceeded.", "danger")
                        return redirect(url_for("courses.learn", course_id=course.id))

                    score = 0
                    for i, q in enumerate(questions):
                        sel = (request.form.get(f"lq_{quiz.id}_{i}") or "").strip()
                        correct = (q.get("correctAnswer") or "").strip()
                        if sel and correct and sel.lower() == correct.lower():
                            score += 1
                    max_score = max(len(questions), 1)
                    score_percent = int(round(100 * score / max_score))
                    passed = score_percent >= (quiz.pass_percent or 60)
                    db.session.add(
                        QuizAttempt(
                            user_id=current_user.id,
                            quiz_id=quiz.id,
                            score=score_percent,
                            max_score=100,
                            passed=passed,
                            duration_seconds=elapsed,
                            details_json={"percent": score_percent},
                        )
                    )
                    if passed:
                        current_user.points += 5
                        current_user.update_badge()
                    if try_mark_quiz_passed_from_lms(enrollment):
                        enrollment.progress_pct = max(enrollment.progress_pct or 0, 100)
                        _maybe_issue_certificate(enrollment, course)
                        flash("Course quizzes complete. Certificate issued if eligible.", "success")
                    elif passed:
                        flash(f"Score: {score_percent}% — passed.", "success")
                    else:
                        flash(f"Score: {score_percent}% — review the material and try again.", "warning")
                    db.session.commit()
            elif action == "quiz_new":
                idx = int(request.form.get("quiz_index", "0") or 0)
                correct = (request.form.get("correct_answer") or "").strip()
                answer = (request.form.get("answer") or "").strip()
                items = course.quiz or []
                if 0 <= idx < len(items) and correct and answer.lower() == correct.lower():
                    enrollment.quiz_passed = True
                    enrollment.progress_pct = max(enrollment.progress_pct or 0, 100)
                    _maybe_issue_certificate(enrollment, course)
                    db.session.commit()
                    flash("Correct! Quiz cleared.", "success")
                else:
                    flash("Not quite — try another option.", "warning")
                    db.session.commit()
            elif action == "quiz":
                answer = request.form.get("quiz_answer", "").strip().lower()
                correct = (course.quiz_answer or "").strip().lower()
                if answer and correct and answer == correct:
                    enrollment.quiz_passed = True
                    enrollment.progress_pct = max(enrollment.progress_pct or 0, 100)
                    _maybe_issue_certificate(enrollment, course)
                    db.session.commit()
                    flash("Correct! Great job.", "success")
                else:
                    flash("Incorrect answer. Try again.", "danger")
            else:
                flash("Unknown action.", "warning")
        except (ValueError, SQLAlchemyError) as exc:
            db.session.rollback()
            flash(str(exc) if isinstance(exc, ValueError) else "Could not save. Please try again.", "danger")
        return redirect(url_for("courses.learn", course_id=course.id))

    lms = build_lms_context(course, current_user.id)
    for q in lms.get("quizzes", []):
        session_key = f"quiz_start_time_{q['id']}"
        if session_key not in session:
            session[session_key] = datetime.utcnow().timestamp()
    return render_template("courses/learn_lms.html", course=course, enrollment=enrollment, lms=lms)


def _stream_video_file(path_to_file):
    range_header = request.headers.get('Range', None)
    if not range_header:
        def generator():
            with open(path_to_file, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    yield chunk
        return Response(generator(), mimetype='video/mp4')
    
    size = os.path.getsize(path_to_file)
    byte1, byte2 = 0, None
    
    match = re.search(r'bytes=(\d+)-(\d*)', range_header)
    if match:
        groups = match.groups()
        if groups[0]:
            byte1 = int(groups[0])
        if groups[1]:
            byte2 = int(groups[1])
            
    if byte2 is None:
        byte2 = size - 1
        
    length = byte2 - byte1 + 1
    
    def generator():
        with open(path_to_file, 'rb') as f:
            f.seek(byte1)
            remaining = length
            while remaining > 0:
                to_read = min(8192, remaining)
                chunk = f.read(to_read)
                if not chunk:
                    break
                yield chunk
                remaining -= len(chunk)
                
    rv = Response(generator(), 206, mimetype='video/mp4', direct_passthrough=True)
    rv.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{size}')
    rv.headers.add('Accept-Ranges', 'bytes')
    rv.headers.add('Content-Length', str(length))
    return rv


@courses_bp.route("/stream/<int:lecture_id>")
@login_required
def stream_lecture(lecture_id):
    lecture = RecordedSession.query.get_or_404(lecture_id)
    enrollment = Enrollment.query.filter_by(user_id=current_user.id, course_id=lecture.course_id).first()
    
    is_authorized = (current_user.role in ['admin', 'teacher']) or (enrollment and enrollment.is_paid)
    if not is_authorized:
        return jsonify({"error": "Unauthorized. Please enroll in this course first."}), 403
        
    video_path = lecture.video_path
    if not video_path:
        return jsonify({"error": "Video file not found."}), 404
        
    if video_path.startswith("http://") or video_path.startswith("https://"):
        return redirect(video_path)
        
    abs_path = video_path
    if not os.path.isabs(abs_path):
        abs_path = os.path.join(current_app.root_path, video_path.lstrip("/\\"))
        
    if not os.path.exists(abs_path):
        return jsonify({"error": "Lecture video file not found on disk."}), 404
        
    return _stream_video_file(abs_path)

