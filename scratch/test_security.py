import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from utils.security_helpers import validate_file_safety
from io import BytesIO
from werkzeug.datastructures import FileStorage

def test_file_safety():
    print("Running file safety tests...")
    
    # 1. Valid PDF file storage mock
    pdf_data = b"%PDF-1.4\n%..."
    pdf_file = FileStorage(stream=BytesIO(pdf_data), filename="resume.pdf", content_type="application/pdf")
    assert validate_file_safety(pdf_file, ["pdf"]) == True, "Failed valid PDF test"
    
    # 2. Invalid PDF spoof test (PDF extension, but starts with text)
    spoof_data = b"Hello, I am a plain text file, not a PDF."
    spoof_file = FileStorage(stream=BytesIO(spoof_data), filename="resume.pdf", content_type="application/pdf")
    assert validate_file_safety(spoof_file, ["pdf"]) == False, "Failed invalid PDF spoof test"
    
    # 3. Valid DOCX ZIP mock
    docx_data = b"PK\x03\x04\x14\x00\x08\x00\x08\x00..."
    docx_file = FileStorage(stream=BytesIO(docx_data), filename="resume.docx", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert validate_file_safety(docx_file, ["docx"]) == True, "Failed valid DOCX test"
    
    # 4. Empty/no filename validation
    empty_file = FileStorage(stream=BytesIO(b""), filename="")
    assert validate_file_safety(empty_file, ["pdf"]) == False, "Failed empty file test"
    
    print("All file safety validation checks passed successfully!")

def test_security_headers():
    print("Running security headers and app configuration tests...")
    app = create_app()
    app.config["TESTING"] = True
    
    with app.test_client() as client:
        # Get hompage
        res = client.get("/")
        
        # Verify clickjacking mitigation
        assert res.headers.get("X-Frame-Options") == "SAMEORIGIN", f"Failed X-Frame-Options check: {res.headers.get('X-Frame-Options')}"
        
        # Verify MIME type sniffing protection
        assert res.headers.get("X-Content-Type-Options") == "nosniff", f"Failed X-Content-Type-Options check: {res.headers.get('X-Content-Type-Options')}"
        
        # Verify XSS Protection
        assert res.headers.get("X-XSS-Protection") == "1; mode=block", f"Failed X-XSS-Protection check: {res.headers.get('X-XSS-Protection')}"
        
        # Verify CSP header
        csp = res.headers.get("Content-Security-Policy")
        assert csp is not None, "Content-Security-Policy header is missing"
        assert "default-src 'self'" in csp, f"Failed default-src CSP check: {csp}"
        assert "https://checkout.razorpay.com" in csp, f"Failed Razorpay CDN script-src CSP check: {csp}"
        assert "https://cdn.tailwindcss.com" in csp, f"Failed Tailwind CDN script-src CSP check: {csp}"
        assert "https://www.google.com" in csp, f"Failed Google frame-src CSP check: {csp}"
        
        # Verify Referrer-Policy
        assert res.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin", f"Failed Referrer-Policy check: {res.headers.get('Referrer-Policy')}"
        
    print("All security headers and middleware checks passed successfully!")

if __name__ == "__main__":
    try:
        test_file_safety()
        test_security_headers()
        print("\n[SUCCESS] All security unit tests passed flawlessly!")
    except AssertionError as ae:
        print(f"\n[FAILURE] Assertion failed: {ae}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
