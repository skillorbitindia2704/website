import os
import time
from functools import wraps
from threading import Lock
from flask import abort, flash, redirect, request, url_for

# Global state for thread-safe in-memory rate limiting
_rate_limit_cache = {}
_cache_lock = Lock()

# Try to initialize Redis connection if REDIS_URL is configured
redis_client = None
redis_url = os.getenv("REDIS_URL")
if redis_url:
    try:
        import redis
        redis_client = redis.from_url(redis_url)
        redis_client.ping()
    except Exception:
        redis_client = None


def rate_limit(limit=5, period=60):
    """Sliding window Redis/in-memory rate limiter decorator.
    
    Defaults to 5 requests per 60 seconds.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            from flask import current_app
            if current_app and current_app.config.get("TESTING"):
                return f(*args, **kwargs)
                
            # Key rate limiter by client IP address and route endpoint
            ip = request.remote_addr or "127.0.0.1"
            endpoint = request.endpoint or "global"
            key = f"rate:{ip}:{endpoint}"
            
            now = time.time()
            if redis_client is not None:
                try:
                    pipe = redis_client.pipeline()
                    # Clean up expired timestamps from sorted set
                    pipe.zremrangebyscore(key, 0, now - period)
                    # Count elements in the set
                    pipe.zcard(key)
                    # Add current element
                    pipe.zadd(key, {str(now): now})
                    # Set expiry time
                    pipe.expire(key, period + 10)
                    results = pipe.execute()
                    cardinality = results[1]
                except Exception:
                    # Redis failed (e.g. offline), fall back to in-memory cache.
                    cardinality = None
                else:
                    # Keep abort outside the Redis exception handler: HTTPException
                    # must not be swallowed and downgraded to the local fallback.
                    if cardinality >= limit:
                        abort(429, description="Rate limit exceeded. Please try again later.")
                    return f(*args, **kwargs)

            with _cache_lock:
                # Clean up expired timestamps
                timestamps = _rate_limit_cache.get(key, [])
                timestamps = [t for t in timestamps if now - t < period]
                
                if len(timestamps) >= limit:
                    # Too many requests
                    abort(429, description="Rate limit exceeded. Please try again later.")
                
                timestamps.append(now)
                _rate_limit_cache[key] = timestamps
                
            return f(*args, **kwargs)
        return wrapper
    return decorator


def validate_file_safety(file_storage, allowed_extensions):
    """Deep binary validation of uploaded files using magic bytes.
    
    Verifies that the declared file extension matches its underlying 
    binary signature, mitigating extension spoofing and malware upload risks.
    
    Returns:
        bool: True if safe, False if unsafe or validation failed.
    """
    if not file_storage or not file_storage.filename:
        return False
        
    filename = file_storage.filename.lower()
    if "." not in filename:
        return False
        
    ext = filename.rsplit(".", 1)[1]
    allowed = {str(item).lower().lstrip(".") for item in allowed_extensions}
    if ext not in allowed:
        return False
        
    # Read the first 32 bytes to inspect magic numbers
    try:
        file_storage.seek(0)
        header = file_storage.read(32)
        file_storage.seek(0)  # Critically seek back to start for downstream save operations
    except Exception:
        return False
        
    # Validation dictionary mapping file extensions to signature checkers
    # Format: extension -> (description, validator_func)
    def check_zip_or_docx(h):
        # ZIP archive signature (PK\x03\x04)
        return h.startswith(b"PK\x03\x04")
        
    def check_pdf(h):
        # PDF signature (%PDF-)
        return h.startswith(b"%PDF")
        
    def check_jpeg(h):
        # JPEG/JPG signature (\xff\xd8\xff)
        return h.startswith(b"\xff\xd8\xff")
        
    def check_png(h):
        # PNG signature (\x89PNG)
        return h.startswith(b"\x89PNG")
        
    def check_gif(h):
        # GIF signature (GIF87a or GIF89a)
        return h.startswith(b"GIF87") or h.startswith(b"GIF89")
        
    def check_webp(h):
        # WEBP signature (RIFF at 0, WEBP at 8)
        return h.startswith(b"RIFF") and b"WEBP" in h[8:16]
        
    def check_doc(h):
        # Legacy MS Word signature (\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1)
        return h.startswith(b"\xd0\xcf\x11\xe0")
        
    def check_mp4_mov(h):
        # ISO base media files (MP4/M4V and most MOV files) identify the
        # container with an ftyp box immediately after the 4-byte size.
        return len(h) >= 12 and h[4:8] == b"ftyp"

    def check_webm_mkv(h):
        return h.startswith(b"\\x1a\\x45\\xdf\\xa3")

    def check_avi(h):
        return len(h) >= 12 and h.startswith(b"RIFF") and h[8:12] == b"AVI "

    def check_flv(h):
        return h.startswith(b"FLV")

    def check_text(h):
        try:
            h.decode("utf-8")
            return bool(h) and b"\\x00" not in h
        except UnicodeDecodeError:
            return False

    validators = {
        "pdf": check_pdf,
        "jpg": check_jpeg,
        "jpeg": check_jpeg,
        "png": check_png,
        "gif": check_gif,
        "webp": check_webp,
        "doc": check_doc,
        "ppt": check_doc,
        "docx": check_zip_or_docx,
        "pptx": check_zip_or_docx,
        "zip": check_zip_or_docx,
        "txt": check_text,
        "mp4": check_mp4_mov,
        "m4v": check_mp4_mov,
        "mov": check_mp4_mov,
        "webm": check_webm_mkv,
        "mkv": check_webm_mkv,
        "avi": check_avi,
        "flv": check_flv,
    }
    
    # Reject extensions without an explicit signature validator.
    validator = validators.get(ext)
    if validator is None or not validator(header):
        return False
            
    # Check mime type (basic sanitize check against client-supplied header)
    content_type = file_storage.content_type.lower() if file_storage.content_type else ""
    
    # Ensure known extensions don't carry plain text, HTML, or executable content types
    dangerous_mimes = {
        "text/html", "application/x-sh", "application/x-msdownload", 
        "application/x-executable", "text/javascript", "application/octet-stream"
    }
    if content_type in dangerous_mimes and ext not in {"zip"}:
        return False
        
    return True
