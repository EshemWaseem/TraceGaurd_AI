"""
Analysis engine — Slice 1 stub.
Runs format detection + the appropriate parser + sorting.
Anomaly/hypothesis detection rules are wired in Slice 2.
"""

from ..models.schemas import AnalysisResult, AnalysisSummary, ParsedEvent
from ..parsers.detector import detect_format
from ..parsers.json_parser import parse_json_logs


class AnalysisEngine:
    def analyze(self, content: str, filename: str) -> AnalysisResult:
        fmt = detect_format(content)

        if fmt == "json_application":
            events, unrecognised = parse_json_logs(content)
        else:
            # Slice 1: formats other than JSON are treated as unknown and all
            # lines are flagged as unrecognised. Plaintext and Nginx parsers
            # are added in Slice 2.
            from ..models.schemas import UnrecognisedLine

            events = []
            unrecognised = [
                UnrecognisedLine(
                    line_number=i + 1,
                    raw=line,
                    reason=f"Format '{fmt}' parser not yet available (Slice 1 stub)",
                )
                for i, line in enumerate(content.splitlines())
                if line.strip()
            ]

        # Sort: events with valid timestamps first (by timestamp), then by line number
        events_with_ts = sorted(
            [e for e in events if e.timestamp_parsed],
            key=lambda e: e.timestamp or "",
        )
        events_without_ts = sorted(
            [e for e in events if not e.timestamp_parsed],
            key=lambda e: e.line_number,
        )
        sorted_events: list[ParsedEvent] = events_with_ts + events_without_ts

        error_count = sum(1 for e in sorted_events if e.severity == "ERROR")
        warn_count = sum(1 for e in sorted_events if e.severity == "WARN")
        total_lines = len([l for l in content.splitlines()])

        return AnalysisResult(
            filename=filename,
            summary=AnalysisSummary(
                total_lines=total_lines,
                parsed_events=len(sorted_events),
                error_count=error_count,
                warn_count=warn_count,
                anomalies_flagged=0,  # rules added in Slice 2
                unrecognised_lines=len(unrecognised),
                detected_format=fmt,
            ),
            events=sorted_events,
            anomalies=[],      # Slice 2
            hypotheses=[],     # Slice 2
            unrecognised_lines=unrecognised,
        )
