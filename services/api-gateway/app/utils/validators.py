"""
File validation utilities for video uploads.

Validates:
- File format (mp4, mov, avi, mkv, etc.)
- File size (max 500MB by default)
- Filename safety (no path traversal)
"""

import os
from typing import Tuple
from fastapi import UploadFile, HTTPException, status


# Allowed video formats (MIME types)
ALLOWED_VIDEO_FORMATS = {
    "video/mp4": [".mp4"],
    "video/quicktime": [".mov"],
    "video/x-msvideo": [".avi"],
    "video/x-matroska": [".mkv"],
    "video/webm": [".webm"],
}

# Flatten to list of extensions
ALLOWED_EXTENSIONS = [ext for exts in ALLOWED_VIDEO_FORMATS.values() for ext in exts]


def validate_video_file(
        file: UploadFile,
        max_size_mb: int = 500
) -> Tuple[str, str]:
    """
    Validates uploaded video file.

    Args:
        file: FastAPI UploadFile object
        max_size_mb: Maximum file size in megabytes

    Returns:
        Tuple[filename, extension]

    Raises:
        HTTPException: If validation fails
    """
    # 1. Check if file was provided
    if not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )

    # 2. Check if filename exists
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing"
        )

    # 3. Extract extension
    filename = file.filename.lower()
    _, extension = os.path.splitext(filename)

    # 4. Validate extension
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 5. Validate MIME type (if provided)
    if file.content_type and file.content_type not in ALLOWED_VIDEO_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type: {file.content_type}"
        )

    # 6. Validate filename safety (prevent path traversal)
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename: path traversal detected"
        )

    # Note: File size validation happens during upload (see upload endpoint)
    # We can't check size here because file isn't fully uploaded yet

    return file.filename, extension


def validate_file_size(
        file_path: str,
        max_size_mb: int = 500
) -> None:
    """
    Validates file size after upload.

    Args:
        file_path: Path to uploaded file
        max_size_mb: Maximum file size in megabytes

    Raises:
        HTTPException: If file is too large
    """
    file_size_bytes = os.path.getsize(file_path)
    file_size_mb = file_size_bytes / (1024 * 1024)

    if file_size_mb > max_size_mb:
        # Delete file if too large
        os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large: {file_size_mb:.2f}MB (max: {max_size_mb}MB)"
        )


def sanitize_filename(filename: str) -> str:
    """
    Sanitizes filename for safe storage.

    Removes special characters and spaces.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Keep only alphanumeric, dash, underscore, dot
    safe_chars = []
    for char in filename:
        if char.isalnum() or char in ['-', '_', '.']:
            safe_chars.append(char)
        elif char == ' ':
            safe_chars.append('_')

    return ''.join(safe_chars)


def generate_unique_filename(original_filename: str) -> str:
    """
    Generates unique filename to prevent collisions.

    Format: {timestamp}_{sanitized_original_name}
    Example: 1707385800_vacation_video.mp4

    Args:
        original_filename: Original filename from upload

    Returns:
        Unique filename
    """
    import time

    timestamp = int(time.time())
    sanitized = sanitize_filename(original_filename)

    # Split name and extension
    name, ext = os.path.splitext(sanitized)

    # Truncate name if too long (max 100 chars + extension)
    if len(name) > 100:
        name = name[:100]

    return f"{timestamp}_{name}{ext}"