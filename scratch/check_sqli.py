import os
import re

def check_sqli():
    print("Running SQL Injection Vulnerability Scan...")
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Patterns for execute, raw sql, text()
    patterns = [
        (re.compile(r'\.execute\(\s*f["\']'), "execute with f-string"),
        (re.compile(r'\.execute\(\s*["\'].*%s.*["\']\s*,\s*[^)]+\)'), "execute with %s formatting"),
        (re.compile(r'text\(\s*f["\']'), "SQL text() with f-string"),
        (re.compile(r'text\(\s*["\'].*%s.*["\']'), "SQL text() with %s formatting")
    ]
    
    violations = 0
    for root, dirs, files in os.walk(project_dir):
        if "venv" in root or ".git" in root or "__pycache__" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                rel_path = os.path.relpath(path, project_dir)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines, 1):
                            for pattern, desc in patterns:
                                if pattern.search(line):
                                    print(f"SUSPICIOUS: {rel_path}:{i} - {desc}")
                                    print(f"  Line: {line.strip()}")
                                    violations += 1
                except Exception as e:
                    print(f"Error reading {rel_path}: {e}")
                    
    print(f"SQL injection audit completed. Found {violations} suspicious lines.")

if __name__ == "__main__":
    check_sqli()
