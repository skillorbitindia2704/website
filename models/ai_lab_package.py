from datetime import datetime

from models import db


class AILabPackage(db.Model):
    """AI & robotics lab packages for institutions."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    # Legacy columns kept for backward compatibility with existing SQLite schemas.
    slug = db.Column(db.String(120), nullable=False, default="")
    short_description = db.Column(db.String(255), default="")
    package_type = db.Column(db.String(60), default="custom")
    badge = db.Column(db.String(60), default="")
    is_popular = db.Column(db.Boolean, default=False)
    is_visible = db.Column(db.Boolean, default=True)
    cta_text = db.Column(db.String(60), default="Get started")
    cta_link = db.Column(db.String(255), default="#inquiry")

    subtitle = db.Column(db.String(200), nullable=False)
    pricing_text = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    features = db.Column(db.Text, nullable=False)  # JSON-like string or newline-separated
    button_text = db.Column(db.String(50), default="Get started")
    button_link = db.Column(db.String(100), default="#inquiry")
    badge_text = db.Column(db.String(50), default="")
    icon = db.Column(db.String(10), default="🔧")
    display_order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_features_list(self):
        """Parse features as newline-separated list."""
        if not self.features:
            return []
        return [f.strip() for f in self.features.split('\n') if f.strip()]

    def set_features_list(self, features_list):
        """Store features as newline-separated string."""
        self.features = '\n'.join(str(f).strip() for f in features_list if f and str(f).strip())
