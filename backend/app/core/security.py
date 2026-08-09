"""Security utilities for file handling and input validation."""
import mimetypes
import os
import re
import uuid
from pathlib import Path
from typing import Optional, Tuple

from app.config import get_settings
from app.core.constants import MAGIC_BYTES, SUPPORTED_EXTENSIONS, SUPPORTED_MIME_TYPES
from app.core.exceptions import DocumentValidationError


# Windows reserved names
FORBIDDEN_NAMES = {
    "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5",
    "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5",
    "LPT6", "LPT7", "LPT8", "LPT9",
}


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal and injection attacks."""
    # Remove path components
    filename = os.path.basename(filename)
    # Remove forbidden characters: < > : " / \ | ? * and control chars
    forbidden = '<>:"/\\|?*' + ''.join(chr(i) for i in range(32))
    for char in forbidden:
        filename = filename.replace(char, "")
    # Check forbidden names (Windows reserved)
    name_without_ext = Path(filename).stem.upper()
    if name_without_ext in FORBIDDEN_NAMES:
        filename = f"doc_{filename}"
    # Limit length
    if len(filename) > 255:
        ext = Path(filename).suffix
        filename = filename[:250] + ext
    return filename or "unnamed_document"


def generate_secure_filename(original_name: str) -> str:
    """Generate a secure, unique filename while preserving the extension."""
    safe_name = sanitize_filename(original_name)
    ext = Path(safe_name).suffix.lower()
    unique_id = str(uuid.uuid4())[:8]
    return f"{unique_id}_{safe_name}"


def validate_file_type(filename: str, content_type: Optional[str] = None) -> str:
    """Validate file type by extension and optional content type.

    Returns the detected extension or raises DocumentValidationError.
    """
    settings = get_settings()
    ext = Path(filename).suffix.lower().lstrip(".")

    if ext not in settings.allowed_extensions:
        raise DocumentValidationError(
            f"File extension '.{ext}' is not allowed. "
            f"Supported: {', '.join(settings.allowed_extensions)}"
        )

    if content_type and content_type != "application/octet-stream":
        detected_ext = SUPPORTED_MIME_TYPES.get(content_type)
        if detected_ext and detected_ext != ext:
            raise DocumentValidationError(
                f"Content type mismatch: declared '{content_type}' but extension is '.{ext}'"
            )

    return ext


def validate_file_size(file_size: int) -> None:
    """Validate file size against configured limits."""
    settings = get_settings()
    if file_size > settings.max_file_size_bytes:
        raise DocumentValidationError(
            f"File size {file_size / 1024 / 1024:.1f}MB exceeds limit of {settings.max_file_size_mb}MB"
        )


def validate_magic_bytes(file_path: str, expected_ext: str) -> None:
    """Validate file magic bytes match the expected extension."""
    try:
        with open(file_path, "rb") as f:
            header = f.read(8)
    except Exception as e:
        raise DocumentValidationError(f"Cannot read file for magic byte validation: {e}")

    # PDF check
    if expected_ext == "pdf":
        if not header.startswith(b"%PDF"):
            raise DocumentValidationError("File does not appear to be a valid PDF (magic bytes mismatch)")

    # DOCX check (ZIP archive)
    if expected_ext == "docx":
        if not header.startswith(b"PK\x03\x04"):
            raise DocumentValidationError("File does not appear to be a valid DOCX (magic bytes mismatch)")


def validate_upload(filename: str, file_size: int, content_type: Optional[str] = None) -> str:
    """Full validation pipeline for uploaded files."""
    validate_file_size(file_size)
    ext = validate_file_type(filename, content_type)
    return ext


def get_safe_path(upload_dir: str, secure_filename: str) -> Path:
    """Get a safe absolute path within the upload directory."""
    base = Path(upload_dir).resolve()
    target = (base / secure_filename).resolve()
    # Ensure the resolved path is within the base directory
    if not str(target).startswith(str(base)):
        raise DocumentValidationError("Path traversal detected")
    return target
