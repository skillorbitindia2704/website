"""Secure LMS file paths and validation helpers."""

import os
import time
from werkzeug.utils import secure_filename

ROOT = os.path.join(os.path.dirname(__file__), "..", "static", "uploads")
VIDEO_DIR = os.path.join(ROOT, "videos")
THUMB_DIR = os.path.join(ROOT, "lms", "thumbnails")
NOTES_DIR = os.path.join(ROOT, "lms", "notes")
RES_DIR = os.path.join(ROOT, "lms", "resources")

ALLOWED_VIDEO = {"mp4", "webm", "mov", "avi", "mkv", "flv", "m4v"}
ALLOWED_IMAGE = {"jpg", "jpeg", "png", "webp", "gif"}
ALLOWED_DOCS = {"pdf", "doc", "docx", "ppt", "pptx", "txt", "zip"}


def ensure_dirs():
    for d in (VIDEO_DIR, THUMB_DIR, NOTES_DIR, RES_DIR):
        os.makedirs(d, exist_ok=True)


def _rel_static(abs_path: str) -> str:
    """Turn absolute path under static/ into URL path."""
    static_root = os.path.join(os.path.dirname(__file__), "..", "static")
    static_root = os.path.abspath(static_root)
    abs_path = os.path.abspath(abs_path)
    if not abs_path.startswith(static_root):
        raise ValueError("Invalid upload path")
    rel = os.path.relpath(abs_path, static_root).replace(os.sep, "/")
    return "/static/" + rel.lstrip("/")


def save_upload(file_storage, subdir, allowed, max_bytes, prefix=""):
    """Save werkzeug FileStorage; return URL path like /static/uploads/... or None."""
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    from utils.security_helpers import validate_file_safety
    if not validate_file_safety(file_storage, allowed):
        return None
    ext = filename.rsplit(".", 1)[1].lower()
    ensure_dirs()
    folder = {"video": VIDEO_DIR, "thumb": THUMB_DIR, "note": NOTES_DIR, "res": RES_DIR}.get(subdir, NOTES_DIR)
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    if size > max_bytes:
        return None
    file_storage.seek(0)
    name = f"{prefix}{int(time.time())}_{filename}"
    path = os.path.join(folder, name)
    file_storage.save(path)
    return _rel_static(path)
