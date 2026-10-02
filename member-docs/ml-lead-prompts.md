# ML Lead — AI Prompt Implementation Plan

Companion to `ml-lead.md`. Ready-to-paste prompts for each file you own, in build order.

---

## File 1 of 6: `scripts/prepare_demo_set.py` + `data/demo_images/manifest.csv`

**Build order note:** P2, no dependencies on anyone else's code. Do this first — it's independent of the schema lock and the earliest thing you can ship.

**Files to upload alongside this prompt:** none required, but describe any images you've already manually selected so the script matches your actual folder layout rather than inventing one.

**Prompt:**

```
I'm curating a small demo image set for an image-tampering-detection
hackathon project. I need a script, scripts/prepare_demo_set.py, that:

1. Takes a source directory of raw candidate images (e.g.
   data/datasets_raw/) and a destination directory (data/demo_images/).
2. Copies a specified subset of images into the destination, organized
   by category: "real" (untouched photos), "spliced" (one region from
   another image pasted in), "copy_move" (a region duplicated within
   the same image), and "ai_generated" (fully AI-generated images).
3. Writes data/demo_images/manifest.csv with columns: filename, label
   (one of the four categories above), source (where the image
   originally came from, e.g. "CASIA v2" or "CoMoFoD"), licence (a
   short licence/usage note I fill in by hand per image), and
   expected_verdict (one of "authentic", "suspicious", "likely_tampered"
   — my own judgment of what the pipeline should ideally say about this
   image, for later comparison against what it actually says).
4. Takes the specific list of filenames-to-category mappings as a
   simple Python dict or a small input CSV I provide, rather than trying
   to auto-classify images itself — I'm doing the curation judgment
   manually, this script just automates the copying and manifest
   generation so I'm not doing it by hand for 8-10 files.
5. Prints a summary at the end: how many images per category, and flags
   if any category has zero images (so I don't silently end up with an
   unbalanced demo set).

Python 3.11, full type hints, PEP 8, use pathlib not os.path.
```

---

## File 2 of 6: `scripts/download_models.py`

**Build order note:** P3. Depends on nothing except knowing the model name and the `MODEL_CACHE_DIR` env var convention.

**Files to upload alongside this prompt:** `app/core/config.py` if it exists yet (for the exact settings attribute name), otherwise just state the env var name in the prompt.

**Prompt:**

```
Write scripts/download_models.py for a project using the Hugging Face
model umm-maybe/AI-image-detector (an image classification model, a Swin
Transformer architecture, ~330MB of weights). The script should:

1. Read a MODEL_CACHE_DIR path from environment variables (default
   "./models_cache" if unset).
2. Use huggingface_hub's snapshot_download (or an equivalent
   transformers-native caching call) to download and cache the full
   model + its preprocessor config into that directory, so a later
   `from_pretrained(MODEL_CACHE_DIR)` call never touches the network.
3. Skip the download entirely (printing a message) if the model already
   appears to be cached at that path, so re-running this script is safe
   and fast.
4. Print clear progress/status messages, since this is a ~330MB download
   that pre-build should run once on good wifi, not something to re-run
   blindly.
5. Exit with a non-zero status code and a clear error message if the
   download fails (e.g. network error), rather than failing silently.

Python 3.11, full type hints, PEP 8.
```

---

## File 3 of 6: `forensics/layers/ai_detector.py`

**Build order note:** P3, the core ML file. Depends on `forensics/layers/base.py` (the `Layer` protocol) and `forensics/schemas.py` existing — don't run this until Backend Lead has pushed those.

**Files to upload alongside this prompt:** `forensics/layers/base.py`, `forensics/schemas.py`.

**Prompt:**

```
I have a Layer protocol and LayerResult/schemas file (both attached) for
an image forensics pipeline. Write forensics/layers/ai_detector.py
implementing an "AI-generated image" detection layer using the Hugging
Face model umm-maybe/AI-image-detector (a Swin Transformer image
classifier, labels are "artificial"/"human" or similar — check the
model's actual label names at load time rather than hardcoding an
assumption, and map whatever its real output labels are onto this
project's suspicion scale).

Requirements:

1. Load the model from a local cache directory (read the path from
   wherever this project's settings/config object exposes
   MODEL_CACHE_DIR — attach app/core/config.py if you want the AI to
   use the real import, otherwise just read it from an environment
   variable directly) using transformers' pipeline() or
   AutoModelForImageClassification, NOT downloading at runtime — this
   should fail loudly with a clear error message if the cache is empty,
   rather than silently trying to hit the network.
2. Load the model ONCE at module import time (or via a cached singleton
   pattern), not on every call to run() — reloading a ~330MB model per
   request would make this unusably slow.
3. Implement a class or function matching the attached Layer protocol's
   run(image: PIL.Image.Image) -> LayerResult signature:
   - Run inference, get the model's confidence that the image is
     AI-generated.
   - Map that confidence onto this project's 0-1 suspicion score (higher
     = more likely AI-generated / tampered).
   - Set reliability based on how far the confidence is from 0.5 (very
     confident predictions = "high" reliability, near-50/50 = "low").
   - Put the raw model output (both class labels and their raw
     probabilities) in the LayerResult.detail dict for transparency.
4. If model loading fails for any reason (missing cache, corrupted
   files), use the attached base.py helper to return a clean "skipped"
   LayerResult rather than crashing the whole pipeline.
5. Add a one-paragraph docstring at the top of the file noting this
   layer answers "does this look AI-generated," which is a different
   question from "was this specific photo edited" — it should not be
   treated as authoritative on its own.

Python 3.11, full type hints, PEP 8.
```

---

## File 4 of 6: `forensics/explain/explainer.py` + `config/explain_templates.yaml`

