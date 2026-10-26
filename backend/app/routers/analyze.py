"""Updated analyze router — Phase 2.

Now returns both `AnalysisResult` (unchanged) and a new `InvestigationReport`
in a combined `AnalyzeResponse`. The existing /api/analyze response is extended,
not replaced — old fields remain at the same keys.
"""

import os
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from ..core.security import auth_rate_limiter, get_trusted_client_ip
from ..analysis.validator import validate_upload, validate_pasted_text
from ..analysis.engine import AnalysisEngine
from ..analysis.investigation_builder import build_investigation_report
from ..models.schemas import AnalysisResult
from ..models.investigation import InvestigationReport
from pydantic import BaseModel

router = APIRouter(prefix="/api")
engine = AnalysisEngine()

MAX_BYTES = 5 * 1024 * 1024  # 5 MB

_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


class AnalyzeResponse(BaseModel):
    """Combined analysis + investigation response."""
    # Original AnalysisResult fields (kept flat for backwards compatibility)
    filename: str
    summary: dict
    events: list
    anomalies: list
    hypotheses: list
    unrecognised_lines: list
    # Phase 2: investigation report
    investigation: dict


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}



@router.get("/sample")
async def get_sample() -> dict:
    """Return the bundled sample incident log."""
    fixture_path = os.path.join(_FIXTURES_DIR, "sample_incident.log")
    if os.path.exists(fixture_path):
        with open(fixture_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = (
            '{"timestamp":"2024-01-15T10:00:00Z","level":"INFO",'
            '"message":"Sample incident log not yet available","service":"api"}\n'
        )
    return {"content": content, "filename": "sample_incident.log"}


@router.post("/analyze")
async def analyze(
    request: Request,
    file: Optional[UploadFile] = File(default=None),
    use_ai: bool = Query(default=False, description="Request AI-assisted reasoning (falls back to deterministic)"),
) -> dict:
    """
    Accept a log file (multipart/form-data) or pasted text (application/json).
    Enforces 5 MB limit on both paths.
    Returns AnalysisResult fields + investigation report.
    """
    # Rate limit check (protects server resources from abuse)
    client_ip = get_trusted_client_ip(request)
    if auth_rate_limiter.is_rate_limited(f"analyze:{client_ip}", max_attempts=120, window_seconds=60):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded for log analysis. Please wait a minute before submitting again.",
        )

    content_type = request.headers.get("content-type", "")

    if file is not None:
        filename = file.filename or "uploaded.log"
        raw_bytes = await file.read(MAX_BYTES + 1)
        content = validate_upload(raw_bytes, filename=filename, content_type=content_type)

    elif "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid JSON body.")
        raw_content = body.get("content", "")
        filename = body.get("filename", "pasted_logs.txt")
        use_ai = body.get("use_ai", use_ai)
        content = validate_pasted_text(raw_content, filename=filename)

    else:
        raise HTTPException(
            status_code=422,
            detail="Send logs as multipart/form-data (file upload) or application/json ({content, filename}).",
        )

    result: AnalysisResult = engine.analyze(content, filename)
    investigation: InvestigationReport = build_investigation_report(result, use_ai=use_ai)

    # Return flat response: original fields + investigation key
    result_dict = result.model_dump()
    result_dict["investigation"] = investigation.model_dump()
    return result_dict
