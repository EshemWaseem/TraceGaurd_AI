"""File validation and binary content classification stage for TraceGuard AI.

Validates uploaded files and pasted text before parsing to reject PDFs,
executables, archives, media, and malformed binary content safely and return
actionable, user-friendly explanations.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple
from fastapi import HTTPException, status

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB hard cap

# Known binary magic byte signatures
_BINARY_SIGNATURES = [
    (b"%PDF-", "PDF document"),
    (b"\x7fELF", "Linux ELF executable"),
    (b"MZ", "Windows PE executable / DLL"),
    (b"PK\x03\x04", "ZIP / Office archive"),
    (b"\x1f\x8b", "GZIP compressed archive"),
    (b"\x89PNG\r\n\x1a\n", "PNG image"),
    (b"\xff\xd8\xff", "JPEG image"),
    (b"GIF87a", "GIF image"),
    (b"GIF89a", "GIF image"),
    (b"ustar", "TAR archive"),
]

PDF_FRIENDLY_ERROR = (
    "This file is a PDF report, not a supported log file. "
    "Upload a .log, .txt, or supported .json file instead."
)

BINARY_FRIENDLY_ERROR = (
    "This file appears to be a binary or unsupported file format. "
    "Upload a plain text .log, .txt, or JSON log file instead."
)


def is_pdf_content(raw_bytes: bytes, filename: str = "") -> bool:
    """Return True if content matches PDF magic bytes, header or file extension."""
    if filename.lower().endswith(".pdf"):
        return True
    header = raw_bytes[:1024]
    if b"%PDF-" in header:
        return True
    return False


def is_binary_content(raw_bytes: bytes) -> Tuple[bool, Optional[str]]:
    """Inspect byte signature and byte distribution for binary / non-text files."""
    header = raw_bytes[:2048]
    for sig, desc in _BINARY_SIGNATURES:
        if header.startswith(sig) or (sig == b"%PDF-" and sig in header):
            return True, desc

    # Null bytes are a definitive signal of binary encoding in text files
    if b"\x00" in header:
        return True, "Binary data with null bytes"

    # Check ratio of non-printable / non-ASCII/UTF-8 control characters
    if header:
        non_printable = sum(
            1 for b in header
            if b < 32 and b not in (9, 10, 13)  # \t, \n, \r are allowed
        )
        if non_printable / len(header) > 0.20:
            return True, "High ratio of non-printable control bytes"

    return False, None


def validate_upload(
    raw_bytes: bytes,
    filename: str,
    content_type: str = "",
) -> str:
    """Validate uploaded bytes. Returns decoded text or raises structured HTTPException."""
    if len(raw_bytes) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Log input exceeds 5 MB limit. Upload a smaller file or paste a subset.",
        )

    if not raw_bytes or not raw_bytes.strip():
        raise HTTPException(
            status_code=422,
            detail="Log input is empty. Please provide a file with log content.",
        )

    # 1. Check for PDF explicitly
    if is_pdf_content(raw_bytes, filename) or "application/pdf" in content_type.lower():
        raise HTTPException(
            status_code=422,
            detail=PDF_FRIENDLY_ERROR,
        )

    # 2. Check for binary / unsupported format
    is_binary, reason = is_binary_content(raw_bytes)
    if is_binary:
        raise HTTPException(
            status_code=422,
            detail=BINARY_FRIENDLY_ERROR,
        )

    # 3. Decode as UTF-8 safely
    try:
        content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            # Fallback to latin-1 / windows-1252 if strictly text without nulls
            content = raw_bytes.decode("latin-1")
        except Exception:
            raise HTTPException(
                status_code=422,
                detail="Could not decode file as text. Please ensure the file is saved as UTF-8.",
            )

    if not content.strip():
        raise HTTPException(
            status_code=422,
            detail="Log input contains only whitespace.",
        )

    return content


def validate_pasted_text(content: str, filename: str = "") -> str:
    """Validate pasted text content from JSON requests."""
    raw_encoded = content.encode("utf-8")
    if len(raw_encoded) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Log input exceeds 5 MB limit. Paste a smaller subset.",
        )

    if not content.strip():
        raise HTTPException(
            status_code=422,
            detail="Input is empty.",
        )

    # Reject pasted PDF syntax
    if content.startswith("%PDF-") or "%PDF-" in content[:1024] or filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=422,
            detail=PDF_FRIENDLY_ERROR,
        )

    # Reject binary null bytes in pasted text
    if "\x00" in content[:4096]:
        raise HTTPException(
            status_code=422,
            detail=BINARY_FRIENDLY_ERROR,
        )

    return content
