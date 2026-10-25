from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import analyze

app = FastAPI(
    title="TraceGuard AI API",
    version="0.1.0",
    description="Deterministic incident investigation backend.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev
        "http://localhost:4173",  # Vite preview
        "http://frontend:5173",  # Docker Compose service name
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router)
