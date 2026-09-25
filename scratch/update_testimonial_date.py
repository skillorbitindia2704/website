import os
import sys
sys.path.insert(0, os.path.abspath("."))
from app import create_app
from models.about_testimonial import AboutTestimonial
from models import db

app = create_app()
with app.app_context():
    t1 = AboutTestimonial.query.filter_by(id=1).first()
    if t1:
        print("Before t1.course_name:", repr(t1.course_name))
        t1.course_name = "AI, Robotics & IoT Internship Program 2026"
        db.session.commit()
        print("After t1.course_name:", repr(t1.course_name))

    # Also check if any other testimonial has a truncated 202
    for t in AboutTestimonial.query.all():
        if t.course_name and t.course_name.endswith("202"):
            t.course_name = t.course_name + "6"
            print(f"Fixed testimonial {t.id}: {t.course_name}")
    db.session.commit()
    print("Testimonial date update complete!")
