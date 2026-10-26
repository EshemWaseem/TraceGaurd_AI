from typing import Literal, Optional

from pydantic import BaseModel


class ParsedEvent(BaseModel):
    line_number: int
    line_range: Optional[list[int]] = None  # [first, last] for multiline entries (e.g. stack traces)
    timestamp: Optional[str] = None  # ISO 8601 UTC string, or None if unparseable
    timestamp_parsed: bool
    severity: Literal["ERROR", "WARN", "INFO", "DEBUG", "UNKNOWN"]
    service: Optional[str] = None
    message: str
    raw: str  # exact original line(s), never mutated
    format: Literal["json_application", "plaintext", "nginx_apache", "unknown"]


class MatchedRule(BaseModel):
    name: str
    description: str
    threshold: str


class Anomaly(BaseModel):
    id: str
    rule: str
    title: str
    epistemic_label: Literal["detected_pattern"]
    explanation: str
    matched_rule: MatchedRule
    evidence_line_numbers: list[int]
    supporting_line_count: int
    relationship: Literal["main_finding", "related_evidence", "additional_pattern"] = "main_finding"


class Hypothesis(BaseModel):
    id: str
    title: str
    epistemic_label: Literal["unconfirmed_hypothesis"]
    plausibility: str
    supporting_anomaly_ids: list[str]
    evidence_line_numbers: list[int]
    next_steps: list[str]
    llm_explanation: Optional[str] = None  # present only when LLM mode active and succeeded


class UnrecognisedLine(BaseModel):
    line_number: int
    raw: str
    reason: str


class AnalysisSummary(BaseModel):
    total_lines: int
    parsed_events: int
    error_count: int
    warn_count: int
    anomalies_flagged: int
    unrecognised_lines: int
    detected_format: str


class AnalysisResult(BaseModel):
    filename: str
    summary: AnalysisSummary
    events: list[ParsedEvent]
    anomalies: list[Anomaly]
    hypotheses: list[Hypothesis]
    unrecognised_lines: list[UnrecognisedLine]
