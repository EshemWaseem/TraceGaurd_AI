"""Nginx / Apache Combined Access Log parser.

Parses lines matching the combined log format:
    127.0.0.1 - - [15/Jan/2024:10:02:31 +0000] "GET /api/health HTTP/1.1" 200 512 "-" "curl/7"

Severity is derived from HTTP status code:
    5xx → ERROR  |  4xx → WARN  |  3xx/2xx/1xx → INFO
"""

import re
from typing import List, Tuple

from ..models.schemas import ParsedEvent, UnrecognisedLine

# Regex matching the combined log format
# Nginx timestamp format: 15/Jan/2024:10:02:31 +0000
# Convert to "15 Jan 2024 10:02:31 +0000" which dateutil handles correctly.
_NGINX_TS_RE = re.compile(
    r"(\d{1,2})/(\w{3})/(\d{4}):(\d{2}:\d{2}:\d{2}) ([+-]\d{4})"
)


def _normalise_nginx_timestamp(raw: str) -> str:
    """Convert Nginx/Apache log timestamp to a dateutil-parseable form."""
    m = _NGINX_TS_RE.match(raw.strip())
    if m:
        day, month, year, time, tz = m.groups()
        return f"{day} {month} {year} {time} {tz}"
    return raw  # return unchanged if it doesn't match; normaliser will mark as unparseable


_NGINX_RE = re.compile(
    r'^(?P<remote_host>\S+) \S+ \S+ '
    r'\[(?P<time>[^\]]+)\] '
    r'"(?P<request>[^"]*)" '
    r'(?P<status>\d{3}) '
    r'(?P<bytes>\S+)'
    r'(?: "(?P<referer>[^"]*)" "(?P<agent>[^"]*)")?$'
)


def _severity_from_status(status: str) -> str:
    code = int(status)
    if code >= 500:
        return "ERROR"
    if code >= 400:
        return "WARN"
    return "INFO"


def parse_nginx_logs(
    content: str,
) -> Tuple[List[ParsedEvent], List[UnrecognisedLine]]:
    events: List[ParsedEvent] = []
    unrecognised: List[UnrecognisedLine] = []

    for idx, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        m = _NGINX_RE.match(stripped)
        if not m:
            unrecognised.append(UnrecognisedLine(
                line_number=idx,
                raw=line,
                reason="Nginx/Apache: line does not match combined log format",
            ))
            continue

        events.append(ParsedEvent(
            line_number=idx,
            line_range=None,
            timestamp=_normalise_nginx_timestamp(m.group("time")),
            timestamp_parsed=False,       # normaliser resolves
            severity=_severity_from_status(m.group("status")),  # type: ignore[arg-type]
            service=m.group("remote_host"),
            message=m.group("request"),
            raw=line,
            format="nginx_apache",
        ))

    return events, unrecognised
