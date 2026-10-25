import os
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from ..analysis.engine import AnalysisEngine
from ..models.schemas import AnalysisResult

router = APIRouter(prefix="/api")
engine = AnalysisEngine()

MAX_BYTES = 5 * 1024 * 1024  # 5 MB — enforced on the backend; client-side check is UX only

_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/sample")
async def get_sample() -> dict:
    """Return the bundled sample incident log for the Load Sample action."""
    fixture_path = os.path.join(_FIXTURES_DIR, "sample_incident.log")
    if os.path.exists(fixture_path):
        with open(fixture_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        # Slice 1 placeholder — sample is authored in Slice 2
        content = (
            '{"timestamp":"2024-01-15T10:00:00Z","level":"INFO",'
            '"message":"Sample incident log not yet available","service":"api"}\n'
        )
    return {"content": content, "filename": "sample_incident.log"}


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(
    request: Request,
    file: Optional[UploadFile] = File(default=None),
) -> AnalysisResult:
    """
    Accept a log file (multipart/form-data) or pasted text (application/json).
    Enforces 5 MB limit on both paths. Returns a complete AnalysisResult.
    """
    content_type = request.headers.get("content-type", "")

    if file is not None:
        # --- File upload path ---
        raw_bytes = await file.read(MAX_BYTES + 1)
        if len(raw_bytes) > MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Log input exceeds 5 MB limit. Upload a smaller file or paste a subset.",
            )
        try:
            content = raw_bytes.decode("utf-8", errors="replace")
        except Exception:
            raise HTTPException(status_code=422, detail="Could not decode file as UTF-8 text.")
        filename = file.filename or "uploaded.log"

    elif "application/json" in content_type:
        # --- Paste path ---
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid JSON body.")
        content = body.get("content", "")
        filename = body.get("filename", "pasted_logs.txt")
        if len(content.encode("utf-8")) > MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Log input exceeds 5 MB limit. Paste a smaller subset.",
            )

    else:
        raise HTTPException(
            status_code=422,
            detail="Send logs as multipart/form-data (file upload) or application/json ({content, filename}).",
        )

    if not content.strip():
        raise HTTPException(status_code=422, detail="Input is empty.")

    result = engine.analyze(content, filename)
    return result
