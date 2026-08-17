import os
import sys
sys.path.insert(0, os.getcwd())

from app import create_app
from flask import render_template
from models import db
from models.homepage_content import HomeContent
from models.homepage_testimonial import HomeTestimonial
from models.course import Course
from models.event import Event
from models.internship import Internship
from models.store import Product

print("Initializing test environment to compile templates...")
app = create_app()

with app.app_context():
    # Load dummy listings to ensure loops run and render
    courses = Course.query.limit(2).all()
    events = Event.query.limit(2).all()
    products = Product.query.filter(Product.is_deleted.isnot(True)).limit(2).all()
    internships = Internship.query.limit(2).all()
    testimonials = HomeTestimonial.query.limit(2).all()
    
    content = {
        "hero_badge_text": "Badge",
        "hero_badge_subtext": "Subtext",
        "hero_heading": "Heading",
        "hero_description": "Description",
        "theme_gradient_theme": "blue-purple",
        "theme_card_radius": "22px",
        "theme_shadows": "glow",
        "theme_typography": "Outfit",
        "theme_dark_mode": "1",
        "section_visibilities": "{}",
        "stats_kpis": "[]",
        "trusted_partners": "[]",
        "ai_lab_equipment": "[]",
        "projects_list": "[]",
        "faqs_list": "[]"
    }

    print("Simulating rendering of 'admin/homepage_manager.html' in test request context...")
    with app.test_request_context():
        try:
            html = render_template(
                "admin/homepage_manager.html",
                content=content,
                courses=courses,
                events=events,
                products=products,
                internships=internships,
                testimonials=testimonials,
                versions=[],
                logs=[],
                last_updated=None
            )
            print("  ✓ Template 'admin/homepage_manager.html' compiled and rendered successfully!")
            assert "Manage Testimonials Database" in html, "Testimonials link is missing"
            assert "Manage Events Database" in html, "Events link is missing"
            print("  ✓ Verified direct database management button links exist in the HTML output.")
            
        except Exception as exc:
            print(f"  ❌ Template render failed: {exc}")
            sys.exit(1)

    print("Simulating rendering of admin dashboard landing page 'admin/index.html' (with mocked admin permissions)...")
    with app.test_request_context():
        try:
            # We mock the stats dictionary passed by admin index
            stats = {
                "users": 10,
                "orders": 5,
                "courses": 3,
                "service_requests": 2,
                "ai_lab_inquiries": 1,
                "ai_lab_packages": 2
            }
            # Inject a mock admin_can function that always returns True
            html_index = render_template(
                "admin/index.html",
                stats=stats,
                admin_can=lambda permission: True
            )
            print("  ✓ Template 'admin/index.html' compiled and rendered successfully!")
            assert "Homepage Manager" in html_index, "Homepage Manager link is missing in landing page"
            assert "Homepage events" not in html_index, "Duplicate 'Homepage events' card was not removed"
            assert "Homepage testimonials" not in html_index, "Duplicate 'Homepage testimonials' card was not removed"
            assert "Homepage hero manager" not in html_index, "Duplicate 'Homepage hero manager' card was not removed"
            print("  ✓ Verified all duplicate individual cards were safely removed and layout is clean.")
            
        except Exception as exc:
            print(f"  ❌ Admin index template render failed: {exc}")
            sys.exit(1)

print("\n🎉 ALL TEMPLATE COMPILE & RENDER TESTS PASSED FLAWLESSLY!")
