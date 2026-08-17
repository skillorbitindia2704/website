from flask import Blueprint, Response, render_template, request, url_for

from models.course import Course
from models.event import Event
from models.homepage_testimonial import HomeTestimonial
from models.about_content import AboutContent
from models.about_team import AboutTeamMember
from models.about_timeline import AboutTimelineEntry
from models.about_gallery import AboutGalleryImage
from models.about_partner import AboutPartnerLogo
from models.about_recognition import AboutRecognition
from models.about_counter import AboutCounter
from models.about_testimonial import AboutTestimonial
from models.internship import Internship
from models.store import Product
from models.homepage_content import HomeContent

main_bp = Blueprint("main", __name__)


@main_bp.get("/")
def home():
    import json
    
    # Query all HomeContent keys at once to prevent multiple DB queries
    homepage_settings = {row.key: row.value for row in HomeContent.query.all()}
    
    def get_content(key: str, default: str = "") -> str:
        return (homepage_settings.get(key) if homepage_settings.get(key) is not None else default) or default
        
    def get_json_content(key: str, default_str: str) -> list | dict:
        val = get_content(key, default_str)
        try:
            return json.loads(val)
        except Exception:
            try:
                return json.loads(default_str)
            except Exception:
                return []

    # Parse visibilities (default all to True)
    visibilities = {}
    try:
        raw_vis = get_content("section_visibilities", "{}")
        visibilities = json.loads(raw_vis)
    except Exception:
        pass

    sections = [
        "hero", "why_choose_us", "products", "courses", "internships", "ai_lab",
        "projects", "testimonials", "events", "certification", "cta_banner", "faq"
    ]
    for sec in sections:
        if sec not in visibilities:
            visibilities[sec] = True
        else:
            val = visibilities[sec]
            if val == "false" or val is False or val == 0 or val == "0" or val == "False":
                visibilities[sec] = False
            else:
                visibilities[sec] = True

    # Parse JSON repeaters
    stats_kpis = get_json_content("stats_kpis", '[{"number": "5000+", "label": "Students", "icon": "ri-graduation-cap-line", "speed": "1500"}, {"number": "120+", "label": "Workshops", "icon": "ri-flashlight-line", "speed": "1500"}, {"number": "50+", "label": "Schools", "icon": "ri-building-2-line", "speed": "1500"}, {"number": "24×7", "label": "Support", "icon": "ri-phone-line", "speed": "1500"}]')
    trusted_partners = get_json_content("trusted_partners", '[{"name": "Arduino", "logo": "", "link": ""}, {"name": "NVIDIA", "logo": "", "link": ""}, {"name": "Raspberry Pi", "logo": "", "link": ""}, {"name": "Microsoft", "logo": "", "link": ""}, {"name": "AWS", "logo": "", "link": ""}, {"name": "ESPRESSIF", "logo": "", "link": ""}]')
    ai_lab_equipment = get_json_content("ai_lab_equipment", '["Complete AI Lab Setup", "Robotics Kits", "IoT Modules", "Teacher Training", "Curriculum Support", "Installation & Maintenance"]')
    projects_list = get_json_content("projects_list", '[{"title": "Line Follower Robot", "description": "Robotics foundations with sensors.", "tech_stack": "Arduino, IR Sensors", "demo_link": "", "github_link": "", "is_featured": "1"}, {"title": "AI Face Detection", "description": "Computer vision demo pipeline.", "tech_stack": "Python, OpenCV", "demo_link": "", "github_link": "", "is_featured": "1"}, {"title": "Smart Home Automation", "description": "IoT + automation workflows.", "tech_stack": "ESP32, Blynk", "demo_link": "", "github_link": "", "is_featured": "1"}, {"title": "Gesture Control Robot", "description": "Control + vision interaction.", "tech_stack": "Arduino, MPU6050", "demo_link": "", "github_link": "", "is_featured": "1"}, {"title": "Obstacle Avoidance Bot", "description": "Navigation + sensor fusion.", "tech_stack": "Arduino, Ultrasonic Sensor", "demo_link": "", "github_link": "", "is_featured": "1"}]')
    faqs_list = get_json_content("faqs_list", "[]")
    
    # Query database records as fallbacks / data sources
    products = Product.query.order_by(Product.created_at.desc()).limit(8).all()
    courses = Course.query.order_by(Course.created_at.desc()).limit(6).all()
    internships = Internship.query.filter_by(is_active=True).order_by(Internship.created_at.desc()).limit(3).all()
    events = (
        Event.query.filter_by(is_active=True)
        .order_by(Event.display_order.asc(), Event.id.desc())
        .limit(6)
        .all()
    )
    testimonials = (
        HomeTestimonial.query.filter_by(is_active=True)
        .order_by(HomeTestimonial.display_order.asc(), HomeTestimonial.id.desc())
        .limit(12)
        .all()
    )
    
    # Content dictionary
    content = {
        "hero_badge_text": get_content("hero_badge_text", "AI • Robotics • Electronics"),
        "hero_badge_subtext": get_content("hero_badge_subtext", "India's learning orbit"),
        "hero_heading": get_content("hero_heading", "Premium AI + Robotics Learning Platform"),
        "hero_description": get_content("hero_description", "Learn AI, Robotics, IoT, Embedded Systems and build real projects. Shop curated kits, earn verified certificates, and access internship pathways — built for outcomes, not just content."),
        "hero_primary_btn_text": get_content("hero_primary_btn_text", "Explore Courses"),
        "hero_primary_btn_link": get_content("hero_primary_btn_link", "/courses"),
        "hero_secondary_btn_text": get_content("hero_secondary_btn_text", "Book Free Demo"),
        "hero_secondary_btn_link": get_content("hero_secondary_btn_link", "/ai-lab#enquiry"),
        "hero_tertiary_btn_text": get_content("hero_tertiary_btn_text", "Watch Video"),
        "hero_tertiary_btn_link": get_content("hero_tertiary_btn_link", "/courses"),
        "hero_layout": get_content("hero_layout", "default"),
        "hero_ai_lab_title": get_content("hero_ai_lab_title", "AI & Robotics Lab Atmosphere"),
        "hero_ai_lab_description": get_content("hero_ai_lab_description", "Experience cutting-edge AI and robotics learning environment."),
        "hero_image": get_content("hero_image", ""),
        "hero_ai_lab_image": get_content("hero_ai_lab_image", ""),
        "hero_robotics_image": get_content("hero_robotics_image", ""),
        "hero_workshop_image": get_content("hero_workshop_image", ""),
        "hero_student_activity_image": get_content("hero_student_activity_image", ""),
        
        "ai_lab_heading": get_content("ai_lab_heading", "AI Lab Setup for Schools & Colleges"),
        "ai_lab_description": get_content("ai_lab_description", "Premium NEP-aligned labs with hardware + curriculum + teacher enablement."),
        "ai_lab_image": get_content("ai_lab_image", ""),
        "ai_lab_video": get_content("ai_lab_video", ""),
        "ai_lab_cta_text": get_content("ai_lab_cta_text", "Request proposal"),
        "ai_lab_cta_link": get_content("ai_lab_cta_link", "/ai-lab#enquiry"),
        
        "footer_promo_text": get_content("footer_promo_text", "Ready to orbit your career?"),
        "footer_promo_btn_text": get_content("footer_promo_btn_text", "Create free account"),
        "footer_promo_btn_link": get_content("footer_promo_btn_link", "/auth/signup"),
        "footer_promo_image": get_content("footer_promo_image", ""),
        "footer_promo_badge": get_content("footer_promo_badge", "Join thousands building hardware skills with guided paths and employer-ready proof."),
        
        # SEO
        "seo_meta_title": get_content("seo_meta_title", "Skill Orbit India — Learn, Build, Certify"),
        "seo_meta_description": get_content("seo_meta_description", "Skill Orbit India: practical tech courses, curated electronics kits, verified certificates, internships, IT services, and AI lab setup — built for outcomes, not just content."),
        "seo_keywords": get_content("seo_keywords", "Skill Orbit India, tech courses, electronics store, certificates, internships, IT services, AI lab, online learning India"),
        "seo_canonical_url": get_content("seo_canonical_url", ""),
        "seo_og_image": get_content("seo_og_image", ""),
        "seo_twitter_image": get_content("seo_twitter_image", ""),
        "seo_schema_markup": get_content("seo_schema_markup", ""),
        
        # Theme Settings
        "theme_primary_color": get_content("theme_primary_color", "#4F46E5"),
        "theme_secondary_color": get_content("theme_secondary_color", "#06B6D4"),
        "theme_gradient_theme": get_content("theme_gradient_theme", "blue-purple"),
        "theme_card_radius": get_content("theme_card_radius", "22px"),
        "theme_shadows": get_content("theme_shadows", "glow"),
        "theme_typography": get_content("theme_typography", "Outfit"),
        "theme_section_spacing": get_content("theme_section_spacing", "medium"),
        "theme_dark_mode": get_content("theme_dark_mode", "1"),
        
        # Animations
        "anim_scroll": get_content("anim_scroll", "1"),
        "anim_hover": get_content("anim_hover", "1"),
        "anim_parallax": get_content("anim_parallax", "1"),
        "anim_counter_speed": get_content("anim_counter_speed", "1500"),
        "anim_transition_speed": get_content("anim_transition_speed", "600"),
        "anim_floating_effects": get_content("anim_floating_effects", "1"),
        "anim_speed": get_content("anim_speed", "normal"),
    }

    return render_template(
        "home.html",
        products=products,
        courses=courses,
        internships=internships,
        events=events,
        testimonials=testimonials,
        content=content,
        visibilities=visibilities,
        stats_kpis=stats_kpis,
        trusted_partners=trusted_partners,
        ai_lab_equipment=ai_lab_equipment,
        projects_list=projects_list,
        faqs_list=faqs_list,
    )


