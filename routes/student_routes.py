from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user

from models.course import Certificate, Course, Enrollment
from models.store import Order
from models.user import User
from utils.role_auth import student_required

student_bp = Blueprint("student", __name__, url_prefix="/student")


@student_bp.get("/dashboard")
@student_required
def dashboard():
    user = current_user
    top_users = User.query.order_by(User.points.desc()).limit(10).all()
    enrollments = (
        Enrollment.query.filter_by(user_id=user.id, is_paid=True)
        .join(Course)
        .order_by(Enrollment.created_at.desc())
        .limit(12)
        .all()
    )
    return render_template(
        "student/dashboard.html",
        user=user,
        order_count=Order.query.filter_by(user_id=user.id).count(),
        course_count=Enrollment.query.filter_by(user_id=user.id).count(),
        cert_count=Certificate.query.filter_by(user_id=user.id).count(),
        top_users=top_users,
        enrollments=enrollments,
    )


def _register_student_lms():
    from routes.student_lms import register as register_student_lms

    register_student_lms(student_bp)


_register_student_lms()

