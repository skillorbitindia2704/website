import os
import re

templates_dir = "d:/SOI_2026/SOI_2026/templates/admin"
missing_csrf = []

for root, dirs, files in os.walk(templates_dir):
    for file in files:
        if file.endswith(".html"):
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            
            # Find all <form ...> tags
            forms = re.findall(r'<form\b[^>]*>', content, re.IGNORECASE)
            # Check if any form has method="post" or method='post'
            post_forms = [form for form in forms if 'method="post"' in form.lower() or "method='post'" in form.lower() or 'method=post' in form.lower()]
            
            if post_forms:
                # Check if csrf_token is in the file
                if 'csrf_token' not in content.lower():
                    missing_csrf.append((file, len(post_forms)))

print("Templates missing csrf_token:")
for item, count in missing_csrf:
    print(f"- {item} ({count} POST form(s))")