@main_bp.get("/about")
def about():
    import json
    def get_content(key: str, default: str = "") -> str:
        row = AboutContent.query.filter_by(key=key).first()
        return (row.value if row and row.value is not None else default) or default

    # Parse visibilities (default all to true)
    visibilities = {}
    try:
        raw_vis = get_content("section_visibilities", "{}")
        visibilities = json.loads(raw_vis)
    except Exception:
        pass

    # Ensure defaults are True for sections if not explicitly set to False
    sections = [
        "hero", "who_we_are", "mission_vision", "what_we_offer", "why_choose_us",
        "counters", "timeline", "team", "gallery", "partners", "testimonials", "recognition"
    ]
    for sec in sections:
        if sec not in visibilities:
            visibilities[sec] = True
        else:
            val = visibilities[sec]
            if val == "false" or val is False or val == 0 or val == "0":
                visibilities[sec] = False
            else:
                visibilities[sec] = True

    # Parse what_we_offer_cards and why_choose_us_cards
    what_we_offer_cards = []
    try:
        raw_cards = get_content("what_we_offer_cards", "[]")
        what_we_offer_cards = json.loads(raw_cards)
    except Exception:
        pass

    why_choose_us_cards = []
    try:
        raw_reasons = get_content("why_choose_us_cards", "[]")
        why_choose_us_cards = json.loads(raw_reasons)
    except Exception:
        pass

    content = {
        "hero_badge_text": get_content("hero_badge_text", "About Us"),
        "hero_trust_line": get_content("hero_trust_line", ""),
        "hero_heading": get_content("hero_heading", "About Skill Orbit India"),
        "hero_subtitle": get_content(
            "hero_subtitle",
            "Empowering Future Tech Innovators through practical, hands-on learning.",
        ),
        "hero_description": get_content("hero_description", ""),
        "hero_primary_btn_text": get_content("hero_primary_btn_text", "Explore Programs"),
        "hero_primary_btn_link": get_content("hero_primary_btn_link", "/courses"),
        "hero_secondary_btn_text": get_content("hero_secondary_btn_text", "Visit AI Lab"),
        "hero_secondary_btn_link": get_content("hero_secondary_btn_link", "/ai-lab"),
        
        "hero_stat1_num": get_content("hero_stat1_num", "5000+"),
        "hero_stat1_lbl": get_content("hero_stat1_lbl", "Students Trained"),
        "hero_stat2_num": get_content("hero_stat2_num", "120+"),
        "hero_stat2_lbl": get_content("hero_stat2_lbl", "Workshops"),
        "hero_stat3_num": get_content("hero_stat3_num", "50+"),
        "hero_stat3_lbl": get_content("hero_stat3_lbl", "School Partners"),
        "hero_stat4_num": get_content("hero_stat4_num", "24×7"),
        "hero_stat4_lbl": get_content("hero_stat4_lbl", "Support"),
        
        "hero_gradient_theme": get_content("hero_gradient_theme", "blue-purple"),
        "hero_image": get_content("hero_image", ""),
        
        "who_we_are_title": get_content("who_we_are_title", "Who we are"),
        "who_we_are_body": get_content(
            "who_we_are_body",
            "Skill Orbit India is a hands-on EdTech platform that bridges theory with real hardware projects — "
            "AI, Robotics, IoT, Embedded Systems, and industry-ready certification.",
        ),
        "who_we_are_btn_text": get_content("who_we_are_btn_text", "Explore Programs"),
        "who_we_are_btn_link": get_content("who_we_are_btn_link", "/courses"),
        "who_we_are_feature1": get_content("who_we_are_feature1", "Hands-on labs"),
        "who_we_are_feature2": get_content("who_we_are_feature2", "Mentor support"),
        "who_we_are_feature3": get_content("who_we_are_feature3", "Project pathways"),
        "who_we_are_side_image": get_content("who_we_are_side_image", ""),
        
        "mission_icon": get_content("mission_icon", "🎯"),
        "mission_heading": get_content("mission_heading", "Our Mission"),
        "mission_text": get_content(
            "mission_text",
            "To make practical tech education accessible through hands-on learning and real-world projects.",
        ),
        
        "vision_icon": get_content("vision_icon", "🚀"),
        "vision_heading": get_content("vision_heading", "Our Vision"),
        "vision_text": get_content(
            "vision_text",
            "To build a future-ready AI + Robotics learning ecosystem accessible to every learner.",
        ),
        
        "seo_meta_title": get_content("seo_meta_title", "About Us — Skill Orbit India"),
        "seo_meta_description": get_content(
            "seo_meta_description",
            "About Skill Orbit India: our mission, hands-on EdTech approach, courses, certificates, internships, and services for tech learners across India.",
        ),
        "seo_keywords": get_content("seo_keywords", "about Skill Orbit India, EdTech mission, tech education India, courses, certificates"),
        "seo_canonical_url": get_content("seo_canonical_url", ""),
        "seo_schema_markup": get_content("seo_schema_markup", ""),
        "seo_og_image": get_content("seo_og_image", ""),
    }

    team = (
        AboutTeamMember.query.filter_by(is_active=True)
        .order_by(AboutTeamMember.display_order.asc(), AboutTeamMember.id.desc())
        .limit(12)
        .all()
    )
    timeline = (
        AboutTimelineEntry.query.filter_by(is_active=True)
        .order_by(AboutTimelineEntry.display_order.asc(), AboutTimelineEntry.id.asc())
        .limit(12)
        .all()
    )
    gallery = (
        AboutGalleryImage.query.filter_by(is_active=True)
        .order_by(AboutGalleryImage.display_order.asc(), AboutGalleryImage.id.desc())
        .limit(24)
        .all()
    )
    partners = (
        AboutPartnerLogo.query.filter_by(is_active=True)
        .order_by(AboutPartnerLogo.display_order.asc(), AboutPartnerLogo.id.desc())
        .limit(24)
        .all()
    )
    recognition = (
        AboutRecognition.query.filter_by(is_active=True)
        .order_by(AboutRecognition.display_order.asc(), AboutRecognition.id.desc())
        .limit(12)
        .all()
    )
    counters = (
        AboutCounter.query.filter_by(is_active=True)
        .order_by(AboutCounter.display_order.asc(), AboutCounter.id.desc())
        .limit(12)
        .all()
    )
    testimonials = (
        AboutTestimonial.query.filter_by(is_active=True)
        .order_by(AboutTestimonial.display_order.asc(), AboutTestimonial.id.desc())
        .limit(20)
        .all()
    )

    return render_template(
        "about.html",
        content=content,
        team=team,
        timeline=timeline,
        gallery=gallery,
        partners=partners,
        recognition=recognition,
        counters=counters,
        testimonials=testimonials,
        visibilities=visibilities,
        what_we_offer_cards=what_we_offer_cards,
        why_choose_us_cards=why_choose_us_cards,
    )


