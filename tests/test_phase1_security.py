import unittest
from io import BytesIO

from werkzeug.datastructures import FileStorage

from utils.security_helpers import validate_file_safety


class FileValidationSecurityTests(unittest.TestCase):
    def make_file(self, data, filename, content_type):
        return FileStorage(stream=BytesIO(data), filename=filename, content_type=content_type)

    def test_valid_pdf_is_accepted(self):
        upload = self.make_file(b"%PDF-1.7\n", "resume.pdf", "application/pdf")
        self.assertTrue(validate_file_safety(upload, {"pdf"}))

    def test_pdf_extension_spoof_is_rejected(self):
        upload = self.make_file(b"not a PDF document", "resume.pdf", "application/pdf")
        self.assertFalse(validate_file_safety(upload, {"pdf"}))

    def test_mp4_must_have_ftyp_signature(self):
        valid = self.make_file(b"\x00\x00\x00\x18ftypisom", "lesson.mp4", "video/mp4")
        spoof = self.make_file(b"plain text pretending to be video", "lesson.mp4", "video/mp4")
        self.assertTrue(validate_file_safety(valid, {"mp4"}))
        self.assertFalse(validate_file_safety(spoof, {"mp4"}))

    def test_unknown_extension_is_rejected(self):
        upload = self.make_file(b"anything", "payload.bin", "application/octet-stream")
        self.assertFalse(validate_file_safety(upload, {"bin"}))

    def test_avi_signature_is_checked(self):
        valid = self.make_file(b"RIFF\x24\x00\x00\x00AVI ", "lesson.avi", "video/x-msvideo")
        spoof = self.make_file(b"RIFF\x24\x00\x00\x00NOPE", "lesson.avi", "video/x-msvideo")
        self.assertTrue(validate_file_safety(valid, {"avi"}))
        self.assertFalse(validate_file_safety(spoof, {"avi"}))


if __name__ == "__main__":
    unittest.main()
