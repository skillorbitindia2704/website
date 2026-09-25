import os
import sys
sys.path.insert(0, os.path.abspath("."))
from app import create_app
from models.homepage_hero import HomePageHero
from models.homepage_content import HomeContent
from models.site_setting import SiteSetting
from models import db

app = create_app()
with app.app_context():
    # 1. Issue 17: Hero button typo "See What We Builds" -> "See What We Build"
    for h in HomePageHero.query.all():
        if h.tertiary_button_text and "Builds" in h.tertiary_button_text:
            print("Before Hero tertiary_button_text:", repr(h.tertiary_button_text))
            h.tertiary_button_text = h.tertiary_button_text.replace("See What We Builds", "See What We Build")
            print("After Hero tertiary_button_text:", repr(h.tertiary_button_text))

    for c in HomeContent.query.all():
        if c.value and "See What We Builds" in str(c.value):
            print("Before HomeContent key:", c.key, repr(c.value))
            c.value = c.value.replace("See What We Builds", "See What We Build")
            print("After HomeContent key:", c.key, repr(c.value))

    # 2. Issue 18: Footer address typo "Uttar Pradeh" -> "Uttar Pradesh"
    for s in SiteSetting.query.all():
        if s.value and "Uttar Pradeh" in str(s.value):
            print("Before SiteSetting key:", s.key, repr(s.value))
            s.value = s.value.replace("Uttar Pradeh", "Uttar Pradesh")
            print("After SiteSetting key:", s.key, repr(s.value))

    db.session.commit()
    print("Database updates for Issue 17 and Issue 18 complete!")
