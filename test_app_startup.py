#!/usr/bin/env python
import sys
import os
sys.path.insert(0, os.getcwd())
print("Starting import...")
try:
    from app import create_app
    print("App module imported successfully")
    print("Creating app...")
    app = create_app()
    print("App created successfully!")
    print(f"App running on http://127.0.0.1:5000")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
