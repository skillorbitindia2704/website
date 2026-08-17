import os
import sys
import re
import io

# Add root folder to python path
sys.path.insert(0, os.getcwd())

from app import create_app
from models import db
from models.about_gallery import AboutGalleryImage

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

print("=== STARTING ABOUT GALLERY SYSTEM VERIFICATION SUITE ===")

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

# Helper to execute GET on gallery page and fetch CSRF token
def get_gallery_page_and_token():
    resp = client.get("/admin/about/gallery")
    assert resp.status_code == 200, f"Failed to load gallery page, got {resp.status_code}"
    token = extract_csrf_token(resp.get_data(as_text=True))
    return resp, token

# 3. Test 1: Submit Form WITH image upload and full fields (Normal submission + Unicode)
print("\n[Step 3] Test 1: Submitting 'Add gallery image' form with Emojis and image upload...")
_, csrf_token = get_gallery_page_and_token()
assert csrf_token is not None, "Could not extract CSRF token from gallery page!"

post_data = {
    "csrf_token": csrf_token,
    "item_id": "",
    "title": "Robotics Lab Launch 🤖🚀",
    "category": "Inauguration Events",
    "display_order": "5",
    "is_active": "1",
    "image": (io.BytesIO(b"fake JPEG header data"), "robot_lab.jpg")
}

resp = client.post("/admin/about/gallery", data=post_data, content_type="multipart/form-data", follow_redirects=True)
assert resp.status_code == 200, f"POST request returned {resp.status_code} instead of 200"
html = resp.get_data(as_text=True)

# Assert that no CSRF or general 400 Bad Request error is shown
assert "400 Bad Request" not in html, "Failing with 400 Bad Request!"
assert "Your session may have expired, or the CSRF token was invalid" not in html, "CSRF error was triggered!"
assert "Gallery image saved successfully." in html, "Success flash message was missing!"

# Verify entry in the database
with app.app_context():
    gallery_item = AboutGalleryImage.query.filter_by(title="Robotics Lab Launch 🤖🚀").first()
    assert gallery_item is not None, "Gallery item was not saved to the database!"
    assert gallery_item.category == "Inauguration Events", "Category mismatch"
    assert gallery_item.display_order == 5, "Display order mismatch"
    assert gallery_item.is_active is True, "Active status mismatch"
    assert "uploads/ai_lab/about/gallery" in gallery_item.image_path, f"Unexpected image path: {gallery_item.image_path}"
    print("-> Test 1 PASSED: Gallery image saved successfully with emojis and uploaded image!")

# 4. Test 2: Edit existing entry without optional image upload
print("\n[Step 4] Test 2: Editing gallery image details (retaining old image)...")
with app.app_context():
    gallery_item = AboutGalleryImage.query.filter_by(title="Robotics Lab Launch 🤖🚀").first()
    assert gallery_item is not None
    gallery_id = gallery_item.id
    old_image_path = gallery_item.image_path

_, csrf_token = get_gallery_page_and_token()
post_data = {
    "csrf_token": csrf_token,
    "item_id": str(gallery_id),
    "title": "Robotics Lab Launch v2 🤖",
    "category": "Tech Labs",
    "display_order": "8",
    "is_active": "0",
    "image": (io.BytesIO(b""), "")  # Empty file on edit
}

resp = client.post("/admin/about/gallery", data=post_data, content_type="multipart/form-data", follow_redirects=True)
assert resp.status_code == 200
html = resp.get_data(as_text=True)
assert "Gallery image saved successfully." in html

with app.app_context():
    gallery_item = AboutGalleryImage.query.get(gallery_id)
    assert gallery_item is not None
    assert gallery_item.title == "Robotics Lab Launch v2 🤖"
    assert gallery_item.category == "Tech Labs"
    assert gallery_item.display_order == 8
    assert gallery_item.is_active is False
    assert gallery_item.image_path == old_image_path, "Image path should have remained unchanged!"
    print("-> Test 2 PASSED: Edited successfully without overwriting old image!")

# 5. Test 3: Testing input validations on POST route
print("\n[Step 5] Test 3: Testing input validations on POST route...")

def assert_validation_failed(post_payload, expected_err_fragment):
    _, csrf_token = get_gallery_page_and_token()
    post_payload["csrf_token"] = csrf_token
    resp = client.post("/admin/about/gallery", data=post_payload, content_type="multipart/form-data", follow_redirects=True)
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

# A. Empty/Short Title
print("- Testing empty/short title...")
assert_validation_failed({
    "item_id": "",
    "title": "T", # too short
    "category": "Valid Category",
    "display_order": "0",
    "is_active": "1",
    "image": (io.BytesIO(b"data"), "image.jpg")
}, "Gallery title must be at least 2 characters")

# B. Too Long Title
print("- Testing too long title...")
assert_validation_failed({
    "item_id": "",
    "title": "T" * 161, # > 160
    "category": "Valid Category",
    "display_order": "0",
    "is_active": "1",
    "image": (io.BytesIO(b"data"), "image.jpg")
}, "Gallery title exceeds database limit of 160 characters")

