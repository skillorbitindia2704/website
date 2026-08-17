import os
import uuid
from datetime import datetime

from flask import current_app
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def generate_certificate_pdf(student_name, course_title):
    cert_uid = str(uuid.uuid4())
    cert_dir = os.path.join(current_app.root_path, "static", "certificates")
    os.makedirs(cert_dir, exist_ok=True)
    file_name = f"{cert_uid}.pdf"
    output_path = os.path.join(cert_dir, file_name)

    c = canvas.Canvas(output_path, pagesize=A4)
    c.setFont("Helvetica-Bold", 28)
    c.drawString(120, 760, "Skill Orbit India")
    c.setFont("Helvetica", 20)
    c.drawString(170, 700, "Certificate of Completion")
    c.setFont("Helvetica", 14)
    c.drawString(100, 640, f"This certifies that {student_name} has completed")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 610, course_title)
    c.setFont("Helvetica", 12)
    c.drawString(100, 560, f"Issued on: {datetime.utcnow().strftime('%d-%m-%Y')}")
    c.drawString(100, 530, f"Certificate ID: {cert_uid}")
    c.save()
    return cert_uid, f"/static/certificates/{file_name}"
