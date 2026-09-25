import json
import os
import sys
sys.path.insert(0, os.path.abspath("."))
from app import create_app
from models.about_content import AboutContent
from models import db

reasons = [
    {
        "icon": "ri-tools-line",
        "title": "Hands-on Build Culture",
        "desc": "Learn by building real hardware prototypes, circuit designs, and AI models instead of passive slide lectures."
    },
    {
        "icon": "ri-user-star-line",
        "title": "Industry-Experienced Mentors",
        "desc": "Direct guidance and code reviews from practicing engineers with real-world deployment experience."
    },
    {
        "icon": "ri-verified-badge-line",
        "title": "Verified Public Credentials",
        "desc": "Tamper-proof, QR-verifiable certificates designed for showcase on resumes and LinkedIn profiles."
    },
    {
        "icon": "ri-briefcase-4-line",
        "title": "Direct Internship Pathways",
        "desc": "Structured pathways linking high-performing learners to industry internships and live client projects."
    },
    {
        "icon": "ri-cpu-line",
        "title": "Integrated Hardware Kits",
        "desc": "Curated electronics components, microcontrollers, and robotics hardware kits delivered directly to learners."
    },
    {
        "icon": "ri-book-read-line",
        "title": "NEP 2020 Aligned Pedagogy",
        "desc": "Outcome-oriented curricula and institutional lab setups aligned with national education benchmarks."
    },
    {
        "icon": "ri-customer-service-2-line",
        "title": "24×7 Community Support",
        "desc": "Round-the-clock peer learning community and mentor support so you never stay stuck on a problem."
    },
    {
        "icon": "ri-funds-line",
        "title": "Transparent and Affordable Access",
        "desc": "High-caliber frontier technology education made accessible to every ambitious student across India."
    }
]

app = create_app()
with app.app_context():
    row = AboutContent.query.filter_by(key="why_choose_us_cards").first()
    if not row:
        row = AboutContent(key="why_choose_us_cards", value=json.dumps(reasons))
        db.session.add(row)
    else:
        row.value = json.dumps(reasons)
    db.session.commit()
    print("Updated why_choose_us_cards successfully!")
