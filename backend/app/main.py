from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .db.session import engine, Base, check_db_health
from .models import db as db_models  # Ensure models are registered with Base.metadata
from .routers import analyze_router, auth_router, incidents_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        print(f"Warning: Could not initialize database tables on startup: {exc}")
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Deterministic incident investigation workspace with secure authentication and multi-tenancy.",
    lifespan=lifespan,
)

import re
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


@app.middleware("http")
async def security_and_correlation_middleware(request: Request, call_next):
    # Correlation ID handling
    incoming_req_id = request.headers.get("X-Request-ID", "").strip()
    if incoming_req_id and _REQUEST_ID_REGEX.match(incoming_req_id):
        request_id = incoming_req_id
    else:
        request_id = uuid.uuid4().hex

    request.state.request_id = request_id

    response: Response = await call_next(request)

    # Attach correlation ID to response
    response.headers["X-Request-ID"] = request_id

    # Attach hardened security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self' https: http://localhost:* http://127.0.0.1:* ws://localhost:* ws://127.0.0.1:*; "
        "frame-ancestors 'none';"
    )

    return response

# Liveness healthcheck at root (standard for cloud load balancers and Render)
@app.get("/health", tags=["Health"])
async def root_health() -> dict:
    return {"status": "ok"}

# Detailed database status endpoint
@app.get("/api/health/db", tags=["Health"])
async def db_health() -> dict:
    return check_db_health()

app.include_router(analyze_router)
app.include_router(auth_router)
app.include_router(incidents_router)


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.getenv("PORT", "8010"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
