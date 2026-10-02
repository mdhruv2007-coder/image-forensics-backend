# Forensics Lead — AI Prompt Implementation Plan

Companion to `forensics-lead.md`. Ready-to-paste prompts for each file you own, in build order.

---

## File 1 of 6: `forensics/layers/ela.py`

**Build order note:** P4. Depends on `forensics/layers/base.py` and `forensics/schemas.py` (Backend Lead's).

**Files to upload alongside this prompt:** `forensics/layers/base.py`, `forensics/schemas.py`.

**Prompt:**

```
I have a Layer protocol and LayerResult schema (attached) for an image
forensics pipeline. Write forensics/layers/ela.py implementing Error
Level Analysis:

1. Implement a class or function matching the attached Layer protocol's
   run(image: PIL.Image.Image) -> LayerResult signature.
2. Core ELA technique: re-save the image at a known JPEG quality (e.g.
   quality=90), reload it, and compute the per-pixel difference between
   the original and the re-saved version, scaled/amplified for
   visibility. Areas with unusually high error levels relative to the
   rest of the image suggest localized editing.
3. Compute an overall suspicion score (0-1) from the error-level map —
   e.g. based on the variance or max-vs-median ratio of error across
   regions, where a few sharply higher-error regions against an
   otherwise-consistent background suggests tampering more than
   uniformly-elevated error (which often just means a generally
   low-quality source image).
4. IMPORTANT — handle non-JPEG input correctly: if the input image's
   original format is already lossless (e.g. PNG) with no prior JPEG
   compression history, ELA's signal is much weaker/less meaningful.
   In that case, still run the technique (re-encode as JPEG and
   compare) but set reliability="low" explicitly rather than reporting
   a confident-looking score, and note in LayerResult.detail that the
   input was re-encoded for analysis and the result should be weighted
   accordingly.
5. Put the computed error-level map in LayerResult.detail as a base64
   PNG (grayscale or false-color, your choice) so later visualization
   code has access to the raw map, separate from whatever overlay.py
   does with it.
6. Use the base.py helper for a clean skipped result if the image can't
   be processed at all (corrupt file, unsupported mode).

Python 3.11, full type hints, PEP 8, use Pillow + NumPy. Add a module
docstring explaining ELA's JPEG-artifact basis and its PNG limitation
explicitly, so this isn't a hidden gotcha for whoever reads the code
next.
```

---

## File 2 of 6: `forensics/layers/noise_residual.py`

**Build order note:** P5. Same dependencies as File 1.

**Files to upload alongside this prompt:** `forensics/layers/base.py`, `forensics/schemas.py`.

**Prompt:**

```
I have a Layer protocol and LayerResult schema (attached). Write
forensics/layers/noise_residual.py implementing noise residual analysis
for tamper detection:

1. Implement run(image: PIL.Image.Image) -> LayerResult per the attached
   protocol.
2. Extract the image's noise residual using a denoising filter (e.g.
   a median filter or a wavelet-based denoiser via SciPy/scikit-image if
   available, otherwise a simple Gaussian-blur-and-subtract approach is
   an acceptable fallback) — subtract the denoised version from the
   original to isolate the noise pattern.
3. Different regions of a single untouched photo should show a
   reasonably consistent noise pattern (same camera sensor, same
   processing pipeline). A spliced-in region from a different source
   image typically shows a different noise signature. Compute a
   suspicion score based on local noise-pattern inconsistency across
   the image (e.g. divide into a grid of patches, compute a noise
   statistic per patch, and flag high variance between patches as
   suspicious — simpler than a full co-occurrence-matrix approach, which
   is out of scope for the time budget here).
4. Put the noise residual map (or the per-patch inconsistency heatmap)
   into LayerResult.detail as a base64 PNG.
5. Use the base.py skipped-result helper for corrupt/unsupported images.
6. Note in a module docstring that this technique is inherently noisier
   and lower-precision than ELA or copy-move — set a conservative upper
   bound on reliability (never "high", cap at "medium") unless the
   inconsistency signal is extremely clear, since false positives from
   ordinary lighting/exposure variation across a real photo are common.

Python 3.11, full type hints, PEP 8, Pillow + NumPy + SciPy.
```

---

## File 3 of 6: `forensics/layers/copy_move.py` + `forensics/viz/match_lines.py`

**Build order note:** P6, the largest single pre-build task (3 hours). Same base dependencies.

**Files to upload alongside this prompt:** `forensics/layers/base.py`, `forensics/schemas.py`.

**Prompt:**

```
I have a Layer protocol and LayerResult schema (attached). Write two
files implementing copy-move forgery detection:

1. forensics/layers/copy_move.py — implement run(image:
   PIL.Image.Image) -> LayerResult per the attached protocol:
   - Use OpenCV's SIFT (cv2.SIFT_create() — this is in the main
     opencv-python-headless package in current versions, not
     opencv-contrib) to detect keypoints and compute descriptors across
     the image.
   - Match descriptors against each other (not against a second image —
     this is detecting duplicated regions WITHIN the same image) using
     a FLANN or brute-force matcher, applying a ratio test to filter
     weak matches, and explicitly excluding trivial self-matches (a
     keypoint matching itself or an immediate neighbor) which aren't
     evidence of copy-move.
   - Cluster the remaining matched keypoint pairs into one or more
     candidate duplicated regions (a simple approach: group matches
     whose spatial displacement vector — the offset between a keypoint
     and its match — clusters together, since a real copy-move forgery
     usually has a consistent translation/rotation between the original
     and pasted region).
   - Compute a suspicion score (0-1) based on how many strong,
     non-trivial matched pairs survive clustering, and how consistent
     their displacement vectors are.
   - Put the matched keypoint pairs (as pixel coordinates, in the
     normalized image's coordinate space) into LayerResult.detail so
     match_lines.py (below) can draw them, and so the API response can
     expose exact coordinates to the frontend if needed.
   - Use the base.py skipped-result helper if SIFT fails to initialize
     or the image has too few keypoints to analyze meaningfully (e.g. a
     nearly blank image).

2. forensics/viz/match_lines.py — a function `draw_match_lines(image:
   PIL.Image.Image, matched_pairs: list[tuple]) -> bytes` that takes the
   original image and the matched keypoint pairs from copy_move.py's
   detail output, draws lines connecting each duplicated region pair
   (using OpenCV's line-drawing functions, a distinct bright color per
   cluster if there are multiple candidate duplicated regions), and
   returns the result as PNG bytes ready for base64 encoding.

Python 3.11, full type hints, PEP 8, use OpenCV + NumPy. Add a comment
noting the SIFT-vs-ORB tradeoff (SIFT is more robust to rotation/scale
in the duplicated region but slower; ORB is a faster drop-in alternative
if processing time becomes an issue) so swapping later is a one-line
change, not a rewrite.
```

---

## File 4 of 6: `forensics/viz/overlay.py`

**Build order note:** E3, event day. Depends on whichever layer is producing the probability/suspicion map you're visualizing — could be any of your three layers, or a combined map.

**Files to upload alongside this prompt:** `forensics/schemas.py`, and whichever of your layer files already has a `detail` map you're visualizing (e.g. the ELA error-level map).

**Prompt:**

```
I have a schemas file (attached) and a layer module producing a
grayscale suspicion/error map as part of its output (attached). Write
forensics/viz/overlay.py with a single function:

    def make_heatmap_png(suspicion_map: np.ndarray) -> str

that:

1. Takes a 2D NumPy array (values 0-1, same dimensions as the analyzed
   image) representing per-pixel or per-region tamper suspicion.
2. Applies a perceptually sensible color map using
   cv2.applyColorMap (e.g. COLORMAP_JET or COLORMAP_TURBO — pick
   whichever reads most clearly as "blue/green = low suspicion, red =
   high suspicion" to someone with no technical background).
3. Encodes the result as a PNG and returns it as a base64-encoded string
   (not raw bytes — this needs to go directly into a JSON response
   field and then into a frontend <img src="data:image/png;base64,...">
   tag).

IMPORTANT — do NOT blend this onto the original image, and do NOT accept
an opacity parameter. This function's only job is producing the
colorized heatmap on its own, as a separate image. Blending it over the
original with an adjustable opacity happens client-side in the frontend
via CSS, specifically so a slider drag doesn't require a new network
request per frame — keep this function simple and stateless, returning
just the one colorized PNG every time.

Python 3.11, full type hints, PEP 8, OpenCV + NumPy.
```

---

## File 5 of 6: `scripts/generate_edge_cases.py` + edge-case tests

**Build order note:** E8, due event hour 6. Depends on a stable pipeline to test against — don't run this until E1 is solid.

**Files to upload alongside this prompt:** `forensics/pipeline.py`, a couple of your demo/test images.

**Prompt:**

```
I have a working pipeline.py (attached) for an image forensics API, and
need to stress-test it against unusual input before a live demo. Write:

1. scripts/generate_edge_cases.py — a script that takes a couple of
   clean source images (attached, or read from a folder I specify) and
   generates these edge-case variants into data/edge_cases/:
   - A PNG version of a photo that's normally JPEG (tests the ELA
     low-reliability path)
   - A heavily recompressed JPEG simulating WhatsApp's re-encoding
     (save at a low quality, multiple times, to mimic real-world
     messaging-app degradation)
   - A plain screenshot-style image (flat colors, UI elements, no
     camera noise or EXIF at all — tests how the pipeline handles
     "this was never a photograph" input)
   - An oversized file (upscale or pad a source image well past typical
     phone-camera resolution, to test size handling / timeout behavior)
   Each generated file should be named descriptively
   (e.g. edge_case_png_from_jpeg.png, edge_case_whatsapp_compressed.jpg)
   so it's obvious what each one is testing just from the filename.

2. tests/test_edge_cases.py — a pytest file that runs the attached
   pipeline's analyze() function against every file in data/edge_cases/
   and asserts, at minimum, that: (a) it never raises an unhandled
   exception for any of these inputs (a skipped/low-reliability result
   is fine, a crash is not), and (b) the PNG-from-JPEG case specifically
   produces an ELA layer result with reliability == "low", confirming
   the handling described in ela.py actually works end-to-end.

Python 3.11, full type hints, PEP 8, pytest conventions for the test
file (clear test names, one assertion focus per test function where
reasonable).
```

---

## File 6 of 6: Patch to `forensics/utils/image_io.py` (only after event hour 6, only if E8 surfaces a real need)

**Build order note:** this is the one file you don't own outright — Backend Lead wrote the original. Only touch it if `generate_edge_cases.py` actually surfaces a concrete failure this file needs to handle, and get Backend Lead's review on the resulting PR before merging.

**Files to upload alongside this prompt:** the current `forensics/utils/image_io.py`, plus whatever specific edge-case failure you hit (error message, or a description of the wrong behavior).

**Prompt:**

```
I have an existing image_io.py module (attached) that loads, validates,
and normalizes incoming images for a forensics pipeline — it's owned by
a teammate, and I'm making a narrow, targeted patch, not a rewrite.

The specific problem I hit during edge-case testing: [DESCRIBE THE
EXACT FAILURE HERE — e.g. "oversized images (>8000px on the long side)
cause a MemoryError during the resize step" or "a specific PNG with an
alpha channel crashes the normalize_size function because it assumes
3-channel RGB input"].

Make the smallest possible change to the attached file that fixes this
specific case, without restructuring existing functions, renaming
anything, or changing behavior for any input that was already working
correctly. Show me a clear diff-style explanation of exactly what
changed and why, so I can explain the change in one sentence when I ask
the file's owner to review it.

Python 3.11, full type hints, PEP 8, consistent with the attached file's
existing style.
```
