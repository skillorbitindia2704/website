import os
import sys
import re

# Add root folder to python path
sys.path.insert(0, os.getcwd())

from app import create_app
from models import db
from models.about_counter import AboutCounter

# Configure app for active CSRF testing
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

print("=== STARTING ACHIEVEMENT COUNTERS VERIFICATION SUITE ===")

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

assert login_resp.status_code == 200
assert b"Logout" in login_resp.data or b"Dashboard" in login_resp.data
print("-> Authentication successful!")

# Helper to execute GET on counters page and fetch CSRF token
def get_counters_page_and_token():
    resp = client.get("/admin/about/counters")
    assert resp.status_code == 200, f"Failed to load counters page, got {resp.status_code}"
    token = extract_csrf_token(resp.get_data(as_text=True))
    return resp, token

# 3. Test 1: Submit Form WITH emojis and full fields
print("\n[Step 3] Test 1: Submitting 'Add counter' form with Emoji, Suffix, and value...")
_, csrf_token = get_counters_page_and_token()
assert csrf_token is not None, "Could not extract CSRF token from counters page!"

post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "label": "Students Trained",
    "value": "500",
    "suffix": "+",
    "icon": "🎓",
    "display_order": "3",
    "is_active": "1"
}

resp = client.post("/admin/about/counters", data=post_data, follow_redirects=True)
assert resp.status_code == 200
html = resp.get_data(as_text=True)

# Assert that no 400 Bad Request error is shown
assert "400 Bad Request" not in html
assert "Counter saved successfully." in html

# Verify entry in the database
with app.app_context():
    counter = AboutCounter.query.filter_by(label="Students Trained").first()
    assert counter is not None, "Counter was not saved to database!"
    assert counter.icon == "🎓", f"Counter icon mismatch: expected '🎓', got '{counter.icon}'"
    assert counter.value == 500, "Value mismatch"
    assert counter.suffix == "+", "Suffix mismatch"
    assert counter.display_order == 3, "Display order mismatch"
    assert counter.is_active is True, "Active status mismatch"
    print("-> Test 1 PASSED: Counter saved successfully with emoji, value, suffix, and active status!")

# 4. Test 2: Submit Form with zero values/other emojis
print("\n[Step 4] Test 2: Submitting counter form with 0 value and other emoji...")
_, csrf_token = get_counters_page_and_token()
post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "label": "Zero Test",
    "value": "0",
    "suffix": "%",
    "icon": "🤖",
    "display_order": "100",
    "is_active": "0"
}

resp = client.post("/admin/about/counters", data=post_data, follow_redirects=True)
assert resp.status_code == 200
html = resp.get_data(as_text=True)
assert "400 Bad Request" not in html
assert "Counter saved successfully." in html

with app.app_context():
    counter = AboutCounter.query.filter_by(label="Zero Test").first()
    assert counter is not None
    assert counter.value == 0
    assert counter.is_active is False
    print("-> Test 2 PASSED: Saved successfully with 0 value and disabled active status!")

# 5. Test 3: Submit invalid inputs (empty label, too long suffix, negative value)
print("\n[Step 5] Test 3: Testing robust validation against invalid inputs...")

# A. Empty Label
print("Submitting empty label...")
_, csrf_token = get_counters_page_and_token()
post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "label": "",
    "value": "10",
    "suffix": "+",
    "icon": "🚀",
    "display_order": "0",
    "is_active": "1"
}
resp = client.post("/admin/about/counters", data=post_data, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Validation failed:" in html
assert "Label cannot be empty" in html or "Label must be at least 2 characters" in html
print("-> Caught empty label correctly!")

# B. Too long label
print("Submitting too long label...")
_, csrf_token = get_counters_page_and_token()
post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "label": "L" * 125,
    "value": "10",
    "suffix": "+",
    "icon": "🚀",
    "display_order": "0",
    "is_active": "1"
}
resp = client.post("/admin/about/counters", data=post_data, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Validation failed:" in html
assert "Label exceeds the limit of 120 characters" in html
print("-> Caught too long label correctly!")

# C. Negative value
print("Submitting negative value...")
_, csrf_token = get_counters_page_and_token()
post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "label": "Negative Value Test",
    "value": "-50",
    "suffix": "+",
    "icon": "🚀",
    "display_order": "0",
    "is_active": "1"
}
resp = client.post("/admin/about/counters", data=post_data, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Validation failed:" in html
assert "Value must be a non-negative integer" in html
print("-> Caught negative value correctly!")

print("-> Test 3 PASSED: Validation catches invalid labels, negative values, and overflows successfully!")

# 6. Test 4: Submit invalid CSRF token
print("\n[Step 6] Test 4: Submitting with invalid CSRF token...")
post_data = {
    "csrf_token": "hacked-token-999",
    "item_id": "",
    "label": "Hacker Counter",
    "value": "9999",
    "suffix": "x",
    "icon": "💀",
    "display_order": "0",
    "is_active": "1"
}
resp = client.post("/admin/about/counters", data=post_data, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Your session may have expired, or the CSRF token was invalid" in html
print("-> Test 4 PASSED: Rejected invalid CSRF token safely with standard flash message recovery!")

# 7. Clean up test database entries
print("\n[Step 7] Cleaning up test counters from database...")
with app.app_context():
    AboutCounter.query.filter(AboutCounter.label.in_(["Students Trained", "Zero Test", "Hacker Counter"])).delete()
    db.session.commit()
    print("-> Cleanup complete!")

print("\n============================================================")
print("ALL TESTS PASSED SUCCESSFULLY! THE ACHIEVEMENT COUNTER SYSTEM")
print("IS SECURE, EMOJI-COMPATIBLE, STABLE AND ROBUST.")
print("============================================================")
sys.exit(0)
