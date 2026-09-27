import os
import sys

# Add website to path
sys.path.insert(0, os.path.abspath("website"))

# Override DATABASE_URL to avoid remote DB network latency during endpoint check
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["TESTING"] = "1"
os.environ["WTF_CSRF_ENABLED"] = "false"

from app import create_app

app = create_app()

with app.test_request_context():
    from flask import url_for
    
    endpoints = [
        ("admin.user_management", url_for("admin.user_management"), "/admin/dashboard/user-management"),
        ("admin.users", url_for("admin.users"), "/admin/users"),
        ("admin.roles", url_for("admin.roles"), "/admin/roles"),
        ("admin.permissions", url_for("admin.permissions"), "/admin/permissions"),
        ("admin.admin_accounts", url_for("admin.admin_accounts"), "/admin/admin-accounts"),
        ("admin.approve_teacher_role", url_for("admin.approve_teacher_role", user_id=42), "/admin/roles/approve-teacher/42"),
    ]
    
    for name, url, expected in endpoints:
        assert url == expected, f"Expected {expected}, got {url}"
        print(f"PASS: {name} -> {url}")

print("ALL 4 USER MANAGEMENT ENDPOINTS ARE REGISTERED AND MATCH PERFECTLY!")
