import os
import sys
import re
import io

# Add root folder to python path
sys.path.insert(0, os.getcwd())

from app import create_app
from models import db
from models.about_partner import AboutPartnerLogo

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

print("=== STARTING ABOUT PARTNER SYSTEM VERIFICATION SUITE ===")

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

# Helper to execute GET on partners page and fetch CSRF token
def get_partners_page_and_token():
    resp = client.get("/admin/about/partners")
    assert resp.status_code == 200, f"Failed to load partners page, got {resp.status_code}"
    token = extract_csrf_token(resp.get_data(as_text=True))
    return resp, token

# 3. Test 1: Submit Form WITH logo upload and full fields (Normal submission + Unicode)
print("\n[Step 3] Test 1: Submitting 'Add partner' form with Emojis and logo upload...")
_, csrf_token = get_partners_page_and_token()
assert csrf_token is not None, "Could not extract CSRF token from partners page!"

post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "name": "Google AI Labs 🌟",
    "url": "https://ai.google",
    "display_order": "1",
    "is_active": "1",
    "logo": (io.BytesIO(b"fake PNG header data"), "google_logo.png")
}

resp = client.post("/admin/about/partners", data=post_data, content_type="multipart/form-data", follow_redirects=True)
assert resp.status_code == 200, f"POST request returned {resp.status_code} instead of 200"
html = resp.get_data(as_text=True)

# Assert that no CSRF or general 400 Bad Request error is shown
assert "400 Bad Request" not in html, "Failing with 400 Bad Request!"
assert "Your session may have expired, or the CSRF token was invalid" not in html, "CSRF error was triggered!"
assert "Partner saved successfully." in html, "Success flash message was missing!"

# Verify entry in the database
with app.app_context():
    partner = AboutPartnerLogo.query.filter_by(name="Google AI Labs 🌟").first()
    assert partner is not None, "Partner was not saved to the database!"
    assert partner.url == "https://ai.google", "URL mismatch"
    assert partner.display_order == 1, "Display order mismatch"
    assert partner.is_active is True, "Active status mismatch"
    assert "uploads/ai_lab/about/partners" in partner.logo_path, f"Unexpected logo path: {partner.logo_path}"
    print("-> Test 1 PASSED: Partner saved successfully with emojis and logo!")

# 4. Test 2: Submit Form without logo upload (empty optional logo)
print("\n[Step 4] Test 2: Submitting partner without optional logo...")
_, csrf_token = get_partners_page_and_token()
post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "name": "Microsoft India",
    "url": "https://microsoft.com/en-in",
    "display_order": "2",
    "is_active": "1",
    "logo": (io.BytesIO(b""), "") # Empty file
}

resp = client.post("/admin/about/partners", data=post_data, content_type="multipart/form-data", follow_redirects=True)
assert resp.status_code == 200
html = resp.get_data(as_text=True)
assert "Partner saved successfully." in html

with app.app_context():
    partner = AboutPartnerLogo.query.filter_by(name="Microsoft India").first()
    assert partner is not None, "Partner without logo not found in database!"
    assert partner.logo_path == "", f"Expected empty logo path, got '{partner.logo_path}'"
    print("-> Test 2 PASSED: Saved successfully with empty optional logo!")

# 5. Test 3: Testing input validations on POST route
print("\n[Step 5] Test 3: Testing input validations on POST route...")

def assert_validation_failed(post_payload, expected_err_fragment):
    _, csrf_token = get_partners_page_and_token()
    post_payload["csrf_token"] = csrf_token
    resp = client.post("/admin/about/partners", data=post_payload, content_type="multipart/form-data", follow_redirects=True)
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


# A. Empty/Short Name
print("- Testing empty/short name...")
assert_validation_failed({
    "item_id": "",
    "name": "A", # too short
    "url": "https://test.com",
    "display_order": "0",
    "is_active": "1"
}, "Partner name must be at least 2 characters")

# B. Too Long Name
print("- Testing too long name...")
assert_validation_failed({
    "item_id": "",
    "name": "N" * 121, # > 120
    "url": "https://test.com",
    "display_order": "0",
    "is_active": "1"
}, "Partner name exceeds database limit of 120 characters")

