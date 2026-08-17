import re

with open('templates/admin/about_manager.html', 'r', encoding='utf-8') as f:
    content = f.read()

select_match = re.search(r'<select[^>]*name=["\']hero_gradient_theme["\'][^>]*>([\s\S]*?)</select>', content)
if select_match:
    print("Found select options:")
    print(select_match.group(1).strip())
else:
    print("Could not find hero_gradient_theme select")
