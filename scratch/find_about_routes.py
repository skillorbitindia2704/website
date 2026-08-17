with open("d:/SOI_2026/SOI_2026/routes/admin.py", "r", encoding="utf-8") as f:
    for idx, line in enumerate(f, 1):
        if "/about/" in line or "/about\"" in line or "/about'" in line:
            print(f"Line {idx}: {line.strip()}")
