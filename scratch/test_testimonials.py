import os
import sys
import re

# Add root folder to python path
sys.path.insert(0, os.getcwd())

from app import create_app
from models import db
from models.about_testimonial import AboutTestimonial

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

print("=== STARTING ABOUT TESTIMONIAL SYSTEM VERIFICATION SUITE ===")

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

# Helper to execute GET on testimonials page and fetch CSRF token
def get_testimonials_page_and_token():
    resp = client.get("/admin/about/testimonials")
    assert resp.status_code == 200, f"Failed to load testimonials page, got {resp.status_code}"
    token = extract_csrf_token(resp.get_data(as_text=True))
    return resp, token

# 3. Test 1: Submit Form WITH emojis and full fields (Normal submission + Unicode)
print("\n[Step 3] Test 1: Submitting 'Add testimonial' form with Emojis and full fields...")
_, csrf_token = get_testimonials_page_and_token()
assert csrf_token is not None, "Could not extract CSRF token from testimonials page!"

post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "name": "Rohan 🌟",
    "city": "Mumbai 🇮🇳",
    "course_name": "Advanced Python & AI 🎓🤖",
    "rating": "5",
    "display_order": "1",
    "is_active": "1",
    "feedback": "Absolutely brilliant training course! Explanations were extremely clear. 🚀"
}

resp = client.post("/admin/about/testimonials", data=post_data, follow_redirects=True)
assert resp.status_code == 200, f"POST request returned {resp.status_code} instead of 200 (follow redirect)"
html = resp.get_data(as_text=True)

# Assert that no CSRF or general 400 Bad Request error is shown
assert "400 Bad Request" not in html, "Failing with 400 Bad Request!"
assert "Your session may have expired, or the CSRF token was invalid" not in html, "CSRF error was triggered!"
assert "Testimonial saved successfully." in html, "Success flash message was missing!"

# Verify entry in the database
with app.app_context():
    testi = AboutTestimonial.query.filter_by(name="Rohan 🌟").first()
    assert testi is not None, "Testimonial was not saved to the database!"
    assert testi.city == "Mumbai 🇮🇳", "City mismatch"
    assert testi.course_name == "Advanced Python & AI 🎓🤖", "Course name mismatch"
    assert testi.rating == 5, "Rating mismatch"
    assert testi.display_order == 1, "Display order mismatch"
    assert testi.is_active is True, "Active status mismatch"
    assert "Absolutely brilliant" in testi.feedback, "Feedback content mismatch"
    print("-> Test 1 PASSED: Testimonial saved successfully with emojis and all fields!")

# 4. Test 2: Submit Form with empty optional fields
print("\n[Step 4] Test 2: Submitting testimonial with empty optional fields (city, course_name)...")
_, csrf_token = get_testimonials_page_and_token()
post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "name": "Amit Sharma",
    "city": "",
    "course_name": "",
    "rating": "4",
    "display_order": "2",
    "is_active": "1",
    "feedback": "Highly recommended platform for tech enthusiasts."
}

resp = client.post("/admin/about/testimonials", data=post_data, follow_redirects=True)
assert resp.status_code == 200
html = resp.get_data(as_text=True)
assert "Testimonial saved successfully." in html

with app.app_context():
    testi = AboutTestimonial.query.filter_by(name="Amit Sharma").first()
    assert testi is not None, "Testimonial not found in database!"
    assert testi.city == "", f"Expected empty city, got '{testi.city}'"
    assert testi.course_name == "", f"Expected empty course, got '{testi.course_name}'"
    print("-> Test 2 PASSED: Saved successfully with empty optional fields!")

# 5. Test 3: Submit Form with extremely long feedback text
print("\n[Step 5] Test 3: Submitting testimonial with long feedback text...")
_, csrf_token = get_testimonials_page_and_token()
long_feedback = ("Very detailed review. " * 150).strip() # 3000 chars (stripped)

post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "name": "Jane Doe",
    "city": "London",
    "course_name": "Full Stack Development",
    "rating": "5",
    "display_order": "3",
    "is_active": "1",
    "feedback": long_feedback
}

resp = client.post("/admin/about/testimonials", data=post_data, follow_redirects=True)
assert resp.status_code == 200
html = resp.get_data(as_text=True)
assert "Testimonial saved successfully." in html

with app.app_context():
    testi = AboutTestimonial.query.filter_by(name="Jane Doe").first()
    assert testi is not None
    assert len(testi.feedback) == len(long_feedback), f"Feedback length mismatch: expected {len(long_feedback)}, got {len(testi.feedback)}"
    print("-> Test 3 PASSED: Long feedback text saved successfully without truncation or errors!")

# 6. Test 4: Testing robust input boundary validations
print("\n[Step 6] Test 4: Testing input validations on POST route...")

