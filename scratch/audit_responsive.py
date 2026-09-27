import os
import re

def check_templates():
    print("=== CHECKING TEMPLATES FOR RESPONSIVE ISSUES ===")
    template_dir = os.path.join('website', 'templates')
    for root, dirs, files in os.walk(template_dir):
        for f in files:
            if f.endswith('.html'):
                path = os.path.join(root, f)
                rel = os.path.relpath(path, template_dir)
                with open(path, encoding='utf-8') as fp:
                    txt = fp.read()

                # 1. Inline styles with large fixed width
                w_matches = re.findall(r'style=["\'][^"\']*(?:width|min-width):\s*([0-9]{3,4}px)[^"\']*["\']', txt)
                if w_matches:
                    print(f"[{rel}] Inline widths: {w_matches}")

                # 2. Table not wrapped in table-wrap or responsive container
                tables = re.findall(r'<table[^>]*>', txt)
                if tables and 'table-wrap' not in txt and 'table-responsive' not in txt:
                    print(f"[{rel}] Contains <table> without table-wrap wrapper!")

                # 3. Form elements with fixed sizes
                form_fixed = re.findall(r'(?:<input|<select|<textarea)[^>]*size=["\']([0-9]+)["\']', txt)
                if form_fixed:
                    print(f"[{rel}] Form element with size attribute: {form_fixed}")

if __name__ == '__main__':
    check_templates()
