from flask import Blueprint, render_template
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from models import db
from models.course import Certificate, Enrollment
from models.notification import Notification
from models.store import Order, OrderItem
from models.user import User
from utils.decorators import login_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/")
@login_required
def index():
    top_users = User.query.order_by(User.points.desc()).limit(10).all()
    
    # Use aggregation to avoid N+1 queries instead of separate COUNT queries
    counts = (
        db.session.query(
            func.count(Order.id).label('order_count'),
            func.count(Enrollment.id).label('course_count'),
            func.count(Certificate.id).label('cert_count'),
        )
        .outerjoin(Order, Order.user_id == current_user.id)
        .outerjoin(Enrollment, Enrollment.user_id == current_user.id)
        .outerjoin(Certificate, Certificate.user_id == current_user.id)
        .first()
    )
    
    order_count = counts.order_count or 0
    course_count = counts.course_count or 0
    cert_count = counts.cert_count or 0
    
    unread_notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    recent_notes = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template(
        "dashboard/index.html",
        top_users=top_users,
        order_count=order_count,
        course_count=course_count,
        cert_count=cert_count,
        unread_notifications=unread_notifications,
        recent_notes=recent_notes,
    )


@dashboard_bp.get("/orders")
@login_required
def orders():
    orders_list = (
        Order.query.options(selectinload(Order.items).selectinload(OrderItem.product))
        .filter_by(user_id=current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )
    return render_template("dashboard/orders.html", orders=orders_list)


@dashboard_bp.get("/courses")
@login_required
def my_courses():
    enrollments = Enrollment.query.filter_by(user_id=current_user.id).all()
    return render_template("dashboard/courses.html", enrollments=enrollments)


@dashboard_bp.get("/certificates")
@login_required
def certificates():
    certs = Certificate.query.filter_by(user_id=current_user.id).order_by(Certificate.issued_at.desc()).all()
    return render_template("dashboard/certificates.html", certificates=certs)
