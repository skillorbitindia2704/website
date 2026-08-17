from datetime import datetime

from models import db


class HomePageHero(db.Model):
    """Homepage hero section content and visuals management."""

    __tablename__ = "homepage_hero"

    id = db.Column(db.Integer, primary_key=True)

    # Badge & text content
    badge_text = db.Column(db.String(120), default="AI • Robotics • Electronics")
    badge_subtext = db.Column(db.String(160), default="India's learning orbit")

    # Main heading & description
    heading = db.Column(
        db.String(255),
        default="Premium AI + Robotics Learning Platform",
        nullable=False,
    )
    description = db.Column(
        db.Text,
        default="Learn AI, Robotics, IoT, Embedded Systems and build real projects. Shop curated kits, earn verified certificates, and access internship pathways — built for outcomes, not just content.",
    )

    # CTA Buttons
    primary_button_text = db.Column(db.String(80), default="Explore Courses")
    primary_button_link = db.Column(db.String(255), default="/courses")
    secondary_button_text = db.Column(db.String(80), default="Book Free Demo")
    secondary_button_link = db.Column(db.String(255), default="/ai-lab#enquiry")
    tertiary_button_text = db.Column(db.String(80), default="Watch Video")
    tertiary_button_link = db.Column(db.String(255), default="/courses")

    # Main hero image
    hero_image = db.Column(db.String(255), nullable=True)

    # Right side card visuals (AI Lab card section)
    ai_lab_image = db.Column(db.String(255), nullable=True)
    robotics_image = db.Column(db.String(255), nullable=True)
    workshop_image = db.Column(db.String(255), nullable=True)
    student_activity_image = db.Column(db.String(255), nullable=True)

    # Right side card content
    ai_lab_card_title = db.Column(db.String(160), default="AI & Robotics Lab Atmosphere")
    ai_lab_card_description = db.Column(
        db.Text, default="Experience cutting-edge AI and robotics learning environment."
    )

    # Card badges/features
    card_feature_1_title = db.Column(db.String(80), default="Live Projects")
    card_feature_1_desc = db.Column(db.String(160), default="Portfolio-ready builds")
    card_feature_2_title = db.Column(db.String(80), default="Verified Certs")
    card_feature_2_desc = db.Column(db.String(160), default="QR verification")

    # KPI/Statistics section
    kpi_1_label = db.Column(db.String(60), default="5000+")
    kpi_1_text = db.Column(db.String(60), default="Students")
    kpi_2_label = db.Column(db.String(60), default="120+")
    kpi_2_text = db.Column(db.String(60), default="Workshops")
    kpi_3_label = db.Column(db.String(60), default="50+")
    kpi_3_text = db.Column(db.String(60), default="Schools")
    kpi_4_label = db.Column(db.String(60), default="24×7")
    kpi_4_text = db.Column(db.String(60), default="Support")

    # Publishing & visibility
    is_published = db.Column(db.Boolean, default=True)
    is_draft = db.Column(db.Boolean, default=False)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "badge_text": self.badge_text,
            "badge_subtext": self.badge_subtext,
            "heading": self.heading,
            "description": self.description,
            "primary_button": {
                "text": self.primary_button_text,
                "link": self.primary_button_link,
            },
            "secondary_button": {
                "text": self.secondary_button_text,
                "link": self.secondary_button_link,
            },
            "tertiary_button": {
                "text": self.tertiary_button_text,
                "link": self.tertiary_button_link,
            },
            "hero_image": self.hero_image,
            "ai_lab_card": {
                "title": self.ai_lab_card_title,
                "description": self.ai_lab_card_description,
                "images": {
                    "main": self.ai_lab_image,
                    "robotics": self.robotics_image,
                    "workshop": self.workshop_image,
                    "student_activity": self.student_activity_image,
                },
            },
            "card_features": [
                {
                    "title": self.card_feature_1_title,
                    "description": self.card_feature_1_desc,
                },
                {
                    "title": self.card_feature_2_title,
                    "description": self.card_feature_2_desc,
                },
            ],
            "kpis": [
                {"label": self.kpi_1_label, "text": self.kpi_1_text},
                {"label": self.kpi_2_label, "text": self.kpi_2_text},
                {"label": self.kpi_3_label, "text": self.kpi_3_text},
                {"label": self.kpi_4_label, "text": self.kpi_4_text},
            ],
            "is_published": self.is_published,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "updated_at": self.updated_at.isoformat(),
        }
