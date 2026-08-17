import os
import re
import sys

sys.path.insert(0, os.getcwd())

output_lines = []
def log(msg):
    print(msg)
    output_lines.append(msg)

try:
    from app import create_app
    app = create_app()
except Exception as e:
    log(f"CRITICAL: Failed to import or initialize Flask app: {e}")
    sys.exit(1)

# Get all registered endpoints from the Flask app
valid_endpoints = set(app.view_functions.keys())
log(f"Loaded {len(valid_endpoints)} registered Flask endpoints.")

# Trace all endpoints with their module names
log("\n--- Registered Routes ---")
for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.endpoint):
    log(f"Endpoint: {rule.endpoint:35} Route: {str(rule):50} Methods: {','.join(rule.methods)}")

log("\n--- Auditing Jinja Templates for Invalid url_for() calls ---")
template_dir = os.path.join(os.getcwd(), "templates")
url_for_pattern = re.compile(r"url_for\(\s*['\"]([^'\"]+)['\"]")

url_for_errors = 0
for root, dirs, files in os.walk(template_dir):
    for file in files:
        if file.endswith(".html"):
            path = os.path.join(root, file)
            rel_path = os.path.relpath(path, os.getcwd())
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                matches = url_for_pattern.findall(content)
                for match in matches:
                    # Ignore static file endpoints (handled differently)
                    if match == "static":
                        continue
                    if match not in valid_endpoints:
                        log(f"ERROR: {rel_path} contains invalid url_for('{match}') endpoint!")
                        url_for_errors += 1

log(f"Jinja url_for() Audit completed. Found {url_for_errors} errors.")

log("\n--- Auditing Python Route Files for Missing Templates ---")
routes_dir = os.path.join(os.getcwd(), "routes")
render_pattern = re.compile(r"render_template\(\s*['\"]([^'\"]+)['\"]")

missing_templates = 0
for root, dirs, files in os.walk(routes_dir):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            rel_path = os.path.relpath(path, os.getcwd())
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                matches = render_pattern.findall(content)
                for match in matches:
                    template_path = os.path.join(template_dir, match)
                    if not os.path.exists(template_path):
                        log(f"ERROR: {rel_path} renders non-existent template: '{match}' (Path: {template_path})")
                        missing_templates += 1

log(f"Route Template Audit completed. Found {missing_templates} missing templates.")

# Save to file
output_path = os.path.join("scratch", "audit_results.txt")
with open(output_path, "w", encoding="utf-8") as f:
    f.write("\n".join(output_lines))
log(f"\nWritten complete results to: {output_path}")

