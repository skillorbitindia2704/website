import os
import sys
import re
import io

# Add root folder to python path
sys.path.insert(0, os.getcwd())

from app import create_app
from models import db
from models.about_team import AboutTeamMember

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

print("=== STARTING ABOUT TEAM SYSTEM VERIFICATION SUITE ===")

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

# Helper to execute GET on team page and fetch CSRF token
def get_team_page_and_token():
    resp = client.get("/admin/about/team")
    assert resp.status_code == 200, f"Failed to load team page, got {resp.status_code}"
    token = extract_csrf_token(resp.get_data(as_text=True))
    return resp, token

# 3. Test 1: Submit Form WITH full fields (Normal submission + Unicode)
print("\n[Step 3] Test 1: Submitting 'Create team member' form with Emojis and URLs...")
_, csrf_token = get_team_page_and_token()
assert csrf_token is not None, "Could not extract CSRF token from team page!"

post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "name": "Dr. Rohán D'Souza 🚀",
    "role": "Principal AI Scientist 🤖",
    "bio": "Leading our advanced AI initiatives with 10+ years experience... 🌟",
    "linkedin_url": "https://linkedin.com/in/rohan-dsouza",
    "github_url": "https://github.com/rohan-dsouza",
    "instagram_url": "https://instagram.com/rohan_dsouza",
    "display_order": "1",
    "is_active": "1",
    "image": (io.BytesIO(b""), "") # Empty optional image
}

resp = client.post("/admin/about/team", data=post_data, follow_redirects=True)
assert resp.status_code == 200, f"POST request returned {resp.status_code} instead of 200"
html = resp.get_data(as_text=True)

# Assert no CSRF or general 400 Bad Request error is shown
assert "400 Bad Request" not in html, "Failing with 400 Bad Request!"
assert "Your session may have expired, or the CSRF token was invalid" not in html, "CSRF error was triggered!"
assert "Team member saved successfully." in html, "Success flash message was missing!"

# Verify entry in the database
with app.app_context():
    member = AboutTeamMember.query.filter_by(name="Dr. Rohán D'Souza 🚀").first()
    assert member is not None, "Team member was not saved to the database!"
    assert member.role == "Principal AI Scientist 🤖", "Role mismatch"
    assert member.display_order == 1, "Display order mismatch"
    assert member.is_active is True, "Active status mismatch"
    assert member.linkedin_url == "https://linkedin.com/in/rohan-dsouza", "LinkedIn URL mismatch"
    assert member.github_url == "https://github.com/rohan-dsouza", "GitHub URL mismatch"
    assert member.instagram_url == "https://instagram.com/rohan_dsouza", "Instagram URL mismatch"
    assert "advanced AI" in member.bio, "Bio mismatch"
    print("-> Test 1 PASSED: Team member saved successfully with emojis!")

# 4. Test 2: Submit Form WITH image upload
print("\n[Step 4] Test 2: Submitting 'Create team member' form with Profile Image upload...")
_, csrf_token = get_team_page_and_token()

post_data_with_image = {
    "csrf_token": csrf_token,
    "item_id": "",
    "name": "Prof. S. R. Sharma 🎓",
    "role": "Dean of Engineering 🏫",
    "bio": "Expert in Computer Vision and Neural Networks.",
    "linkedin_url": "https://linkedin.com/in/sr-sharma",
    "github_url": "",
    "instagram_url": "",
    "display_order": "2",
    "is_active": "1",
    "image": (io.BytesIO(b"fake PNG image header data"), "sr_sharma_avatar.png")
}

resp = client.post("/admin/about/team", data=post_data_with_image, follow_redirects=True)
assert resp.status_code == 200, f"POST request returned {resp.status_code} instead of 200"
html = resp.get_data(as_text=True)

assert "Team member saved successfully." in html, "Success flash message was missing!"

# Verify entry and file existence in database
with app.app_context():
    member = AboutTeamMember.query.filter_by(name="Prof. S. R. Sharma 🎓").first()
    assert member is not None, "Team member with image was not saved!"
    assert member.image_path != "", "Image path was not stored!"
    assert "uploads/ai_lab/about/team" in member.image_path, f"Unexpected image path structure: {member.image_path}"
    
    # Check if file exists on disk
    abs_image_path = os.path.join(app.static_folder, member.image_path.replace("/", os.sep))
    assert os.path.exists(abs_image_path), f"Uploaded image does not exist on disk at: {abs_image_path}"
    print("-> Test 2 PASSED: Saved successfully with uploaded profile image file!")

# 5. Test 3: Testing input validations on POST route
print("\n[Step 5] Test 3: Testing input validations on POST route...")

def assert_validation_failed(post_payload, expected_err_fragment):
    _, csrf_token = get_team_page_and_token()
    post_payload["csrf_token"] = csrf_token
    # If image not provided in payload, mock it as empty
    if "image" not in post_payload:
        post_payload["image"] = (io.BytesIO(b""), "")
    resp = client.post("/admin/about/team", data=post_payload, follow_redirects=True)
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

# A. Empty Name
print("- Testing empty name...")
assert_validation_failed({
    "item_id": "",
    "name": "", # empty
    "role": "AI Engineer",
    "display_order": "0",
    "is_active": "1"
}, "Team member name is required")

# B. Too Short Name
print("- Testing too short name...")
assert_validation_failed({
    "item_id": "",
    "name": "A", # too short
    "role": "AI Engineer",
    "display_order": "0",
    "is_active": "1"
}, "Team member name must be at least 2 characters")

# C. Too Long Name
print("- Testing too long name...")
assert_validation_failed({
    "item_id": "",
    "name": "N" * 161, # > 160 chars
    "role": "AI Engineer",
    "display_order": "0",
    "is_active": "1"
}, "Team member name exceeds database limit of 160 characters")

