"""FastAPI application entrypoint for the image-forensics API.

Run locally with:

    uvicorn app.main:app --reload --port 8000

Configuration is read from ``app.core.config.settings``; nothing here touches
``os.environ`` directly.
"""

from __future__ import annotations

from typing import Final

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_analyze import router as analyze_router
from app.core.config import settings

APP_TITLE: Final[str] = "Image Forensics API"
APP_VERSION: Final[str] = "0.1.0"


def _validate_cors_origins(origins: list[str]) -> list[str]:
    """Fail fast if the configured CORS origins include a wildcard."""
    if "*" in origins:
        raise RuntimeError(
            "CORS_ORIGINS must list explicit origins; the wildcard '*' is "
            "not permitted because credentials are enabled."
        )
    return origins


app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_validate_cors_origins(settings.cors_origins_list),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=dict[str, str], tags=["meta"])
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


# routes_analyze.py already declares the full path "/api/analyze" on its
# routes, so it is included WITHOUT a prefix. Adding prefix="/api" here would
# produce /api/api/analyze.
app.include_router(analyze_router)

# routes_report.py: send it to me and I'll wire it in the same way.