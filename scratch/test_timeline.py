import os
import sys
import re

# Add root folder to python path
sys.path.insert(0, os.getcwd())

from app import create_app
from models import db
from models.about_timeline import AboutTimelineEntry

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

print("=== STARTING ABOUT TIMELINE SYSTEM VERIFICATION SUITE ===")

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

# Helper to execute GET on timeline page and fetch CSRF token
def get_timeline_page_and_token():
    resp = client.get("/admin/about/timeline")
    assert resp.status_code == 200, f"Failed to load timeline page, got {resp.status_code}"
    token = extract_csrf_token(resp.get_data(as_text=True))
    return resp, token

# 3. Test 1: Submit Form WITH full fields (Normal submission + Unicode)
print("\n[Step 3] Test 1: Submitting 'Create timeline entry' form with Emojis...")
_, csrf_token = get_timeline_page_and_token()
assert csrf_token is not None, "Could not extract CSRF token from timeline page!"

post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "year": "2026",
    "title": "Establishment of Advanced AI Center 🌟🤖",
    "description": "Launched the state-of-the-art AI and NEP-aligned Robotics hub in Agra.",
    "display_order": "1",
    "is_active": "1"
}

resp = client.post("/admin/about/timeline", data=post_data, follow_redirects=True)
assert resp.status_code == 200, f"POST request returned {resp.status_code} instead of 200"
html = resp.get_data(as_text=True)

# Assert that no CSRF or general 400 Bad Request error is shown
assert "400 Bad Request" not in html, "Failing with 400 Bad Request!"
assert "Your session may have expired, or the CSRF token was invalid" not in html, "CSRF error was triggered!"
assert "Timeline entry saved successfully." in html, "Success flash message was missing!"

# Verify entry in the database
with app.app_context():
    entry = AboutTimelineEntry.query.filter_by(title="Establishment of Advanced AI Center 🌟🤖").first()
    assert entry is not None, "Timeline entry was not saved to the database!"
    assert entry.year == "2026", "Year mismatch"
    assert entry.display_order == 1, "Display order mismatch"
    assert entry.is_active is True, "Active status mismatch"
    assert "Agra" in entry.description, "Description mismatch"
    print("-> Test 1 PASSED: Timeline entry saved successfully with emojis!")

# 4. Test 2: Testing input validations on POST route
print("\n[Step 4] Test 2: Testing input validations on POST route...")

def assert_validation_failed(post_payload, expected_err_fragment):
    _, csrf_token = get_timeline_page_and_token()
    post_payload["csrf_token"] = csrf_token
    resp = client.post("/admin/about/timeline", data=post_payload, follow_redirects=True)
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

# A. Empty Year
print("- Testing empty year...")
assert_validation_failed({
    "item_id": "",
    "year": "", # empty
    "title": "Valid Title",
    "description": "Some description",
    "display_order": "0",
    "is_active": "1"
}, "Year is required")

# B. Non-numeric Year
print("- Testing non-numeric year...")
assert_validation_failed({
    "item_id": "",
    "year": "2026A", # not digits
    "title": "Valid Title",
    "description": "Some description",
    "display_order": "0",
    "is_active": "1"
}, "Year must contain only digits")

# C. Too Short Year
print("- Testing too short year...")
assert_validation_failed({
    "item_id": "",
    "year": "202", # < 4 chars
    "title": "Valid Title",
    "description": "Some description",
    "display_order": "0",
    "is_active": "1"
}, "Year must be between 4 and 8 characters")

# D. Too Long Year
print("- Testing too long year...")
assert_validation_failed({
    "item_id": "",
    "year": "202620262", # > 8 chars
    "title": "Valid Title",
    "description": "Some description",
    "display_order": "0",
    "is_active": "1"
}, "Year must be between 4 and 8 characters")

# E. Empty/Short Title
print("- Testing empty/short title...")
assert_validation_failed({
    "item_id": "",
    "year": "2026",
    "title": "T", # too short
    "description": "Some description",
    "display_order": "0",
    "is_active": "1"
}, "Timeline title must be at least 2 characters")

# F. Too Long Title
print("- Testing too long title...")
assert_validation_failed({
    "item_id": "",
    "year": "2026",
    "title": "T" * 161, # > 160 chars
    "description": "Some description",
    "display_order": "0",
    "is_active": "1"
}, "Timeline title exceeds database limit of 160 characters")

# G. Negative Display Order
print("- Testing negative display order...")
assert_validation_failed({
    "item_id": "",
    "year": "2026",
    "title": "Valid Title",
    "description": "Some description",
    "display_order": "-1", # negative
    "is_active": "1"
}, "Display order must be a non-negative integer")

print("-> Test 2 PASSED: All boundary validations correctly reject bad inputs!")

# 5. Test 3: Submit with invalid CSRF token
print("\n[Step 5] Test 3: Submitting with invalid CSRF token...")
post_data = {
    "csrf_token": "hacker-csrf-spoof",
    "item_id": "",
    "year": "2026",
    "title": "Hacker entry",
    "description": "Exploit timeline",
    "display_order": "0",
    "is_active": "1"
}
resp = client.post("/admin/about/timeline", data=post_data, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Your session may have expired, or the CSRF token was invalid" in html
print("-> Test 3 PASSED: Rejection of invalid CSRF token works flawlessly!")

# 6. Test 4: Deleting Timeline Entry
print("\n[Step 6] Test 4: Deleting timeline entry...")
with app.app_context():
    entry = AboutTimelineEntry.query.filter_by(title="Establishment of Advanced AI Center 🌟🤖").first()
    assert entry is not None, "Timeline entry to delete does not exist!"
    entry_id = entry.id

# Submit delete POST request
_, csrf_token = get_timeline_page_and_token()
resp = client.post(f"/admin/about/timeline/{entry_id}/delete", data={"csrf_token": csrf_token}, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Timeline entry deleted successfully." in html

with app.app_context():
    entry = AboutTimelineEntry.query.get(entry_id)
    assert entry is None, "Timeline entry was not deleted from database!"
print("-> Test 4 PASSED: Deleting timeline entry performs correctly!")

# 7. Clean up test database entries
print("\n[Step 7] Cleaning up other test timeline entries...")
with app.app_context():
    test_entries = AboutTimelineEntry.query.filter(AboutTimelineEntry.title.in_([
        "Establishment of Advanced AI Center 🌟🤖",
        "Hacker entry",
        "Valid Title"
    ])).all()
    for item in test_entries:
        db.session.delete(item)
    db.session.commit()
    print("-> Cleanup complete!")

print("\n============================================================")
print("ALL TESTS PASSED SUCCESSFULLY! THE TIMELINE ADMIN SYSTEM")
print("IS SECURE, EMOJI-COMPATIBLE, STABLE AND ROBUST.")
print("============================================================")
sys.exit(0)
