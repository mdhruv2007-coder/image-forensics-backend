# Backend Lead — AI Prompt Implementation Plan

Companion to `backend-lead.md`, not a replacement. That doc is your full reference; this one gives ready-to-paste AI prompts for generating each file you own, in build order, with exactly what to upload alongside each one.

**How to use this doc:** work top to bottom. Upload the files each prompt asks for even if you think you remember their contents — the receiving AI has no memory of this project beyond what you give it.

---

## File 1 of 9: `forensics/schemas.py` — the contract

**Build order note:** first file, no dependencies. Everything else in this project — your own later files, and every teammate's P2–P8 work — is built against this.

**Files to upload alongside this prompt:** none yet (this is the first file). If you've already drafted the six contract-question answers from Section 7/10 of your role doc, paste them directly into the prompt instead of as an attachment.

**Prompt:**

```
I'm building the API contract for an image-tampering-detection FastAPI
backend. This file, forensics/schemas.py, is the single source of truth
every other module in the project (four detection layers, a fusion
function, and a separate React frontend) is built against.

Using Pydantic v2, define:

1. LayerResult — the output of one detection layer (ELA, noise residual,
   copy-move, or an AI-generated-image classifier). Fields: layer_name
   (str), score (float, 0-1, higher = more suspicious), reliability
   (Literal["low","medium","high"]), status (Literal["ok","skipped",
   "failed"]), detail (a free-form dict for layer-specific extra data,
   e.g. match-line coordinates for copy-move), and an optional
   heatmap_png_b64 (str | None) for layers that produce a visual
   heatmap.

2. AnalysisResult — the full response of one analysis. Fields: verdict
   (Literal["authentic","suspicious","likely_tampered"]), tamper_score
   (float, 0-1, the fused score), per_layer (list[LayerResult]),
   explanation (list[str], plain-English reasons from the explainability
   module), metadata (dict, EXIF/file metadata findings),
   coordinate_space (a small nested model describing the normalized
   image size the overlay/heatmap coordinates are relative to — include
   width and height as ints), offline_mode (bool, whether this analysis
   ran with any layers skipped due to no-internet fallback), and
   generated_at (a UTC ISO-8601 timestamp string).

3. ErrorResponse — a clean error shape for failed requests: error
   (str, short machine-readable code like "no_image_provided" or
   "pipeline_failure"), message (str, human-readable), and detail
   (str | None).

4. AnalyzeRequest is NOT a Pydantic body model — note in a comment that
   the actual endpoint accepts multipart/form-data with a single file
   field named "image", not a JSON body, so there's no request schema
   to define here beyond that comment.

Requirements:
- Every field needs a clear one-line docstring or Field(description=...).
- Use Pydantic v2 syntax (model_config, Field, not v1-style Config
  classes).
- Add a model_config = ConfigDict(json_schema_extra={...}) on
  AnalysisResult with one fully-filled realistic example, so FastAPI's
  /docs page shows a concrete sample response, not just field names.
- Python 3.11, full type hints, PEP 8.

This file will be imported with zero other project dependencies (no
FastAPI imports here) — forensics/ is a pure-Python package.
```

---

## File 2 of 9: `app/core/config.py` + `.env.example`

**Build order note:** depends on nothing. Do this alongside or right after schemas.py.

**Files to upload alongside this prompt:** none required, but mention your exact env var list (below) so the AI doesn't invent different names.

**Prompt:**

```
Write app/core/config.py for a FastAPI project using pydantic-settings
(not plain os.environ calls). It should define a Settings class reading
these environment variables, with sensible defaults for local
development:

- ENVIRONMENT (str, default "development")
- CORS_ORIGINS (str, comma-separated list of allowed origins, default
  "http://localhost:5173" — parse this into an actual list[str] via a
  field_validator or computed property, don't leave it as a raw string
  the rest of the app has to re-split)
- MODEL_CACHE_DIR (str, default "./models_cache")
- MAX_IMAGE_SIDE (int, default 1600)
- LOG_LEVEL (str, default "INFO")
- OFFLINE_MODE (bool, default False — parse the string "true"/"false"
  from the env correctly)

Export a single module-level `settings = Settings()` instance that the
rest of the app imports, so there's exactly one source of config truth.

Also write a matching .env.example file with all six variables set to
sensible local-dev defaults and a one-line comment above each explaining
what it controls.

Python 3.11, full type hints, PEP 8.
```

