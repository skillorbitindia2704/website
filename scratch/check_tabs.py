import re

with open(r'd:\SOI_2026\SOI_2026\templates\admin\store_manager.html', 'r', encoding='utf-8') as f:
    html = f.read()

print("Tabs found:")
# Regex to find bootstrap-like tab links e.g. data-bs-target="#..." or href="#..."
tabs = re.findall(r'(?:data-bs-target|href)=\"#([a-zA-Z0-9_-]+)\"[^>]*>(.*?)<\/a>', html)
for target, label in tabs:
    clean_label = re.sub(r'<[^>]+>', '', label).strip()
    print(f" - Target ID: #{target} | Label: {clean_label}")

print("\nForm Actions found:")
actions = re.findall(r'action=\"([^\"]+)\"', html)
for action in set(actions):
    print(f" - Action: {action}")
