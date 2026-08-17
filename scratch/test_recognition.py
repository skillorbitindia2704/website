import os
import sys
import re

# Add root folder to python path
sys.path.insert(0, os.getcwd())

from app import create_app
from models import db
from models.about_recognition import AboutRecognition

# Ensure testing configuration is active but keep CSRF enabled to test CSRF validation!
app = create_app()
app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = True

client = app.test_client()

def extract_csrf_token(html_content):
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html_content)
    if match:
        return match.group(1)
    # Try different quote patterns
    match = re.search(r"name='csrf_token'\s+value='([^']+)'", html_content)
    if match:
        return match.group(1)
    return None

print("=== STARTING RECOGNITION BADGE SYSTEM VERIFICATION SUITE ===")

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

# Helper to execute GET on recognition page and fetch CSRF token
def get_recognition_page_and_token():
    resp = client.get("/admin/about/recognition")
    assert resp.status_code == 200, f"Failed to load recognition page, got {resp.status_code}"
    token = extract_csrf_token(resp.get_data(as_text=True))
    return resp, token

# 3. Test 1: Submit Form WITH emojis and full fields
print("\n[Step 3] Test 1: Submitting 'Add recognition badge' form with Emoji and subtitle...")
_, csrf_token = get_recognition_page_and_token()
assert csrf_token is not None, "Could not extract CSRF token from recognition page!"

post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "title": "MSME Registered",
    "icon": "✅",
    "subtitle": "Government of India Udyam Registered Enterprise",
    "display_order": "5",
    "is_active": "1"
}

resp = client.post("/admin/about/recognition", data=post_data, follow_redirects=True)
assert resp.status_code == 200, f"POST request returned {resp.status_code} instead of 200 (follow redirect)"
html = resp.get_data(as_text=True)

# Assert that no 400 Bad Request error is shown
assert "400 Bad Request" not in html, "Failing with 400 Bad Request!"
assert "The server could not understand the request" not in html, "CSRF error was triggered!"
assert "Recognition item saved successfully." in html, "Success flash message was missing!"

# Verify entry in the database
with app.app_context():
    badge = AboutRecognition.query.filter_by(title="MSME Registered").first()
    assert badge is not None, "Badge was not saved to the database!"
    assert badge.icon == "✅", f"Badge icon mismatch: expected '✅', got '{badge.icon}'"
    assert badge.subtitle == "Government of India Udyam Registered Enterprise", "Subtitle mismatch"
    assert badge.display_order == 5, "Display order mismatch"
    assert badge.is_active is True, "Active status mismatch"
    print("-> Test 1 PASSED: Badge saved successfully with emoji, active status, display order, and subtitle!")

# 4. Test 2: Submit Form WITHOUT subtitle
print("\n[Step 4] Test 2: Submitting badge form without subtitle...")
_, csrf_token = get_recognition_page_and_token()
post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "title": "ISO Certified 9001",
    "icon": "🏢",
    "subtitle": "",
    "display_order": "10",
    "is_active": "1"
}

resp = client.post("/admin/about/recognition", data=post_data, follow_redirects=True)
assert resp.status_code == 200
html = resp.get_data(as_text=True)
assert "400 Bad Request" not in html
assert "Recognition item saved successfully." in html

with app.app_context():
    badge = AboutRecognition.query.filter_by(title="ISO Certified 9001").first()
    assert badge is not None, "Badge without subtitle not found in database!"
    assert badge.subtitle == "", f"Expected empty subtitle, got '{badge.subtitle}'"
    print("-> Test 2 PASSED: Saved successfully without subtitle!")

# 5. Test 3: Submit invalid inputs (empty title, invalid display order, too long subtitle)
print("\n[Step 5] Test 3: Testing robust validation against invalid inputs...")

# A. Empty Title
print("Submitting empty title...")
_, csrf_token = get_recognition_page_and_token()
post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "title": "",
    "icon": "❌",
    "subtitle": "Test",
    "display_order": "0",
    "is_active": "1"
}
resp = client.post("/admin/about/recognition", data=post_data, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Validation failed:" in html, "Failed to catch empty title validation error"
assert "Title cannot be empty" in html or "Title must be at least 2 characters" in html
print("-> Caught empty title correctly!")

# B. Too long title
print("Submitting too long title...")
_, csrf_token = get_recognition_page_and_token()
post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "title": "A" * 165,
    "icon": "❌",
    "subtitle": "Test",
    "display_order": "0",
    "is_active": "1"
}
resp = client.post("/admin/about/recognition", data=post_data, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Validation failed:" in html
assert "Title exceeds the limit of 160 characters" in html
print("-> Caught too long title correctly!")

# C. Invalid display order
print("Submitting negative/invalid display order...")
_, csrf_token = get_recognition_page_and_token()
post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "title": "Valid Title",
    "icon": "ℹ️",
    "subtitle": "Test",
    "display_order": "-5",
    "is_active": "1"
}
resp = client.post("/admin/about/recognition", data=post_data, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Validation failed:" in html
assert "Display order must be a non-negative integer" in html
print("-> Caught negative display order correctly!")

print("-> Test 3 PASSED: Input validation catches invalid values and rejects safely with user-friendly alerts!")

# 6. Test 4: Submit invalid CSRF token
print("\n[Step 6] Test 4: Submitting with invalid CSRF token...")
post_data = {
    "csrf_token": "invalid-token-12345",
    "item_id": "",
    "title": "Hacker Badge",
    "icon": "😈",
    "subtitle": "This should be rejected",
    "display_order": "0",
    "is_active": "1"
}
resp = client.post("/admin/about/recognition", data=post_data, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Your session may have expired, or the CSRF token was invalid" in html
print("-> Test 4 PASSED: Rejected invalid CSRF token safely with a custom error flash message instead of 400 Bad Request!")

# 7. Clean up test database entries
print("\n[Step 7] Cleaning up test badges from database...")
with app.app_context():
    AboutRecognition.query.filter(AboutRecognition.title.in_(["MSME Registered", "ISO Certified 9001", "Hacker Badge"])).delete()
    db.session.commit()
    print("-> Cleanup complete!")

print("\n============================================================")
print("ALL TESTS PASSED SUCCESSFULLY! THE RECOGNITION BADGE CREATION")
print("FLOW IS SECURE, EMOJI-COMPATIBLE, STABLE AND ROBUST.")
print("============================================================")
sys.exit(0)
