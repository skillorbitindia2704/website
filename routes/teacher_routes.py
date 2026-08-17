import json
import os
import time
from datetime import date, datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from models import db
from models.course import Course
from models.hr import AttendanceRecord, LeaveRequest, AttendanceCorrectionRequest
from models.payroll import PayrollRun
from sqlalchemy import or_
from utils.lms_uploads import ALLOWED_IMAGE, save_upload
from utils.role_auth import teacher_required

teacher_bp = Blueprint("teacher", __name__, url_prefix="/teacher")

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', 'videos')
ALLOWED_EXTENSIONS = {'mp4', 'webm', 'mov', 'avi', 'mkv', 'flv', 'm4v'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(file_storage):
    from utils.security_helpers import validate_file_safety
    return validate_file_safety(file_storage, ALLOWED_EXTENSIONS)


def save_uploaded_files(files):
    """Save uploaded files and return list of file paths."""
    saved_files = []
    for file in files:
        if file and file.filename and allowed_file(file):
            # Check file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            if file_size > MAX_FILE_SIZE:
                continue
            file.seek(0)
            
            # Save file with secure name
            filename = secure_filename(file.filename)
            # Add timestamp to make unique
            filename = f"{int(time.time())}_{filename}"
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)
            # Store relative path for serving
            saved_files.append(f"/static/uploads/videos/{filename}")
    return saved_files


@teacher_bp.get("/dashboard")
@teacher_required
def dashboard():
    uid = current_user.id
    employee = current_user.employee_profile
    courses = (
        Course.query.filter(or_(Course.teacher_id == uid, Course.teacher_id.is_(None)))
        .order_by(Course.created_at.desc())
        .all()
    )
    attendance_count = 0
    payroll_count = 0
    leave_count = 0
    if employee:
        attendance_count = AttendanceRecord.query.filter_by(employee_id=employee.id).count()
        payroll_count = PayrollRun.query.filter_by(employee_id=employee.id).count()
        leave_count = LeaveRequest.query.filter_by(employee_id=employee.id).count()
    return render_template(
        "teacher/dashboard.html",
        courses=courses,
        employee=employee,
        attendance_count=attendance_count,
        payroll_count=payroll_count,
        leave_count=leave_count,
    )