@main_bp.get("/robots.txt")
def robots_txt():
    """Crawl hints for search engines; keeps private areas out of index."""
    base = request.url_root.rstrip("/")
    body = "\n".join(
        [
            "User-agent: *",
            "Disallow: /admin",
            "Disallow: /dashboard",
            "Disallow: /teacher",
            "Disallow: /student",
            "Disallow: /api/",
            "Disallow: /store/cart",
            "Disallow: /store/checkout",
            "Allow: /",
            "",
            f"Sitemap: {base}/sitemap.xml",
        ]
    )
    return Response(body, mimetype="text/plain; charset=utf-8")


@main_bp.get("/sitemap.xml")
def sitemap_xml():
    """Dynamic sitemap for public marketing and catalog URLs."""
    urls = [
        {"loc": url_for("main.home", _external=True), "changefreq": "daily", "priority": "1.0"},
        {"loc": url_for("main.about", _external=True), "changefreq": "monthly", "priority": "0.8"},
        {"loc": url_for("courses.list_courses", _external=True), "changefreq": "daily", "priority": "0.9"},
        {"loc": url_for("store.listing", _external=True), "changefreq": "daily", "priority": "0.85"},
        {"loc": url_for("internships.listing", _external=True), "changefreq": "weekly", "priority": "0.85"},
        {"loc": url_for("certificates.verify_lookup", _external=True), "changefreq": "monthly", "priority": "0.7"},
        {"loc": url_for("it_services.index", _external=True), "changefreq": "monthly", "priority": "0.75"},
        {"loc": url_for("ai_lab.index", _external=True), "changefreq": "monthly", "priority": "0.75"},
    ]
    try:
        for c in Course.query.filter_by(is_published=True).order_by(Course.created_at.desc()).limit(200).all():
            urls.append(
                {
                    "loc": url_for("courses.buy_course", course_id=c.id, _external=True),
                    "changefreq": "weekly",
                    "priority": "0.7",
                }
            )
    except Exception:
        pass
    xml = render_template("sitemap.xml", urls=urls)
    return Response(xml, mimetype="application/xml; charset=utf-8")
