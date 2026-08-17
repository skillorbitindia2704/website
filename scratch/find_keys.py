import re

with open('routes/admin.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_match = re.search(r'def about_manager\(\):', content)
end_match = re.search(r'def about_restore_version\(', content)

if start_match and end_match:
    func_body = content[start_match.start():end_match.start()]
    print("--- Image handling and variables ---")
    for line in func_body.split('\n'):
        if 'image' in line or 'file' in line or 'photo' in line or 'upload' in line:
            print(line.strip())