def _working_hours_text(record):
    if not record or record.check_in is None or record.check_out is None:
        return "—"
    diff = record.check_out - record.check_in
    total_minutes = int(diff.total_seconds() // 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m"


@teacher_bp.get("/hr")
@teacher_required
def teacher_hr_dashboard():
    employee = current_user.employee_profile
    if not employee:
        flash("No employee profile is linked to your account yet. Contact admin.", "warning")
        return redirect(url_for("teacher.dashboard"))

    attendance_count = AttendanceRecord.query.filter_by(employee_id=employee.id).count()
    payroll_count = PayrollRun.query.filter_by(employee_id=employee.id).count()
    leave_count = LeaveRequest.query.filter_by(employee_id=employee.id).count()
    today = date.today()
    today_record = AttendanceRecord.query.filter_by(employee_id=employee.id, attendance_date=today).first()
    today_working_hours = _working_hours_text(today_record)
    recent_attendance = (
        AttendanceRecord.query.filter_by(employee_id=employee.id)
        .order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.created_at.desc())
        .limit(5)
        .all()
    )
    recent_payroll = (
        PayrollRun.query.filter_by(employee_id=employee.id)
        .order_by(PayrollRun.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template(
        "teacher/hr_dashboard.html",
        employee=employee,
        attendance_count=attendance_count,
        payroll_count=payroll_count,
        leave_count=leave_count,
        recent_attendance=recent_attendance,
        recent_payroll=recent_payroll,
        today=today,
        today_record=today_record,
        today_working_hours=today_working_hours,
    )


@teacher_bp.get("/hr/attendance")
@teacher_required
def teacher_hr_attendance():
    employee = current_user.employee_profile
    if not employee:
        flash("No employee profile is linked to your account yet. Contact admin.", "warning")
        return redirect(url_for("teacher.dashboard"))

    attendance = (
        AttendanceRecord.query.filter_by(employee_id=employee.id)
        .order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.created_at.desc())
        .all()
    )
    today = date.today()
    today_record = AttendanceRecord.query.filter_by(employee_id=employee.id, attendance_date=today).first()
    return render_template(
        "teacher/hr_attendance.html",
        employee=employee,
        attendance=attendance,
        today_record=today_record,
        today=today,
    )


@teacher_bp.post("/hr/attendance/check-in")
@teacher_required
def teacher_attendance_check_in():
    employee = current_user.employee_profile
    if not employee:
        flash("No employee profile is linked to your account yet. Contact admin.", "warning")
        return redirect(url_for("teacher.dashboard"))

    today = date.today()
    record = AttendanceRecord.query.filter_by(employee_id=employee.id, attendance_date=today).first()
    if record and record.check_in is not None:
        flash("You have already checked in for today.", "warning")
        return redirect(url_for("teacher.teacher_hr_attendance"))

    now = datetime.utcnow()
    if not record:
        record = AttendanceRecord(employee_id=employee.id, attendance_date=today)
        db.session.add(record)

    record.check_in = now
    record.status = "Present"
    record.notes = "Checked in by employee"
    db.session.commit()
    flash("Check-in recorded successfully.", "success")
    return redirect(url_for("teacher.teacher_hr_attendance"))


@teacher_bp.post("/hr/attendance/check-out")
@teacher_required
def teacher_attendance_check_out():
    employee = current_user.employee_profile
    if not employee:
        flash("No employee profile is linked to your account yet. Contact admin.", "warning")
        return redirect(url_for("teacher.dashboard"))

    today = date.today()
    record = AttendanceRecord.query.filter_by(employee_id=employee.id, attendance_date=today).first()
    if not record or record.check_in is None:
        flash("You must check in before checking out.", "warning")
        return redirect(url_for("teacher.teacher_hr_attendance"))
    if record.check_out is not None:
        flash("You have already checked out for today.", "warning")
        return redirect(url_for("teacher.teacher_hr_attendance"))

    now = datetime.utcnow()
    record.check_out = now
    if record.check_in and record.check_out < record.check_in:
        record.check_out = record.check_in
    record.status = "Present"
    db.session.commit()
    flash("Check-out recorded successfully.", "success")
    return redirect(url_for("teacher.teacher_hr_attendance"))


@teacher_bp.get("/hr/leave-requests")
@teacher_required
def teacher_leave_requests():
    employee = current_user.employee_profile
    if not employee:
        flash("No employee profile is linked to your account yet. Contact admin.", "warning")
        return redirect(url_for("teacher.dashboard"))

    leave_requests = (
        LeaveRequest.query.filter_by(employee_id=employee.id)
        .order_by(LeaveRequest.created_at.desc())
        .all()
    )
    return render_template(
        "teacher/hr_leave_requests.html",
        employee=employee,
        leave_requests=leave_requests,
        today=date.today(),
    )


@teacher_bp.route("/hr/leave-requests", methods=["POST"])
@teacher_required
def teacher_apply_leave():
    employee = current_user.employee_profile
    if not employee:
        flash("No employee profile is linked to your account yet. Contact admin.", "warning")
        return redirect(url_for("teacher.dashboard"))

    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    leave_type = request.form.get("leave_type", "Paid Leave")
    reason = request.form.get("reason", "").strip()

    if not start_date or not end_date or not reason:
        flash("Start date, end date, and reason are required.", "danger")
        return redirect(url_for("teacher.teacher_leave_requests"))

    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid leave dates provided.", "danger")
        return redirect(url_for("teacher.teacher_leave_requests"))

    if end_date_obj < start_date_obj:
        flash("End date cannot be earlier than start date.", "danger")
        return redirect(url_for("teacher.teacher_leave_requests"))

    leave_request = LeaveRequest(
        employee_id=employee.id,
        start_date=start_date_obj,
        end_date=end_date_obj,
        leave_type=leave_type,
        reason=reason,
    )
    db.session.add(leave_request)
    db.session.commit()
    flash("Leave request submitted successfully.", "success")
    return redirect(url_for("teacher.teacher_leave_requests"))


@teacher_bp.route("/hr/attendance/correction", methods=["GET", "POST"])
@teacher_required
def teacher_attendance_correction():
    employee = current_user.employee_profile
    if not employee:
        flash("No employee profile is linked to your account yet. Contact admin.", "warning")
        return redirect(url_for("teacher.dashboard"))

    if request.method == "POST":
        attendance_id = request.form.get("attendance_id")
        requested_check_in = request.form.get("requested_check_in")
        requested_check_out = request.form.get("requested_check_out")
        reason = request.form.get("reason", "").strip()

        if not attendance_id or not reason:
            flash("Attendance record and reason are required.", "danger")
            return redirect(url_for("teacher.teacher_attendance_correction"))

        try:
            attendance_id_val = int(attendance_id)
        except (TypeError, ValueError):
            flash("Invalid attendance record selected.", "danger")
            return redirect(url_for("teacher.teacher_attendance_correction"))

        record = AttendanceRecord.query.filter_by(id=attendance_id_val, employee_id=employee.id).first()
        if not record:
            flash("Attendance record not found.", "danger")
            return redirect(url_for("teacher.teacher_attendance_correction"))

        requested_check_in_dt = None
        requested_check_out_dt = None
        try:
            if requested_check_in:
                requested_check_in_dt = datetime.fromisoformat(requested_check_in)
            if requested_check_out:
                requested_check_out_dt = datetime.fromisoformat(requested_check_out)
        except ValueError:
            flash("Invalid date/time format for correction.", "danger")
            return redirect(url_for("teacher.teacher_attendance_correction"))

        correction_request = AttendanceCorrectionRequest(
            employee_id=employee.id,
            attendance_id=record.id,
            requested_check_in=requested_check_in_dt,
            requested_check_out=requested_check_out_dt,
            reason=reason,
            original_check_in=record.check_in,
            original_check_out=record.check_out,
        )
        db.session.add(correction_request)
        db.session.commit()
        flash("Attendance correction request submitted successfully.", "success")
        return redirect(url_for("teacher.teacher_attendance_correction"))

    attendance = (
        AttendanceRecord.query.filter_by(employee_id=employee.id)
        .order_by(AttendanceRecord.attendance_date.desc(), AttendanceRecord.created_at.desc())
        .all()
    )
    correction_requests = (
        AttendanceCorrectionRequest.query.filter_by(employee_id=employee.id)
        .order_by(AttendanceCorrectionRequest.submitted_at.desc())
        .all()
    )
    return render_template(
        "teacher/hr_attendance_correction.html",
        employee=employee,
        attendance=attendance,
        correction_requests=correction_requests,
    )


@teacher_bp.get("/hr/payroll")
@teacher_required
def teacher_hr_payroll():
    employee = current_user.employee_profile
    if not employee:
        flash("No employee profile is linked to your account yet. Contact admin.", "warning")
        return redirect(url_for("teacher.dashboard"))

    payroll_runs = (
        PayrollRun.query.filter_by(employee_id=employee.id)
        .order_by(PayrollRun.created_at.desc())
        .all()
    )
    return render_template("teacher/hr_payroll.html", employee=employee, payroll_runs=payroll_runs)


@teacher_bp.route("/courses/new", methods=["GET", "POST"])
@teacher_required
def create_course():
    # POST: create a new course from teacher dashboard.
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        
        # Handle video file uploads instead of URL
        primary_video_path = None
        if 'primary_video' in request.files:
            primary_video_file = request.files['primary_video']
            if primary_video_file and primary_video_file.filename and allowed_file(primary_video_file):
                # Check file size
                primary_video_file.seek(0, os.SEEK_END)
                file_size = primary_video_file.tell()
                if file_size <= MAX_FILE_SIZE:
                    primary_video_file.seek(0)
                    filename = secure_filename(primary_video_file.filename)
                    filename = f"{int(time.time())}_primary_{filename}"
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    primary_video_file.save(file_path)
                    primary_video_path = f"/static/uploads/videos/{filename}"
        
        if len(title) < 3 or not primary_video_path:
            flash("Title and primary video are required.", "danger")
            return redirect(url_for("teacher.create_course"))
        
        # Parse extended teaching system data
        live_class_url = request.form.get("live_class_url", "").strip()
        live_class_datetime = request.form.get("live_class_datetime", "").strip()
        live_class = {}
        if live_class_url:
            live_class = {
                "url": live_class_url,
                "datetime": live_class_datetime or ""
            }
        
        # Handle multiple recorded video uploads
        videos = []
        if 'recorded_videos' in request.files:
            recorded_files = request.files.getlist('recorded_videos')
            for video_file in recorded_files:
                if video_file and video_file.filename and allowed_file(video_file):
                    video_file.seek(0, os.SEEK_END)
                    file_size = video_file.tell()
                    if file_size <= MAX_FILE_SIZE:
                        video_file.seek(0)
                        filename = secure_filename(video_file.filename)
                        filename = f"{int(time.time())}_{filename}"
                        file_path = os.path.join(UPLOAD_FOLDER, filename)
                        video_file.save(file_path)
                        video_title = request.form.get(f"video_title_{video_file.filename}", video_file.filename)
                        videos.append({
                            "url": f"/static/uploads/videos/{filename}",
                            "title": video_title
                        })
        
        # Parse notes JSON
        notes = []
        notes_json = request.form.get("notes_json", "")
        if notes_json:
            try:
                notes = json.loads(notes_json)
            except json.JSONDecodeError:
                notes = []
        
        # Parse quiz JSON
        quiz = []
        quiz_json = request.form.get("quiz_json", "")
        if quiz_json:
            try:
                quiz = json.loads(quiz_json)
            except json.JSONDecodeError:
                quiz = []
        
        thumb_path = ""
        if "thumbnail" in request.files:
            thumb_path = (
                save_upload(
                    request.files["thumbnail"],
                    "thumb",
                    ALLOWED_IMAGE,
                    3 * 1024 * 1024,
                    prefix="course_",
                )
                or ""
            )
        # Create course with extended fields
        course = Course(
            title=title,
            description=request.form.get("description", "").strip(),
            instructor_name=request.form.get("instructor_name", "").strip() or "Teacher",
            duration=request.form.get("duration", "").strip() or "4 weeks",
            level=request.form.get("level", "").strip() or "Beginner",
            price_inr=int(request.form.get("price_inr", 499)) or 499,
            teacher_id=current_user.id,
            is_published=request.form.get("is_published", "on") == "on",
            thumbnail_path=thumb_path,
            category=request.form.get("category", "").strip(),
            prerequisites=request.form.get("prerequisites", "").strip(),
            learning_outcomes=request.form.get("learning_outcomes", "").strip(),
            video_url=primary_video_path,  # Now a file path instead of URL
            content=request.form.get("content", "").strip(),
            quiz_question=request.form.get("quiz_question", "").strip(),  # Keep for compatibility
            quiz_answer=request.form.get("quiz_answer", "").strip(),       # Keep for compatibility
            live_class=live_class,
            videos=videos,
            notes=notes,
            quiz=quiz,
        )
        db.session.add(course)
        db.session.commit()
        flash(f"Course created successfully! Uploaded {len(videos)} recorded sessions.", "success")
        return redirect(url_for("teacher.dashboard"))
    return render_template("teacher/create_course.html")


def _register_teacher_lms():
    from routes.teacher_lms import register as register_teacher_lms

    register_teacher_lms(teacher_bp)


_register_teacher_lms()

