import jinja2
import os

env = jinja2.Environment(loader=jinja2.FileSystemLoader('website/templates'))

files_to_check = [
    'admin/users.html',
    'admin/roles.html',
    'admin/permissions.html',
    'admin/admin_accounts.html',
    'admin/module_group.html',
]

success = True
for f in files_to_check:
    path = os.path.join('website/templates', f)
    if not os.path.exists(path):
        print(f"Skipping {f} (not found)")
        continue
    try:
        with open(path, 'r', encoding='utf-8') as fp:
            src = fp.read()
        env.parse(src)
        print(f"OK: {f}")
    except Exception as e:
        print(f"ERROR in {f}: {e}")
        success = False

if success:
    print("ALL USER MANAGEMENT TEMPLATES PARSED SUCCESSFULLY!")
