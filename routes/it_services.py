"""Public EdTech Services offering page and lead capture."""

import re
from uuid import uuid4

from email_validator import EmailNotValidError, validate_email
from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError

from models import db
from models.service_package import ServicePackage
from models.service_request import ServiceRequest
from utils.decorators import login_required

it_services_bp = Blueprint("it_services", __name__)

# EdTech Services Catalog
EDTECH_SERVICES_CATALOG = [
    {
        "slug": "summer-camp",
        "title": "Summer Camp",
        "description": "Short-term immersive programs for school students covering coding, robotics, and AI fundamentals.",
        "price_note": "Contact for rates",
        "icon": "ri-sun-line",
    },
    {
        "slug": "coding-bootcamp",
        "title": "Coding Bootcamp",
        "description": "Industry-focused bootcamps in Web Development, AI, and App Development from beginner to advanced level.",
        "price_note": "From ₹15,000",
        "icon": "ri-computer-line",
    },
    {
        "slug": "workshops",
        "title": "Workshops",
        "description": "Hands-on practical sessions on Arduino, IoT, AI tools, and emerging technologies.",
        "price_note": "Per session pricing",
        "icon": "ri-tools-line",
    },
    {
        "slug": "webinars",
        "title": "Webinars",
        "description": "Live online sessions with industry experts on careers, technology trends, and skill building.",
        "price_note": "Free to ₹500",
        "icon": "ri-camera-line",
    },
    {
        "slug": "seminars",
        "title": "Seminars",
        "description": "On-campus seminars for colleges covering emerging tech, career guidance, and innovation.",
        "price_note": "Custom packages",
        "icon": "ri-mic-line",
    },
    {
        "slug": "teacher-training",
        "title": "Teacher Training Programs",
        "description": "Empowering educators with coding, AI tools, and modern digital teaching methodologies.",
        "price_note": "Institutional pricing",
        "icon": "ri-user-star-line",
    },
    {
        "slug": "drone-bootcamp",
        "title": "Drone Boot Camp",
        "description": "Practical drone training programs covering drone building, flight control, safety regulations, and real-world applications.",
        "price_note": "Contact us",
        "icon": "ri-flight-takeoff-line",
    },
]


def _catalog_by_slug(slug):
    for item in _public_services():
        if item["slug"] == slug:
            return item
    return None


def _slugify(title):
    base = re.sub(r"[^a-z0-9]+", "-", (title or "").strip().lower()).strip("-")
    return base or f"service-{uuid4().hex[:8]}"


def _public_services():
    rows = (
        ServicePackage.query.filter_by(is_active=1)
        .order_by(ServicePackage.display_order.asc(), ServicePackage.id.asc())
        .all()
    )
    if rows:
        return [
            {
                "id": row.id,
                "slug": row.slug,
                "title": row.title,
                "description": row.short_description,
                "price_note": row.pricing_text,
                "icon": row.icon,
                "features": row.get_features_list(),
                "badge_text": row.badge_text,
                "category": row.category,
                "button_text": row.button_text or "Request service",
            }
            for row in rows
        ]
    return EDTECH_SERVICES_CATALOG


def ensure_default_service_packages():
    try:
        if ServicePackage.query.first():
            return
    except Exception:
        return
    for idx, item in enumerate(EDTECH_SERVICES_CATALOG):
        row = ServicePackage(
            title=item["title"],
            slug=item["slug"] or _slugify(item["title"]),
            short_description=item.get("description", ""),
            full_description=item.get("description", ""),
            pricing_text=item.get("price_note", ""),
            features="",
            icon=item.get("icon", "🔧"),
            image="",
            button_text="Request service",
            button_link="#service-modal",
            category="",
            badge_text="",
            display_order=idx,
            is_active=1,
        )
        db.session.add(row)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


@it_services_bp.get("/")
@login_required
def index():
    return render_template("it_services/index.html", services=_public_services())


@it_services_bp.post("/request")
@login_required
def submit_request():
    # POST: capture a service inquiry from the public form (no login required).
    full_name = request.form.get("full_name", "").strip()
    email_raw = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    service_slug = request.form.get("service_slug", "").strip()
    requirement = request.form.get("requirement", "").strip()

    if len(full_name) < 2:
        flash("Please enter your name.", "danger")
        return redirect(url_for("it_services.index"))
    try:
        email = validate_email(email_raw, check_deliverability=False).normalized
    except EmailNotValidError:
        flash("Please enter a valid email.", "danger")
        return redirect(url_for("it_services.index"))
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 10:
        flash("Please enter a valid phone number (at least 10 digits).", "danger")
        return redirect(url_for("it_services.index"))
    svc = _catalog_by_slug(service_slug)
    if not svc:
        flash("Please pick a valid service.", "danger")
        return redirect(url_for("it_services.index"))
    if len(requirement) < 20:
        flash("Please describe your requirement in at least 20 characters.", "warning")
        return redirect(url_for("it_services.index"))

    row = ServiceRequest(
        full_name=full_name,
        email=email,
        phone=phone,
        service_slug=svc["slug"],
        service_title=svc["title"],
        requirement=requirement,
        status="new",
    )
    try:
        db.session.add(row)
        db.session.commit()
        flash("Thanks — our team will reach out shortly.", "success")
        return redirect(url_for("it_services.index"))
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("Failed to save request. Please try again.", "danger")
        return redirect(url_for("it_services.index"))