# C. Too Long URL
print("- Testing too long URL...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Partner",
    "url": "https://" + "U" * 250 + ".com", # > 255
    "display_order": "0",
    "is_active": "1"
}, "URL exceeds database limit of 255 characters")

# D. Bad URL Format
print("- Testing bad URL formats...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Partner",
    "url": "ftp://bad-schema.com", # not http or https
    "display_order": "0",
    "is_active": "1"
}, "URL must start with a valid HTTP or HTTPS protocol scheme")

assert_validation_failed({
    "item_id": "",
    "name": "Valid Partner",
    "url": "not-a-valid-url-format", 
    "display_order": "0",
    "is_active": "1"
}, "URL must start with a valid HTTP or HTTPS protocol scheme")

# E. Negative Display Order
print("- Testing negative display order...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Partner",
    "url": "https://valid-url.com",
    "display_order": "-1", # negative
    "is_active": "1"
}, "Display order must be a non-negative integer")

# F. Invalid File Extension for Logo Upload
print("- Testing invalid file extensions...")
assert_validation_failed({
    "item_id": "",
    "name": "Valid Partner",
    "url": "https://valid-url.com",
    "display_order": "0",
    "is_active": "1",
    "logo": (io.BytesIO(b"dangerous code"), "malicious_script.sh") # Shell script extension
}, "File extension 'sh' not allowed")

# G. Large Logo File upload rejection (>5MB)
print("- Testing file size limits (>5MB)...")
large_payload = b"0" * (6 * 1024 * 1024) # 6MB
assert_validation_failed({
    "item_id": "",
    "name": "Valid Partner",
    "url": "https://valid-url.com",
    "display_order": "0",
    "is_active": "1",
    "logo": (io.BytesIO(large_payload), "heavy_image.png")
}, "Logo file exceeds the maximum 5MB size limit")

print("-> Test 3 PASSED: All boundary validations correctly reject bad inputs and return helpful user messages!")

# 6. Test 4: Submit with invalid CSRF token (CSRF rejection & session mismatch)
print("\n[Step 6] Test 4: Submitting with invalid CSRF token...")
post_data = {
    "csrf_token": "hacker-csrf-spoof",
    "item_id": "",
    "name": "Hacker Partner",
    "url": "https://hacker.com",
    "display_order": "0",
    "is_active": "1"
}
resp = client.post("/admin/about/partners", data=post_data, content_type="multipart/form-data", follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Your session may have expired, or the CSRF token was invalid" in html
print("-> Test 4 PASSED: Rejection of invalid CSRF token works flawlessly!")

# 7. Test 5: Deleting Partner
print("\n[Step 7] Test 5: Deleting partner...")
with app.app_context():
    partner = AboutPartnerLogo.query.filter_by(name="Microsoft India").first()
    assert partner is not None, "Partner to delete does not exist!"
    partner_id = partner.id

# Submit delete POST request
_, csrf_token = get_partners_page_and_token()
resp = client.post(f"/admin/about/partners/{partner_id}/delete", data={"csrf_token": csrf_token}, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Partner deleted successfully." in html

with app.app_context():
    partner = AboutPartnerLogo.query.get(partner_id)
    assert partner is None, "Partner was not deleted from database!"
print("-> Test 5 PASSED: Deleting partner performs correctly and database cleans up safely!")

# 8. Clean up test database entries and static files
print("\n[Step 8] Cleaning up other test partners and files...")
with app.app_context():
    test_partners = AboutPartnerLogo.query.filter(AboutPartnerLogo.name.in_(["Google AI Labs 🌟", "Microsoft India", "Hacker Partner", "Valid Partner"])).all()
    for p in test_partners:
        if p.logo_path:
            abs_logo_path = os.path.join(app.static_folder, p.logo_path.replace("/", os.sep))
            if os.path.exists(abs_logo_path):
                try:
                    os.remove(abs_logo_path)
                except Exception:
                    pass
        db.session.delete(p)
    db.session.commit()
    print("-> Cleanup complete!")

print("\n============================================================")
print("ALL TESTS PASSED SUCCESSFULLY! THE PARTNER ADMIN SYSTEM")
print("IS SECURE, EMOJI-COMPATIBLE, STABLE AND ROBUST.")
print("============================================================")
sys.exit(0)
