import re

with open('templates/admin/store_manager.html', 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.splitlines()

print("--- SEARCH FOR MODALS & FORMS ---")
for i, line in enumerate(lines):
    line_lower = line.lower()
    if 'id="product-modal"' in line_lower or 'id="edit-product' in line_lower or 'productmodal' in line_lower or 'openproductmodal' in line_lower:
        print(f"Line {i+1}: {line.strip()}")
    elif 'name="seo_title"' in line_lower or 'name="seo_description"' in line_lower:
        print(f"Line {i+1}: {line.strip()}")