---

## File 3 of 9: `app/main.py`

**Build order note:** depends on `app/core/config.py` existing (for CORS origins).

**Files to upload alongside this prompt:** `app/core/config.py`.

**Prompt:**

```
Write app/main.py, the FastAPI application entrypoint, for an image-
forensics API. I have a config.py (attached) with a settings object
exposing cors_origins as a list[str].

Requirements:

1. Create the FastAPI() app instance with a title and version.
2. Add CORSMiddleware configured from settings.cors_origins — allow
   credentials, all methods, all headers, but restrict origins to
   exactly the configured list (no wildcard "*" in production).
3. Define a GET /health endpoint returning {"status": "ok"} — no auth,
   no dependencies, should always succeed if the process is alive.
4. Include a clear placeholder comment showing exactly where and how
   future routers will be registered, e.g.:
   # from app.api.routes_analyze import router as analyze_router
   # app.include_router(analyze_router, prefix="/api")
   so when routes_analyze.py exists later, adding it is a one-line
   change, not a restructure.
5. Write clean, well-documented Python 3.11 code, type hints throughout,
   PEP 8.

Don't add any routes beyond /health yet — this file's job right now is
just to be a working, deployable skeleton.
```

---

## File 4 of 9: `forensics/layers/base.py` + `forensics/mock_result.py`

