# syntax=docker/dockerfile:1

FROM python:3.11-slim

# --- System deps -------------------------------------------------------
# libgl1 / libglib2.0-0: required at import-time by opencv-python-headless
# even though it's the "headless" build (cv2 still links against these).
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- Python deps ---------------------------------------------------------
# Copied and installed before the rest of the source so Docker can cache
# this layer across pushes that don't touch requirements.txt.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# --- App source ------------------------------------------------------------
COPY . .

# Intentionally NOT set:
#   - ENV MODEL_CACHE_DIR=...
#   - RUN python scripts/download_models.py
# With no cache dir configured, ai_detector._resolve_cache_dir() raises
# ModelUnavailableError on first use and run() returns make_skipped_result(),
# matching local pre-model-load behavior. See HF Space secrets/variables too
# -- MODEL_CACHE_DIR must stay unset there as well.

# HF Spaces routes traffic to 7860, not 8000.
EXPOSE 7860

# Create a non-root user (HF Spaces/Docker best practice; also avoids
# permission surprises if you later mount a volume for cache/outputs).
RUN useradd --create-home --uid 1000 appuser
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