def assert_validation_failed(post_payload, expected_err_fragment):
    _, csrf_token = get_testimonials_page_and_token()
    post_payload["csrf_token"] = csrf_token
    resp = client.post("/admin/about/testimonials", data=post_payload, follow_redirects=True)
    html = resp.get_data(as_text=True)
    assert "Validation failed:" in html, f"Expected validation error but got success. Payload: {post_payload}"
    assert expected_err_fragment in html, f"Expected error fragment '{expected_err_fragment}' not found in: {html}"

# A. Empty/Short Name
print("- Testing empty/short name...")
assert_validation_failed({
    "item_id": "",
    "name": "A", # too short
    "city": "Test",
    "course_name": "Test",
    "rating": "5",
    "display_order": "0",
    "is_active": "1",
    "feedback": "Valid feedback content is here"
}, "Name must be at least 2 characters")

# B. Too Long Name
print("- Testing too long name...")
assert_validation_failed({
    "item_id": "",
    "name": "A" * 161, # > 160
    "city": "Test",
    "course_name": "Test",
    "rating": "5",
    "display_order": "0",
    "is_active": "1",
    "feedback": "Valid feedback content is here"
}, "Name exceeds database limit of 160 characters")

# C. Too Long City
print("- Testing too long city...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Name",
    "city": "C" * 121, # > 120
    "course_name": "Test",
    "rating": "5",
    "display_order": "0",
    "is_active": "1",
    "feedback": "Valid feedback content is here"
}, "City exceeds database limit of 120 characters")

# D. Too Long Course Name
print("- Testing too long course name...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Name",
    "city": "Valid City",
    "course_name": "P" * 201, # > 200
    "rating": "5",
    "display_order": "0",
    "is_active": "1",
    "feedback": "Valid feedback content is here"
}, "Course name exceeds database limit of 200 characters")

# E. Empty/Short Feedback
print("- Testing empty/short feedback...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Name",
    "city": "Valid City",
    "course_name": "Valid Course",
    "rating": "5",
    "display_order": "0",
    "is_active": "1",
    "feedback": "Shrt" # < 5
}, "Feedback must be at least 5 characters")

# F. Out of Bounds Rating
print("- Testing out of bounds rating...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Name",
    "city": "Valid City",
    "course_name": "Valid Course",
    "rating": "6", # out of range 1-5
    "display_order": "0",
    "is_active": "1",
    "feedback": "Valid feedback content is here"
}, "Rating must be an integer between 1 and 5")

# G. Negative Display Order
print("- Testing negative display order...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Name",
    "city": "Valid City",
    "course_name": "Valid Course",
    "rating": "5",
    "display_order": "-1", # negative
    "is_active": "1",
    "feedback": "Valid feedback content is here"
}, "Display order must be a non-negative integer")

print("-> Test 4 PASSED: All boundary validations correctly reject bad inputs and return helpful user messages!")

# 7. Test 5: Submit with invalid CSRF token (CSRF rejection & session mismatch)
print("\n[Step 7] Test 5: Submitting with invalid CSRF token...")
post_data = {
    "csrf_token": "hacker-csrf-spoof",
    "item_id": "",
    "name": "Hacker",
    "city": "DarkWeb",
    "course_name": "Exploiting 101",
    "rating": "1",
    "display_order": "0",
    "is_active": "1",
    "feedback": "This should be blocked immediately."
}
resp = client.post("/admin/about/testimonials", data=post_data, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Your session may have expired, or the CSRF token was invalid" in html
print("-> Test 5 PASSED: Rejection of invalid CSRF token works flawlessly!")

# 8. Test 6: Deleting Testimonial
print("\n[Step 8] Test 6: Deleting testimonial...")
with app.app_context():
    testi = AboutTestimonial.query.filter_by(name="Amit Sharma").first()
    assert testi is not None, "Testimonial to delete does not exist!"
    testi_id = testi.id

# Submit delete POST request
_, csrf_token = get_testimonials_page_and_token()
resp = client.post(f"/admin/about/testimonials/{testi_id}/delete", data={"csrf_token": csrf_token}, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Testimonial deleted successfully." in html

with app.app_context():
    testi = AboutTestimonial.query.get(testi_id)
    assert testi is None, "Testimonial was not deleted from database!"
print("-> Test 6 PASSED: Deleting testimonial performs correctly and database cleans up safely!")

# 9. Clean up test database entries
print("\n[Step 9] Cleaning up other test testimonials from database...")
with app.app_context():
    AboutTestimonial.query.filter(AboutTestimonial.name.in_(["Rohan 🌟", "Amit Sharma", "Jane Doe", "Hacker", "Valid Name"])).delete()
    db.session.commit()
    print("-> Cleanup complete!")

print("\n============================================================")
print("ALL TESTS PASSED SUCCESSFULLY! THE TESTIMONIAL ADMIN SYSTEM")
print("IS SECURE, EMOJI-COMPATIBLE, STABLE AND ROBUST.")
print("============================================================")
sys.exit(0)
