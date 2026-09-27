import jinja2
import os

env = jinja2.Environment(loader=jinja2.FileSystemLoader('website/templates'))

files_to_check = [
    'base.html',
    'home.html',
    'partials/navbar.html',
    'partials/footer.html',
    'store/detail.html',
    'store/listing.html',
    'store/cart.html',
    'store/success.html',
    'store/failed.html',
    'courses/listing.html',
    'courses/learn.html',
    'courses/learn_lms.html',
    'certificates/verify_lookup.html',
    'certificates/verify.html',
    'certificates/_verify_success.html',
    'internships/listing.html',
    'it_services/index.html',
    'about.html',
    'auth/login.html',
    'auth/signup.html',
    'dashboard/layout.html',
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
    print("ALL CHECKED TEMPLATES PARSED SUCCESSFULLY!")