**Build order note:** `base.py` is the protocol every layer module (yours and teammates') implements — needs to exist before ML/Forensics start their layer files in earnest, even though they may start from the task tracker's description alone if you're slow. `mock_result.py` depends on `schemas.py`.

**Files to upload alongside this prompt:** `forensics/schemas.py`.

**Prompt:**

```
I have a Pydantic schemas file (attached, forensics/schemas.py) defining
LayerResult and AnalysisResult for an image forensics pipeline. Write two
files:

1. forensics/layers/base.py — define a Layer protocol (using
   typing.Protocol) that every detection layer module implements: a
   single method `run(image: PIL.Image.Image) -> LayerResult` (import
   LayerResult from the attached schemas module). Also include a small
   helper function `make_skipped_result(layer_name: str, reason: str) ->
   LayerResult` that layers can call when they can't run (e.g. no
   internet, unsupported format) — it should produce a LayerResult with
   status="skipped" and a human-readable detail explaining why, so this
   pattern is consistent across all four layers rather than each one
   inventing its own shape for "I didn't run."

2. forensics/mock_result.py — a function `get_mock_result(scenario:
   str = "tampered") -> AnalysisResult` supporting at least three
   scenarios: "tampered" (high tamper_score, multiple suspicious layers,
   a fake base64 PNG string — just use a short valid placeholder base64
   PNG, doesn't need to be a real image), "authentic" (low tamper_score,
   all layers low-reliability-suspicious or clean), and
   "degraded" (one layer with status="skipped", offline_mode=True,
   still produces a valid verdict from the remaining layers). Also
   write a small script (if __name__ == "__main__") that dumps all
   three scenarios' JSON to stdout, so I can redirect it into a file
   the frontend team can use directly as mock data.

Python 3.11, full type hints, PEP 8. Keep the mock data realistic enough
that someone building a UI against it would build the full UI (loading
states, skipped-layer states, both verdict colors), not just a happy-path
view.
```

---

## File 5 of 9: `forensics/pipeline.py` + `app/api/routes_analyze.py`

**Build order note:** this is E1, the core integration — depends on all four layer modules existing (`ai_detector.py` from ML, `ela.py`/`noise_residual.py`/`copy_move.py` from Forensics, `metadata.py` is yours), plus `fusion.py` and `verdicts.py`. Don't run this prompt until those exist, or run it against stub/placeholder versions and re-run once the real layers land.

**Files to upload alongside this prompt:** `forensics/schemas.py`, `forensics/layers/base.py`, all four layer files (or stubs), `forensics/fusion.py`, `forensics/verdicts.py`, `forensics/utils/image_io.py`.

**Prompt:**

```
I have a set of Python modules for an image forensics pipeline (all
attached): a schemas file defining AnalysisResult/LayerResult, a Layer
protocol, four layer implementations (an AI-image classifier, ELA, noise
residual, and copy-move detection), a fusion module, a verdicts module,
and an image I/O utility for loading/validating/resizing images.

Write forensics/pipeline.py with a single function:

    def analyze(image_bytes: bytes) -> AnalysisResult

that:
1. Uses the attached image_io module to load and validate the bytes,
   normalizing to the longest-side cap it already implements.
2. Calls each of the four attached layers' .run() method on the
   normalized image, collecting their LayerResult objects. If a layer
   raises an exception, catch it and convert to a skipped/failed
   LayerResult using the base.py helper rather than letting the whole
   pipeline crash — one broken layer shouldn't take down the others.
3. Passes the four LayerResults into the attached fusion module to get
   a fused tamper_score, and into the attached verdicts module to get
   the final verdict label.
4. Assembles and returns a complete AnalysisResult matching the attached
   schema exactly, including coordinate_space from the normalized image
   dimensions and a generated_at UTC timestamp.

Then write app/api/routes_analyze.py, a FastAPI router that:
1. Defines a POST /api/analyze endpoint accepting multipart/form-data
   with a single file field named "image" (use FastAPI's UploadFile).
2. Validates the upload is actually an image (reasonable content-type
   check) and returns a 422 with the attached ErrorResponse shape if not.
3. Calls pipeline.analyze() on the uploaded bytes and returns the
   resulting AnalysisResult as the response, with response_model set
   so FastAPI's /docs page documents the real return shape.
4. Catches any unhandled pipeline exception and returns a 500 with an
   ErrorResponse rather than leaking a raw traceback.
5. Has a clear docstring describing exactly what this endpoint returns,
   referencing the AnalysisResult shape.

Python 3.11, full type hints, PEP 8, clean docstrings throughout.
```

---

## File 6 of 9: `forensics/fusion.py` + `forensics/verdicts.py` + config YAMLs

**Build order note:** needed before File 5 can be meaningfully run — build this before or alongside the pipeline integration.

**Files to upload alongside this prompt:** `forensics/schemas.py`, `forensics/layers/base.py`.

**Prompt:**

```
I have a schemas file (attached) defining LayerResult (score 0-1,
reliability low/medium/high, status ok/skipped/failed) and AnalysisResult.
Write two modules and two YAML config files for an image forensics
fusion step:

1. config/fusion_weights.yaml — a simple structure mapping each of four
   layer names ("ai_detector", "ela", "noise_residual", "copy_move") to
   a float weight (should sum to 1.0), with placeholder-reasonable
   starting values I can tune later without touching code.

2. config/thresholds.yaml — two float thresholds: one separating
   "authentic" from "suspicious", one separating "suspicious" from
   "likely_tampered", on the same 0-1 scale as the fused score.

3. forensics/fusion.py — a function `fuse(layer_results: list[LayerResult],
   weights_path: str = "config/fusion_weights.yaml") -> float` that:
   - Loads weights from the YAML file (don't hardcode them).
   - Computes a weighted average of each layer's score, but RE-NORMALIZES
     the weights among only the layers with status=="ok" if any layer
     was skipped or failed (so a skipped layer doesn't silently drag the
     score toward zero just because its weighted slot went unfilled).
   - Returns a single float 0-1.

4. forensics/verdicts.py — a function `classify(tamper_score: float,
   thresholds_path: str = "config/thresholds.yaml") -> str` returning
   one of "authentic", "suspicious", "likely_tampered" based on the two
   thresholds loaded from YAML.

Python 3.11, full type hints, PEP 8. Both functions should be pure
(no side effects beyond reading the YAML files) so they're easy to unit
test with hand-constructed LayerResult lists.
```

---

## File 7 of 9: `forensics/layers/metadata.py`

**Build order note:** your own layer module (the EXIF one) — no dependency beyond `base.py` and `schemas.py`.

**Files to upload alongside this prompt:** `forensics/layers/base.py`, `forensics/schemas.py`.

**Prompt:**

```
I have a Layer protocol and LayerResult schema (attached). Write
forensics/layers/metadata.py implementing a metadata/EXIF inspection
layer:

1. A class or function matching the attached Layer protocol's run(image)
   signature, using Pillow's getexif() and the exifread library to pull
   EXIF data from the image.
2. Flag as suspicious (higher score) when: EXIF is entirely missing from
   what should normally have it (suggesting re-saving/editing), the
   Software tag indicates a known editing tool (Photoshop, GIMP, etc. —
   check against a short list of common editor names), or timestamps are
   inconsistent/missing in a way that suggests metadata stripping.
3. Score low (low suspicion) when EXIF looks like an untouched camera
   original (consistent make/model/timestamp fields present).
4. Return the actual extracted EXIF fields in the LayerResult.detail
   dict so the UI can show "what we found," not just the score.
5. Use the base.py helper to return a skipped result cleanly if the
   image format doesn't support EXIF at all (e.g. a PNG with no EXIF
   block) rather than treating "no EXIF" the same as "suspicious" —
   these are different situations and conflating them would be
   misleading in the final report.

Python 3.11, full type hints, PEP 8, clear docstring explaining the
suspicion heuristic.
```

---

## File 8 of 9: `forensics/offline.py` + `scripts/run_offline.ps1`

**Build order note:** E7 — depends on `pipeline.py` and all four layers existing, since this wraps them.

**Files to upload alongside this prompt:** `forensics/pipeline.py`, `app/core/config.py`.

**Prompt:**

```
I have a pipeline.py (attached) that runs four detection layers and a
config.py (attached) exposing settings.offline_mode as a bool. Write
forensics/offline.py with:

1. A function `should_skip_layer(layer_name: str) -> bool` that, when
   settings.offline_mode is True, returns True for any layer requiring
   a downloaded ML model (currently just "ai_detector") and False for
   the purely classical layers (ela, noise_residual, copy_move,
   metadata) — these should always run regardless of offline_mode,
   since they need no internet at any point.
2. Document clearly in a module docstring that offline_mode in this
   project means two distinct things: (a) at the Python level, whether
   to skip the AI-model layer at runtime, and (b) operationally, that
   this whole backend plus the separate frontend can be run with zero
   internet access via localhost, as a fallback if the deployed Render/
   Vercel URLs are unreachable — note that (b) requires no special code,
   just running both services locally, and this module only implements
   (a).

Then write scripts/run_offline.ps1, a PowerShell script that:
1. Activates the venv.
2. Sets $env:OFFLINE_MODE = "true" for this process only (not
   persisted to .env).
3. Runs `uvicorn app.main:app --reload --port 8000`.

Python 3.11, full type hints, PEP 8 for the .py file; plain commented
PowerShell for the .ps1.
```

---

## File 9 of 9: `app/api/routes_report.py` + `forensics/report/json_report.py` + `forensics/report/pdf_report.py` (stretch — cut first if behind)

**Build order note:** E9, explicitly the lowest-priority item in the tracker. Only run this prompt if E1, E4, and E7 are already solid — don't let this eat time that belongs to the Must-priority tasks.

**Files to upload alongside this prompt:** `forensics/schemas.py`.

**Prompt:**

```
I have a schemas file (attached) defining AnalysisResult. Write three
files for a stretch-goal "downloadable report" feature on an image
forensics API — note the JSON report itself doesn't need a backend
endpoint (the frontend already has the AnalysisResult client-side from
the main analyze call and can download it directly as a blob), so skip
building a JSON-report endpoint. Only the PDF needs server-side work:

1. forensics/report/json_report.py — a thin function
   `format_report(result: AnalysisResult) -> dict` that wraps the
   AnalysisResult in a slightly richer shape for a human-readable report:
   adds a disclaimer string ("automated forensic analysis, not a legal
   determination") and a report-generated timestamp, keeping all the
   original fields nested under a "result" key.

2. forensics/report/pdf_report.py — a function
   `generate_pdf(result: AnalysisResult) -> bytes` using reportlab that
   produces a simple one-to-two-page PDF: a title, the verdict and
   tamper score prominently, a table of per-layer scores and
   reliability, the plain-English explanation bullets, and the
   disclaimer from json_report.py. Keep the layout simple — no custom
   fonts or assets, just reportlab's built-in styles; this is a stretch
   feature and should not eat significant time.

3. app/api/routes_report.py — a FastAPI router with a single
   POST /api/report/pdf endpoint that accepts an AnalysisResult as a
   JSON request body (the frontend already has this object from the
   earlier /api/analyze call and just re-sends it), calls generate_pdf(),
   and returns the PDF bytes with the correct
   media_type="application/pdf" and a Content-Disposition header
   suggesting a filename like "forensics-report.pdf".

Python 3.11, full type hints, PEP 8. Keep all three files short — this
is explicitly the first thing to cut if time runs out, so it shouldn't
be the most polished code in the project.
```
