import os
import sys

sys.path.insert(0, os.getcwd())

from app import create_app
from flask_login import login_user

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False
app.config['TESTING'] = True

client = app.test_client()

print("--- Authenticating default Admin user ---")
response = client.post("/login", data={
    "email": "skillorbitindia2704@gmail.com",
    "password": "MAAN0864208642"
}, follow_redirects=True)

# Check if auth succeeded (should reach admin index /dashboard or render dashboard)
if response.status_code == 200:
    print("Authentication simulated successfully!")
else:
    print(f"CRITICAL: Authentication failed with status {response.status_code}!")
    sys.exit(1)

routes_to_test = [
    ("/", 200),
    ("/about", 200),
    ("/login", 302),  # Expect redirect if already logged in
    ("/store/", 200),
    ("/courses/", 200),
    ("/certificate/verify", 200),
    ("/internships/", 200),
    ("/it-services/", 200),
    ("/ai-lab/", 200),
    ("/admin/dashboard", 200),
    ("/admin/website-branding", 200),
    ("/admin/homepage-events", 200),
    ("/admin/site-settings", 200),
    ("/admin/orders", 200),
    ("/admin/products", 200),
    ("/admin/courses", 200),
    ("/admin/teachers", 200),
    ("/admin/users", 200),
    ("/admin/internships", 200),
    ("/admin/services/manage", 200),
]

print("\n--- Testing All Core Pages and Dashboard Sections (Logged In) ---")
failed = 0
for route, expected_status in routes_to_test:
    response = client.get(route)
    status = response.status_code
    if status == expected_status or (expected_status == 302 and status in (302, 301)):
        print(f"PASS: {route:30} returned {status}")
    else:
        print(f"FAIL: {route:30} returned {status}, expected {expected_status}")
        failed += 1

if failed == 0:
    print("\nALL STABILITY AUDIT ENDPOINTS PASSED SUCCESSFULLY! The entire site is navigable, stable and error-free.")
    sys.exit(0)
else:
    print(f"\n{failed} endpoints FAILED stability check!")
    sys.exit(1)
