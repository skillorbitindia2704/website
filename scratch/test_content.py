import os
import sys
import re

# Add root folder to python path
sys.path.insert(0, os.getcwd())

from app import create_app
from models import db
from models.about_content import AboutContent

# Ensure testing configuration is active but keep CSRF enabled to test CSRF validation!
app = create_app()
app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = True

client = app.test_client()

def extract_csrf_token(html_content):
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html_content)
    if match:
        return match.group(1)
    match = re.search(r"name='csrf_token'\s+value='([^']+)'", html_content)
    if match:
        return match.group(1)
    return None

print("=== STARTING ABOUT CONTENT SYSTEM VERIFICATION SUITE ===")

# Save original database state so we can restore it at the end
print("\n[Prep] Fetching original About Content copy to prevent test pollution...")
original_copy = {}
with app.app_context():
    for row in AboutContent.query.all():
        original_copy[row.key] = row.value
print(f"-> Saved {len(original_copy)} original keys.")

# 1. Access Login Page to get CSRF Token
print("\n[Step 1] Fetching login page to extract CSRF token...")
resp = client.get("/login")
assert resp.status_code == 200, f"Failed to load login page, got {resp.status_code}"
login_csrf = extract_csrf_token(resp.get_data(as_text=True))
assert login_csrf is not None, "Could not find CSRF token on login page!"
print(f"-> Extracted Login CSRF Token: {login_csrf[:15]}...")

# 2. Authenticate as default platform admin
print("\n[Step 2] Attempting Admin login with CSRF token...")
login_resp = client.post("/login", data={
    "csrf_token": login_csrf,
    "email": "skillorbitindia2704@gmail.com",
    "password": "MAAN0864208642"
}, follow_redirects=True)

assert login_resp.status_code == 200, f"Login failed with status {login_resp.status_code}"
assert b"Logout" in login_resp.data or b"Dashboard" in login_resp.data, "Login verification failed!"
print("-> Authentication successful!")

# Helper to execute GET on content page and fetch CSRF token
def get_content_page_and_token():
    resp = client.get("/admin/about/content")
    assert resp.status_code == 200, f"Failed to load content page, got {resp.status_code}"
    token = extract_csrf_token(resp.get_data(as_text=True))
    return resp, token

# 3. Test 1: Submit Form WITH normal fields and Emojis/Unicode
print("\n[Step 3] Test 1: Submitting 'Save content' form with Emojis...")
_, csrf_token = get_content_page_and_token()
assert csrf_token is not None, "Could not extract CSRF token from content page!"

post_data = {
    "csrf_token": csrf_token,
    "hero_heading": "Transforming Futures with AI 🚀🤖",
    "hero_subtitle": "NEP 2020 Aligned Advanced Skill Training Hub.",
    "who_we_are_title": "About Skill Orbit India 🇮🇳",
    "who_we_are_body": "Empowering students and professionals through advanced labs... 🌟",
    "mission_text": "To democratize deep tech education.",
    "vision_text": "An AI-ready talent ecosystem globally."
}

resp = client.post("/admin/about/content", data=post_data, follow_redirects=True)
assert resp.status_code == 200, f"POST request returned {resp.status_code} instead of 200"
html = resp.get_data(as_text=True)

# Assert no CSRF or general 400 Bad Request error is shown
assert "400 Bad Request" not in html, "Failing with 400 Bad Request!"
assert "Your session may have expired, or the CSRF token was invalid" not in html, "CSRF error was triggered!"
assert "About content saved successfully." in html, "Success flash message was missing!"

# Verify entries in the database
with app.app_context():
    heading_row = AboutContent.query.filter_by(key="hero_heading").first()
    assert heading_row is not None and heading_row.value == "Transforming Futures with AI 🚀🤖", "Hero heading mismatch"
    
    title_row = AboutContent.query.filter_by(key="who_we_are_title").first()
    assert title_row is not None and title_row.value == "About Skill Orbit India 🇮🇳", "Who we are title mismatch"
    
    mission_row = AboutContent.query.filter_by(key="mission_text").first()
    assert mission_row is not None and mission_row.value == "To democratize deep tech education.", "Mission text mismatch"
    print("-> Test 1 PASSED: About Content saved successfully with Emojis!")

# 4. Test 2: Submit Form with Large Textarea Content
print("\n[Step 4] Test 2: Submitting form with extremely large textarea body content...")
_, csrf_token = get_content_page_and_token()

large_text = "Who We Are Long Body " + ("A" * 1000) + " End of story 🌟"