# C. Empty/Short Category
print("- Testing empty/short category...")
assert_validation_failed({
    "item_id": "",
    "title": "Valid Title",
    "category": "C", # too short
    "display_order": "0",
    "is_active": "1",
    "image": (io.BytesIO(b"data"), "image.jpg")
}, "Category must be at least 2 characters")

# D. Too Long Category
print("- Testing too long category...")
assert_validation_failed({
    "item_id": "",
    "title": "Valid Title",
    "category": "C" * 81, # > 80
    "display_order": "0",
    "is_active": "1",
    "image": (io.BytesIO(b"data"), "image.jpg")
}, "Category name exceeds database limit of 80 characters")

# E. Negative Display Order
print("- Testing negative display order...")
assert_validation_failed({
    "item_id": "",
    "title": "Valid Title",
    "category": "Valid Category",
    "display_order": "-5", # negative
    "is_active": "1",
    "image": (io.BytesIO(b"data"), "image.jpg")
}, "Display order must be a non-negative integer")

# F. Missing Image for New Entries
print("- Testing missing image upload on creation...")
assert_validation_failed({
    "item_id": "",
    "title": "Valid Title",
    "category": "Valid Category",
    "display_order": "0",
    "is_active": "1",
    "image": (io.BytesIO(b""), "") # missing
}, "An image file is required for new gallery entries")

# G. Invalid File Extension for Image Upload
print("- Testing invalid file extensions...")
assert_validation_failed({
    "item_id": "",
    "title": "Valid Title",
    "category": "Valid Category",
    "display_order": "0",
    "is_active": "1",
    "image": (io.BytesIO(b"dangerous shell script code"), "shell.sh") # shell script
}, "File extension 'sh' not allowed")

# H. Large Image File upload rejection (>5MB)
print("- Testing file size limits (>5MB)...")
large_payload = b"0" * (6 * 1024 * 1024) # 6MB
assert_validation_failed({
    "item_id": "",
    "title": "Valid Title",
    "category": "Valid Category",
    "display_order": "0",
    "is_active": "1",
    "image": (io.BytesIO(large_payload), "heavy_image.png")
}, "Image file exceeds the maximum 5MB size limit")

print("-> Test 3 PASSED: All boundary validations correctly reject bad inputs!")

# 6. Test 4: Submit with invalid CSRF token
print("\n[Step 6] Test 4: Submitting with invalid CSRF token...")
post_data = {
    "csrf_token": "hacker-csrf-spoof",
    "item_id": "",
    "title": "Hacker Image",
    "category": "Hacking",
    "display_order": "0",
    "is_active": "1",
    "image": (io.BytesIO(b"fake data"), "hack.jpg")
}
resp = client.post("/admin/about/gallery", data=post_data, content_type="multipart/form-data", follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Your session may have expired, or the CSRF token was invalid" in html
print("-> Test 4 PASSED: Rejection of invalid CSRF token works flawlessly!")

# 7. Test 5: Deleting Gallery Entry
print("\n[Step 7] Test 5: Deleting gallery image...")
with app.app_context():
    gallery_item = AboutGalleryImage.query.filter_by(title="Robotics Lab Launch v2 🤖").first()
    assert gallery_item is not None, "Gallery item to delete does not exist!"
    gallery_id = gallery_item.id

# Submit delete POST request
_, csrf_token = get_gallery_page_and_token()
resp = client.post(f"/admin/about/gallery/{gallery_id}/delete", data={"csrf_token": csrf_token}, follow_redirects=True)
html = resp.get_data(as_text=True)
assert "Gallery image deleted successfully." in html

with app.app_context():
    gallery_item = AboutGalleryImage.query.get(gallery_id)
    assert gallery_item is None, "Gallery item was not deleted from database!"
print("-> Test 5 PASSED: Deleting gallery image performs correctly!")

# 8. Clean up test database entries and static files
print("\n[Step 8] Cleaning up other test gallery items and files...")
with app.app_context():
    test_items = AboutGalleryImage.query.filter(AboutGalleryImage.title.in_([
        "Robotics Lab Launch 🤖🚀",
        "Robotics Lab Launch v2 🤖",
        "Hacker Image",
        "Valid Title"
    ])).all()
    for item in test_items:
        if item.image_path:
            abs_img_path = os.path.join(app.static_folder, item.image_path.replace("/", os.sep))
            if os.path.exists(abs_img_path):
                try:
                    os.remove(abs_img_path)
                except Exception:
                    pass
        db.session.delete(item)
    db.session.commit()
    print("-> Cleanup complete!")

print("\n============================================================")
print("ALL TESTS PASSED SUCCESSFULLY! THE GALLERY ADMIN SYSTEM")
print("IS SECURE, EMOJI-COMPATIBLE, STABLE AND ROBUST.")
print("============================================================")
sys.exit(0)
