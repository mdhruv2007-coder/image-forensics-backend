"""FastAPI application entrypoint for the image-forensics API.
 
Run locally with:
 
    uvicorn app.main:app --reload
 
Configuration is read from ``config.settings``; nothing here touches
``os.environ`` directly.
"""
 
from __future__ import annotations
 
from typing import Final
 
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
 
from app.core.config import settings 
APP_TITLE: Final[str] = "Image Forensics API"
APP_VERSION: Final[str] = "0.1.0"
 
 
def _validate_cors_origins(origins: list[str]) -> list[str]:
    """Fail fast if the configured CORS origins include a wildcard.
 
    A ``"*"`` origin is incompatible with ``allow_credentials=True``
    (browsers reject the combination), and it would also expose the API
    to every website. Raising at startup is preferable to a silently
    broken or insecure deployment.
 
    Args:
        origins: The parsed list of allowed origins from settings.
 
    Returns:
        The same list, if it is safe to use.
 
    Raises:
        RuntimeError: If any origin is the wildcard ``"*"``.
    """
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
    """Liveness probe.
 
    Intentionally has no authentication, no dependencies, and no I/O so
    that it succeeds whenever the process is able to serve requests.
 
    Returns:
        A static payload indicating the service is up.
    """
    return {"status": "ok"}
 
 
# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------
# Future routers are registered here. When a new router module exists,
# uncomment the two lines below (or add an equivalent pair) and nothing
# else in this file needs to change:
#
#     from app.api.routes_analyze import router as analyze_router
#     app.include_router(analyze_router, prefix="/api")
# ---------------------------------------------------------------------------
 