"""Log sanitizer and secret redaction utilities for TraceGuard AI Phase 3.

Redacts tokens, passwords, authorization headers, database connection credentials,
and private keys from log content, telemetry, diagnostic messages, and exception strings.

Preserves original line structure and line count so evidence line references
remain strictly accurate.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Sensitive patterns
# ---------------------------------------------------------------------------

_PATTERNS = [
    # Authorization header: Authorization: Bearer <token> or Basic <token>
    (
        re.compile(r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)[^\r\n,;\"\']+", re.IGNORECASE),
        r"\g<1>[REDACTED_AUTH]",
    ),
    # Bearer tokens standalone: Bearer eyJhbG... or Bearer abcdef12345...
    (
        re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9_\-\.]{15,}\b", re.IGNORECASE),
        r"\g<1>[REDACTED_TOKEN]",
    ),
    # JWTs: eyJ...
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        r"[REDACTED_JWT]",
    ),
    # Database / connection strings with embedded credentials:
    # e.g. postgres://user:secret@localhost:5432/db or mongodb://admin:pass@host
    (
        re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)([^:\s@]+):([^@\s]+)@"),
        r"\g<1>[REDACTED_USER]:[REDACTED_PASSWORD]@",
    ),
    # Common password/secret/api_key/token key-values in JSON, query strings, or logs
    (
        re.compile(
            r"""(?i)(["\']?(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|token|private[_-]?key)["\']?\s*[:=]\s*["\']?)([^"\'\s,;&]+)(["\']?)"""
        ),
        r"\g<1>[REDACTED_SECRET]\g<3>",
    ),
    # GitHub personal access tokens
    (
        re.compile(r"\b(gh[pousr]_[A-Za-z0-9_]{20,})\b"),
        r"[REDACTED_TOKEN]",
    ),
    # AWS access keys
    (
        re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
        r"[REDACTED_AWS_KEY]",
    ),
    # Private key blocks
    (
        re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----[^-]+-----END (?:RSA )?PRIVATE KEY-----", re.DOTALL),
        r"[REDACTED_PRIVATE_KEY]",
    ),
]


def sanitize_message(text: str) -> str:
    """Sanitize secrets, credentials, and sensitive tokens from a single log message or text.

    Does not modify newline characters or line count.
    """
    if not text:
        return text
    sanitized = text
    for pattern, replacement in _PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def sanitize_exception(exc: Exception | str) -> str:
    """Sanitize an exception message to prevent leaking internal database URLs or credentials."""
    msg = str(exc)
    return sanitize_message(msg)[:300]


def sanitize_evidence_package(evidence_package: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep-copied/sanitized version of the evidence package sent to AI providers."""
    sanitized: Dict[str, Any] = {}
    for k, v in evidence_package.items():
        if k == "evidence_text" and isinstance(v, str):
            sanitized[k] = sanitize_message(v)
        elif k == "anomalies" and isinstance(v, list):
            sanitized[k] = [
                {
                    **a,
                    "title": sanitize_message(a.get("title", "")),
                    "explanation": sanitize_message(a.get("explanation", "")),
                }
                for a in v
            ]
        elif k == "hypotheses" and isinstance(v, list):
            sanitized[k] = [
                {
                    **h,
                    "title": sanitize_message(h.get("title", "")),
                    "next_steps": [sanitize_message(s) for s in h.get("next_steps", [])],
                }
                for h in v
            ]
        else:
            sanitized[k] = v
    return sanitized
