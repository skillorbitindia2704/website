import os
import re

templates_dir = "website/templates"

fixed_width_pattern = re.compile(r'style="[^"]*width:\s*([4-9]\d{2,}px|\d{4,}px)[^"]*"', re.IGNORECASE)
fixed_minwidth_pattern = re.compile(r'style="[^"]*min-width:\s*([4-9]\d{2,}px|\d{4,}px)[^"]*"', re.IGNORECASE)
fixed_grid_cols = re.compile(r'grid-template-columns:\s*repeat\([4-9],', re.IGNORECASE)

issues = []

for root, dirs, files in os.walk(templates_dir):
    for f in files:
        if f.endswith('.html'):
            filepath = os.path.join(root, f)
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as fp:
                content = fp.read()
                for line_no, line in enumerate(content.splitlines(), start=1):
                    for m in fixed_width_pattern.finditer(line):
                        issues.append((filepath, line_no, "fixed width", m.group(0)))
                    for m in fixed_minwidth_pattern.finditer(line):
                        issues.append((filepath, line_no, "fixed min-width", m.group(0)))

print(f"Total potential fixed width issues found: {len(issues)}")
for filepath, line_no, itype, snippet in issues[:30]:
    rel = os.path.relpath(filepath, "website")
    print(f"{rel}:{line_no} [{itype}] {snippet}")