**Build order note:** E5. Depends on `schemas.py` and ideally on seeing representative output from all four layers (yours and Forensics Lead's), so the templates cover realistic combinations.

**Files to upload alongside this prompt:** `forensics/schemas.py`, and if available, a few sample `AnalysisResult` JSON outputs (from `mock_result.py` or real pipeline runs) covering different layer combinations.

**Prompt:**

```
I have a schemas file (attached) defining LayerResult (score 0-1,
reliability, status, detail dict) and AnalysisResult, plus some sample
outputs (attached) showing realistic layer combinations. Write:

1. config/explain_templates.yaml — a set of template strings keyed by
   layer name and score range (e.g. "high"/"medium"/"low" suspicion
   bands per layer), written as fill-in-the-blank English sentences a
   non-technical judge could read and immediately understand. Cover all
   four layers: ai_detector, ela, noise_residual, copy_move, plus a
   metadata/EXIF layer. Also include one or two templates for the
   "skipped" status (e.g. "the AI-generation check was skipped because
   no internet connection was available during this analysis").

2. forensics/explain/explainer.py — a function
   `explain(per_layer: list[LayerResult]) -> list[str]` that:
   - Loads the attached templates from the YAML file (don't hardcode
     strings in Python — the YAML is the single source of wording so
     non-engineers on the team can tweak phrasing without touching
     code).
   - For each layer result, picks the matching template based on its
     score band and status, fills in any dynamic values (e.g. the
     specific EXIF software tag found), and returns a list of plain-
     English sentences, one or two per layer, ordered from most to
     least suspicious.
   - Caps the total output at a reasonable number of sentences (e.g. 5)
     so the explanation panel doesn't overwhelm a judge glancing at it
     for a few seconds — prioritize the highest-scoring, most
     informative layers if there are more than that.

Python 3.11, full type hints, PEP 8. Keep the YAML wording honest and
measured — avoid absolute language like "proves" or "definitely"; prefer
"suggests," "is consistent with," "shows signs of."
```

---

## File 5 of 6: `scripts/evaluate.py`

**Build order note:** E6. Depends on a working `pipeline.py` (Backend Lead's E1) and your test image manifest.

**Files to upload alongside this prompt:** `forensics/pipeline.py`, `data/test_images/manifest.csv` (or demo_images manifest if test set isn't ready yet).

**Prompt:**

```
I have a pipeline.py (attached) exposing analyze(image_bytes) ->
AnalysisResult, and a manifest CSV (attached) with columns filename,
label, source, licence, expected_verdict. Write scripts/evaluate.py that:

1. Loads every image listed in the manifest, runs analyze() on each,
   and compares the resulting verdict against the manifest's
   expected_verdict column.
2. Computes and prints: overall accuracy (exact verdict match), a simple
   confusion matrix (rows = expected, columns = actual, for the three
   verdict categories), and per-category accuracy (e.g. how well does it
   do specifically on "copy_move" labeled images vs "ai_generated" ones).
3. Also reports the average processing time per image, since that
   matters for a live demo.
4. Writes all of this to both stdout (human-readable table) and a JSON
   file (data for docs/CALIBRATION_REPORT.md to pull numbers from
   without hand-transcription).
5. Does NOT modify any config files — this script only measures and
   reports, it doesn't tune anything (that's calibrate.py's job).

Python 3.11, full type hints, PEP 8. Be honest in variable naming and
output labeling — don't round numbers in a way that looks better than
they are (e.g. print 0.73 as "73%", not round up to "75%" or similar).
```

---

## File 6 of 6: `scripts/calibrate.py` + `docs/CALIBRATION_REPORT.md` + `docs/KNOWN_LIMITS.md`

**Build order note:** E6, run after or alongside `evaluate.py`. This is the task you should protect most if time runs short — correct thresholds matter more than any other remaining ML work.

**Files to upload alongside this prompt:** `scripts/evaluate.py`'s output JSON (once you have a run), `config/fusion_weights.yaml`, `config/thresholds.yaml`.

**Prompt:**

```
I have evaluation results (attached JSON, from a script that ran our
pipeline against a labeled test set and recorded expected vs actual
verdicts) and two YAML config files (attached) defining fusion weights
per layer and verdict thresholds. Write:

1. scripts/calibrate.py — a script that takes the evaluation results and
   does a simple grid/local search over the threshold values in
   thresholds.yaml (and optionally the weights in fusion_weights.yaml)
   to maximize overall accuracy on the test set, then writes the best
   values found back into those two YAML files, preserving their
   existing structure and comments. Print a before/after accuracy
   comparison so the improvement (or lack of one) is visible.

2. docs/CALIBRATION_REPORT.md — a markdown report template with these
   sections: "Method" (one paragraph on how calibration was done),
   "Demo set results" (the numbers measured on the demo set — labeled
   clearly as optimistic since these were tuned against), "Test set
   results" (numbers on the separate held-out test set — labeled as the
   more honest signal), "Per-category breakdown" (a markdown table:
   category, accuracy, notes), and "Processing time". Leave the actual
   numbers as clearly marked placeholders like [FILL IN: accuracy] for
   me to fill in from the real run — don't invent plausible-looking
   numbers.

3. docs/KNOWN_LIMITS.md — a markdown template with sections: "What this
   system is good at", "What it struggles with" (e.g. heavily compressed
   images degrading ELA signal, small/subtle edits, novel AI generators
   not represented in training data), "False positive / false negative
   notes", and "What we'd do with more time". Again, leave specific
   numbers/findings as [FILL IN: ...] placeholders rather than
   fabricating plausible-sounding limitations I haven't actually
   verified.

Python 3.11, full type hints, PEP 8 for calibrate.py. Plain markdown,
no invented data, for the two docs.
```