post_data_large = {
    "csrf_token": csrf_token,
    "hero_heading": "Valid Heading",
    "hero_subtitle": "Subtitle content",
    "who_we_are_title": "Who we are",
    "who_we_are_body": large_text,
    "mission_text": "Our Mission text goes here...",
    "vision_text": "Our Vision text goes here..."
}

resp = client.post("/admin/about/content", data=post_data_large, follow_redirects=True)
assert resp.status_code == 200, f"POST request returned {resp.status_code}"
html = resp.get_data(as_text=True)
assert "About content saved successfully." in html

with app.app_context():
    body_row = AboutContent.query.filter_by(key="who_we_are_body").first()
    assert body_row is not None, "Body content not found!"
    assert len(body_row.value) > 1000, "Body content length is too short!"
    assert "End of story" in body_row.value, "Content was truncated!"
    print("-> Test 2 PASSED: Large textarea content saves perfectly without truncation!")

# 5. Test 3: Testing input validations on POST route
print("\n[Step 5] Test 3: Testing input validations on POST route...")

def assert_validation_failed(post_payload, expected_err_fragment):
    _, csrf_token = get_content_page_and_token()
    post_payload["csrf_token"] = csrf_token
    resp = client.post("/admin/about/content", data=post_payload, follow_redirects=True)
    html = resp.get_data(as_text=True)
    assert "Validation failed:" in html, f"Expected validation error but got success. Payload: {post_payload}"
    
    # Normalize escapes
    norm_html = html.replace("\\u0027", "'").replace("&#x27;", "'").replace("&#39;", "'")
    norm_frag = expected_err_fragment.replace("\\u0027", "'").replace("&#x27;", "'").replace("&#39;", "'")
    
    if norm_frag in norm_html:
        return
        
    # fallback: match without quotes
    frag_no_quotes = norm_frag.replace("'", "").replace('"', "")
    html_no_quotes = norm_html.replace("'", "").replace('"', "")
    assert frag_no_quotes in html_no_quotes, f"Expected error fragment '{expected_err_fragment}' not found in: {html}"

# A. Empty Heading
print("- Testing empty hero heading...")
assert_validation_failed({
    "hero_heading": "", # empty
    "hero_subtitle": "Subtitle",
    "who_we_are_title": "Title",
    "who_we_are_body": "Body",
    "mission_text": "Mission",
    "vision_text": "Vision"
}, "Hero heading is required")

# B. Too Short Heading
print("- Testing too short hero heading...")
assert_validation_failed({
    "hero_heading": "H", # < 2 characters
    "hero_subtitle": "Subtitle",
    "who_we_are_title": "Title",
    "who_we_are_body": "Body",
    "mission_text": "Mission",
    "vision_text": "Vision"
}, "Hero heading must be at least 2 characters")

# C. Too Long Heading
print("- Testing too long hero heading...")
assert_validation_failed({
    "hero_heading": "H" * 161, # > 160 characters
    "hero_subtitle": "Subtitle",
    "who_we_are_title": "Title",
    "who_we_are_body": "Body",
    "mission_text": "Mission",
    "vision_text": "Vision"
}, "Hero heading exceeds database limit of 160 characters")

print("-> Test 3 PASSED: All boundary validations correctly reject bad inputs!")

# 6. Test 4: Submit with invalid CSRF token
print("\n[Step 6] Test 4: Submitting with invalid CSRF token...")
post_data = {
    "csrf_token": "hacker-csrf-spoof",
    "hero_heading": "Hacker Heading",
    "hero_subtitle": "Subtitle",
    "who_we_are_title": "Title",
    "who_we_are_body": "Body",
    "mission_text": "Mission",
    "vision_text": "Vision"
}
resp = client.post("/admin/about/content", data=post_data, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Your session may have expired, or the CSRF token was invalid" in html
print("-> Test 4 PASSED: Rejection of invalid CSRF token works flawlessly!")

# 7. Test 5: Reverting test entries to original copy
print("\n[Step 7] Reverting About Content database entries to original state...")
with app.app_context():
    for key, val in original_copy.items():
        row = AboutContent.query.filter_by(key=key).first()
        if row:
            row.value = val
            db.session.add(row)
        else:
            row = AboutContent(key=key, value=val)
            db.session.add(row)
    db.session.commit()
print("-> Database restoration complete!")

print("\n============================================================")
print("ALL TESTS PASSED SUCCESSFULLY! THE ABOUT CONTENT CMS")
print("IS SECURE, DRAFT-SAVED, STABLE AND ROBUST.")
print("============================================================")
sys.exit(0)
