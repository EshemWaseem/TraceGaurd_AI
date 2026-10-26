"""Analysis engine — wires format detection, parsing, normalisation, and detection rules."""

from ..models.schemas import AnalysisResult, AnalysisSummary, ParsedEvent, UnrecognisedLine
from ..parsers.detector import detect_format
from ..parsers.json_parser import parse_json_logs
from ..parsers.plaintext_parser import parse_plaintext_logs
from ..parsers.nginx_parser import parse_nginx_logs
from ..analysis.normalizer import normalise_event
from ..analysis.rules import apply_all_rules


# Safeguard against pathological oversized lines (e.g. minified logs or regex DoS payloads)
MAX_LINE_LENGTH = 16384  # 16 KB per line


def _bound_lines(content: str) -> str:
    """Safeguard against pathological oversized lines while preserving line indices."""
    lines = content.splitlines()
    truncated = False
    bounded = []
    for line in lines:
        if len(line) > MAX_LINE_LENGTH:
            bounded.append(line[:MAX_LINE_LENGTH] + "... [TRUNCATED_OVERSIZED_LINE]")
            truncated = True
        else:
            bounded.append(line)
    return "\n".join(bounded) if truncated else content


class AnalysisEngine:
    def analyze(self, content: str, filename: str) -> AnalysisResult:
        content = _bound_lines(content)
        fmt = detect_format(content)

        if fmt == "json_application":
            events, unrecognised = parse_json_logs(content)
        elif fmt == "plaintext":
            events, unrecognised = parse_plaintext_logs(content)
        elif fmt == "nginx_apache":
            events, unrecognised = parse_nginx_logs(content)
        else:
            # Unknown format — every non-blank line is flagged; nothing is silently discarded.
            events = []
            unrecognised = [
                UnrecognisedLine(
                    line_number=i + 1,
                    raw=line,
                    reason=f"Format '{fmt}': no suitable parser available",
                )
                for i, line in enumerate(content.splitlines())
                if line.strip()
            ]

        # Normalise all events (timestamps → ISO-8601 UTC, severity → canonical)
        events = [normalise_event(e) for e in events]

        # Sort: timestamped events first (chronological), then by line order
        events_with_ts: list[ParsedEvent] = sorted(
            [e for e in events if e.timestamp_parsed],
            key=lambda e: e.timestamp or "",
        )
        events_without_ts: list[ParsedEvent] = sorted(
            [e for e in events if not e.timestamp_parsed],
            key=lambda e: e.line_number,
        )
        sorted_events = events_with_ts + events_without_ts

        # Run detection rules
        anomalies, hypotheses = apply_all_rules(sorted_events)

        error_count = sum(1 for e in sorted_events if e.severity == "ERROR")
        warn_count = sum(1 for e in sorted_events if e.severity == "WARN")
        total_lines = len(content.splitlines())

        return AnalysisResult(
            filename=filename,
            summary=AnalysisSummary(
                total_lines=total_lines,
                parsed_events=len(sorted_events),
                error_count=error_count,
                warn_count=warn_count,
                anomalies_flagged=len(anomalies),
                unrecognised_lines=len(unrecognised),
                detected_format=fmt,
            ),
            events=sorted_events,
            anomalies=anomalies,
            hypotheses=hypotheses,
            unrecognised_lines=unrecognised,
        )