# D. Empty Role
print("- Testing empty role...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Name",
    "role": "", # empty
    "display_order": "0",
    "is_active": "1"
}, "Team member role is required")

# E. Too Short Role
print("- Testing too short role...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Name",
    "role": "R", # too short
    "display_order": "0",
    "is_active": "1"
}, "Team member role must be at least 2 characters")

# F. Too Long Role
print("- Testing too long role...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Name",
    "role": "R" * 161, # > 160 chars
    "display_order": "0",
    "is_active": "1"
}, "Team member role exceeds database limit of 160 characters")

# G. Invalid URL Schema (LinkedIn)
print("- Testing invalid LinkedIn URL...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Name",
    "role": "Valid Role",
    "linkedin_url": "ftp://linkedin.com/hacker", # not HTTP/HTTPS
    "display_order": "0",
    "is_active": "1"
}, "LinkedIn URL must start with a valid HTTP or HTTPS protocol scheme")

# H. Invalid URL Schema (GitHub)
print("- Testing invalid GitHub URL...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Name",
    "role": "Valid Role",
    "github_url": "hacker-site.com", # no schema
    "display_order": "0",
    "is_active": "1"
}, "GitHub URL must start with a valid HTTP or HTTPS protocol scheme")

# I. Too Long URL
print("- Testing too long URL...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Name",
    "role": "Valid Role",
    "instagram_url": "https://instagram.com/" + "a"*245, # > 255 chars
    "display_order": "0",
    "is_active": "1"
}, "Instagram URL exceeds database limit of 255 characters")

# J. Negative Display Order
print("- Testing negative display order...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Name",
    "role": "Valid Role",
    "display_order": "-5", # negative
    "is_active": "1"
}, "Display order must be a non-negative integer")

# K. Invalid Image Extension
print("- Testing invalid profile image extension...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Name",
    "role": "Valid Role",
    "display_order": "0",
    "is_active": "1",
    "image": (io.BytesIO(b"hacker code"), "malicious_script.sh")
}, "File extension 'sh' not allowed")

# L. Oversized Image File
print("- Testing oversized profile image size limit (>5MB)...")
large_payload = b"0" * (5 * 1024 * 1024 + 100) # > 5MB
assert_validation_failed({
    "item_id": "",
    "name": "Valid Name",
    "role": "Valid Role",
    "display_order": "0",
    "is_active": "1",
    "image": (io.BytesIO(large_payload), "heavy_avatar.png")
}, "Profile image exceeds the maximum 5MB size limit")

print("-> Test 3 PASSED: All boundary validations correctly reject bad inputs!")

# 6. Test 4: Submit with invalid CSRF token
print("\n[Step 6] Test 4: Submitting with invalid CSRF token...")
post_data = {
    "csrf_token": "hacker-csrf-spoof",
    "item_id": "",
    "name": "Hacker Name",
    "role": "Hacker Role",
    "display_order": "0",
    "is_active": "1",
    "image": (io.BytesIO(b""), "")
}
resp = client.post("/admin/about/team", data=post_data, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Your session may have expired, or the CSRF token was invalid" in html
print("-> Test 4 PASSED: Rejection of invalid CSRF token works flawlessly!")

# 7. Test 5: Deleting Team Member
print("\n[Step 7] Test 5: Deleting team member entries...")
with app.app_context():
    member1 = AboutTeamMember.query.filter_by(name="Dr. Rohán D'Souza 🚀").first()
    assert member1 is not None, "Member 1 does not exist!"
    member1_id = member1.id

    member2 = AboutTeamMember.query.filter_by(name="Prof. S. R. Sharma 🎓").first()
    assert member2 is not None, "Member 2 does not exist!"
    member2_id = member2.id

# Submit delete POST request for Member 1
_, csrf_token = get_team_page_and_token()
resp = client.post(f"/admin/about/team/{member1_id}/delete", data={"csrf_token": csrf_token}, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Team member deleted successfully." in html

with app.app_context():
    member = AboutTeamMember.query.get(member1_id)
    assert member is None, "Team member 1 was not deleted from database!"

# Submit delete POST request for Member 2
_, csrf_token = get_team_page_and_token()
resp = client.post(f"/admin/about/team/{member2_id}/delete", data={"csrf_token": csrf_token}, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Team member deleted successfully." in html

with app.app_context():
    member = AboutTeamMember.query.get(member2_id)
    assert member is None, "Team member 2 was not deleted from database!"

print("-> Test 5 PASSED: Deleting team members performs correctly!")

# 8. Clean up uploaded assets and test database entries
print("\n[Step 8] Cleaning up uploaded test files and DB records...")
with app.app_context():
    test_members = AboutTeamMember.query.filter(AboutTeamMember.name.in_([
        "Dr. Rohán D'Souza 🚀",
        "Prof. S. R. Sharma 🎓",
        "Valid Name",
        "Hacker Name"
    ])).all()
    for m in test_members:
        if m.image_path:
            abs_image_path = os.path.join(app.static_folder, m.image_path.replace("/", os.sep))
            if os.path.exists(abs_image_path):
                os.remove(abs_image_path)
                print(f"-> Removed test file: {abs_image_path}")
        db.session.delete(m)
    db.session.commit()
    print("-> Cleanup complete!")

print("\n============================================================")
print("ALL TESTS PASSED SUCCESSFULLY! THE TEAM ADMIN SYSTEM")
print("IS SECURE, EMOJI-COMPATIBLE, STABLE AND ROBUST.")
print("============================================================")
sys.exit(0)
