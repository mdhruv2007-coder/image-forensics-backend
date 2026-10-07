"""Download and cache the AI-image-detector model for offline use.

Downloads ``umm-maybe/AI-image-detector`` (a Swin Transformer image
classifier, roughly 330MB of weights) together with its preprocessor
config into ``MODEL_CACHE_DIR``, using the standard Hugging Face hub
cache layout (``MODEL_CACHE_DIR/models--umm-maybe--AI-image-detector/
snapshots/<commit>/...``). ``forensics/layers/ai_detector.py`` loads the
model with ``from_pretrained(MODEL_ID, cache_dir=MODEL_CACHE_DIR,
local_files_only=True)``, which expects exactly this layout — a flat
directory of files will NOT be found.

Usage:
    python scripts/download_models.py

Environment:
    MODEL_CACHE_DIR  Target directory (default: ./models_cache).

Exit codes:
    0  Model is cached (freshly downloaded or already present).
    1  Download failed or the downloaded files are incomplete.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

MODEL_ID: str = "umm-maybe/AI-image-detector"
DEFAULT_CACHE_DIR: str = "./models_cache"

# Files that must exist for ``from_pretrained(..., cache_dir=...,
# local_files_only=True)`` to work offline.
REQUIRED_CONFIG_FILES: tuple[str, ...] = (
    "config.json",
    "preprocessor_config.json",
)
WEIGHT_FILE_CANDIDATES: tuple[str, ...] = (
    "model.safetensors",
    "pytorch_model.bin",
)

# Skip weight formats for other frameworks to avoid wasted bandwidth.
IGNORE_PATTERNS: list[str] = [
    "*.msgpack",
    "*.h5",
    "*.onnx",
    "*.ot",
    "*.tflite",
]


def resolve_cache_dir() -> Path:
    """Return the model cache directory as an absolute path.

    Prefers the application's own settings object (which also honours a
    ``.env`` file) so this script and the app always agree on the
    location. Falls back to reading the environment directly when the
    app package cannot be imported.
    """
    raw: str
    try:
        # Make `app` importable when running as `python scripts/...`.
        project_root = Path(__file__).resolve().parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from app.core.config import settings

        raw = settings.MODEL_CACHE_DIR
    except Exception:  # noqa: BLE001 - any import/config problem -> env fallback
        raw = os.environ.get("MODEL_CACHE_DIR", DEFAULT_CACHE_DIR)
    return Path(raw).expanduser().resolve()


def _find_snapshot_dir(cache_dir: Path) -> Path | None:
    """Return the model's snapshot directory inside the hub cache, if any.

    Hub cache layout is ``cache_dir/models--<org>--<name>/snapshots/<commit>/``.
    There is normally exactly one snapshot once a download completes; if
    more than one exists (e.g. after a model update), the most recently
    modified one is used.
    """
    snapshot_root = cache_dir / f"models--{MODEL_ID.replace('/', '--')}" / "snapshots"
    if not snapshot_root.is_dir():
        return None
    snapshots = [p for p in snapshot_root.iterdir() if p.is_dir()]
    if not snapshots:
        return None
    return max(snapshots, key=lambda p: p.stat().st_mtime)


def is_model_cached(cache_dir: Path) -> bool:
    """Return True if ``cache_dir`` holds a complete, loadable model."""
    snapshot = _find_snapshot_dir(cache_dir)
    if snapshot is None:
        return False
    has_configs = all((snapshot / name).is_file() for name in REQUIRED_CONFIG_FILES)
    has_weights = any((snapshot / name).is_file() for name in WEIGHT_FILE_CANDIDATES)
    return has_configs and has_weights


def download_model(cache_dir: Path) -> None:
    """Download the model snapshot into ``cache_dir`` (hub cache layout).

    Raises:
        Exception: Any error raised by ``huggingface_hub`` (network
            failures, HTTP errors, filesystem errors) is propagated to
            the caller.
    """
    from huggingface_hub import snapshot_download

    cache_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_ID,
        cache_dir=str(cache_dir),
        ignore_patterns=IGNORE_PATTERNS,
    )


def main() -> int:
    """Entry point. Returns a process exit code."""
    cache_dir = resolve_cache_dir()
    print(f"Model:     {MODEL_ID}")
    print(f"Cache dir: {cache_dir}")

    if is_model_cached(cache_dir):
        print("Model already cached; skipping download.")
        return 0

    print(
        "Model not found in cache. Downloading (~330MB). "
        "This may take several minutes; keep the connection stable..."
    )

    try:
        download_model(cache_dir)
    except ImportError:
        print(
            "ERROR: huggingface_hub is not installed. "
            "Run `pip install huggingface_hub` and try again.",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print(
            "\nERROR: Download interrupted. Re-run the script to resume.",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:  # noqa: BLE001 - report any download failure clearly
        print(
            f"ERROR: Failed to download {MODEL_ID}: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        print(
            "Check your network connection and disk space, then re-run. "
            "Partial downloads are resumed automatically.",
            file=sys.stderr,
        )
        return 1

    if not is_model_cached(cache_dir):
        print(
            f"ERROR: Download finished but no complete snapshot was found "
            f"under {cache_dir} (expected a 'models--...' / 'snapshots' / "
            f"<commit> directory containing {', '.join(REQUIRED_CONFIG_FILES)} "
            f"plus one of {', '.join(WEIGHT_FILE_CANDIDATES)}).",
            file=sys.stderr,
        )
        return 1

    print(f"Done. Model cached at {cache_dir}")
    print(
        "Load it offline with: from_pretrained(MODEL_ID, "
        "cache_dir=MODEL_CACHE_DIR, local_files_only=True)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
