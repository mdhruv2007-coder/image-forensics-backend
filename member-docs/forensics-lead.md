# Forensics Lead — Role Doc

Project: **Image Tampering & Deepfake Forensics Suite**
Repo you work in: `image-forensics-backend` (shared with Backend Lead and ML Lead — you don't own a separate repo)
Architecture: FastAPI backend (Render) + React frontend (Vercel)
Devices: native Windows, Google Antigravity or VS Code

---

## 1. Identity & Role

**You are the Forensics Lead.** You own the three classical image-forensics layers and their visualizations:
- Error Level Analysis (`forensics/layers/ela.py`)
- Noise residual analysis (`forensics/layers/noise_residual.py`)
- Copy-move detection via ORB/SIFT (`forensics/layers/copy_move.py`, `forensics/viz/match_lines.py`)
- The heatmap visualization these produce (`forensics/viz/overlay.py`)
- Edge-case testing once the pipeline is stable (`scripts/generate_edge_cases.py`, `data/edge_cases/`)
- A late patch to `forensics/utils/image_io.py` (Backend Lead's file — you only touch it after event hour 6)

Your three layers are the ones that can actually say *where* in an image something looks wrong — the AI-detector layer (ML Lead's) answers "does this look AI-made," yours answer "does this specific region look edited." That distinction is worth keeping in mind when you write detail output, since it's what the explainability panel and the heatmap are built to show off.

---

## 2. Full Environment Setup From Absolute Zero

### 2.1 Python + Git

Same as the other docs — Python 3.11.x from python.org, PATH checked, Git installed.

### 2.2 Clone the backend repo

```powershell
cd D:\ImageForensics-Hackathon
git clone https://github.com/<your-github-username>/image-forensics-backend.git
cd image-forensics-backend
```

### 2.3 venv + dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

You don't need the CPU-torch special install step — your three layers are pure OpenCV/NumPy/SciPy, no model weights involved. (Backend Lead and ML Lead need that step; you don't.)

### 2.4 Confirm OpenCV has SIFT

Copy-move detection needs feature matching. Modern `opencv-python-headless` ships SIFT in the main package (it was patent-encumbered in older OpenCV versions and lived in `opencv-contrib`; this is no longer the case in current releases). Confirm:

```powershell
python -c "import cv2; print(cv2.SIFT_create())"
```
If this errors, you likely have a stale or mismatched OpenCV install — reinstall `opencv-python-headless` at the version pinned in `requirements.txt`, don't mix it with `opencv-python` (the GUI variant) in the same venv.

### 2.5 Get test images early

You don't own `data/demo_images/` (ML Lead does), but you'll want a handful of images with known copy-move and splice edits to develop against before the curated demo set exists. Grab 3-4 test images yourself (even just quick manual edits in any image editor) so you're not blocked waiting on ML Lead's P2.

---

## 3. Git Workflow

- **Branch naming:** `forensics-<short-feature>`, e.g. `forensics-ela`, `forensics-copy-move`, `forensics-overlay`.
- **Commits:** Conventional Commits lite — `feat:`, `fix:`, `docs:`, `test:`, `chore:`.
- **PRs:** Backend Lead reviews anything touching `forensics/layers/base.py`-conforming interfaces or `forensics/utils/image_io.py` (since that file is theirs and you're only patching it, late, by agreement). ML Lead is a reasonable second reviewer on `overlay.py` since the heatmap it produces feeds directly into what `explainer.py` describes.
- **Merge strategy:** squash-merge into `main`.
- **The `image_io.py` patch (E8) specifically needs its own small PR**, clearly flagged, reviewed by Backend Lead before merge — it's a shared foundational file every layer depends on, and an unreviewed change there can break things invisibly for everyone.

---

## 4. Your Specific Ownership — Exact Files and Folders

```
image-forensics-backend/
├── forensics/
│   ├── layers/
│   │   ├── ela.py                     [FX]  P4    Layer 2a — Error Level Analysis
│   │   ├── noise_residual.py          [FX]  P5    Layer 2b — noise residual
│   │   └── copy_move.py               [FX]  P6    Layer 3 — ORB/SIFT copy-move detection
│   ├── viz/
│   │   ├── overlay.py                 [FX]  E3    colorized heatmap PNG only — no blending, see Section 7
│   │   └── match_lines.py             [FX]  P6    draws lines between duplicated regions
│   └── utils/
│       └── image_io.py                [BE creates P1 → you patch E8, after event hour 6 only]
├── scripts/
│   └── generate_edge_cases.py         [FX]  E8    PNG, WhatsApp-recompressed, screenshot, oversized-file test cases
├── data/
│   └── edge_cases/                    [FX]  E8
└── tests/
    ├── test_ela.py                    [FX]
    ├── test_noise_residual.py         [FX]
    ├── test_copy_move.py              [FX]
    ├── test_overlay.py                [FX]
    └── test_edge_cases.py             [FX]
```

**On `image_io.py`:** Backend Lead writes the initial version in P1 (load, validate, normalize size). You patch it at E8 — and the tracker is specific that this is "after event hour 6 only." The reason: every layer depends on this file, including ones you don't own. Touching it early, before the other layers are stable, risks breaking integration for everyone at the worst possible time. Wait until the edge-case testing (E8) actually surfaces a real need (e.g. a format `image_io.py` doesn't handle), then patch it narrowly for that case.

---

## 5. Your Dependencies — What You Need FROM Others, and When

| From | What | Due | Blocks |
|---|---|---|---|
| Backend Lead | `forensics/layers/base.py` — the `Layer` protocol | Pre-build, right after P1 | Your three layer files have a concrete interface to implement |
| Backend Lead | The locked schema (`schemas.py`'s `LayerResult` shape, including the `detail` dict convention) | Pre-build, same window | Knowing what to put in `detail` for copy-move's match coordinates, ELA's region flags, etc. |
| Backend Lead | Initial `forensics/utils/image_io.py` | P1 | Your layers need normalized images to run against |
| Backend Lead | A working `pipeline.py` | Event hr 2 (E1) | Confirms your layers actually integrate, not just pass isolated unit tests |

---

## 6. What Others Need FROM You, and When

| Who | What | Due | Why it blocks them |
|---|---|---|---|
| Backend Lead | `ela.py` | Pre-build (P4) | Pipeline integration (E1) needs all four layers |
| Backend Lead | `noise_residual.py` | Pre-build (P5) | Same |
| Backend Lead | `copy_move.py` + `match_lines.py` | Pre-build (P6) | Same |
| Frontend & Pitch Lead | `overlay.py` producing the colorized heatmap PNG | Event hr 3 (E3) | The `ImageCompare` component's original-vs-heatmap view has nothing to show without this |
| Everyone | Edge-case test results | Event hr 6 (E8) | If a layer breaks on a specific file type (huge files, WhatsApp-recompressed JPEGs, screenshots), this needs to surface before the demo, not during it |

---

## 7. The Reasoning Behind Technical Decisions Relevant to Your Work

**Why ELA degrades on PNG, and what to do about it.** Error Level Analysis works by re-compressing the image at a known JPEG quality and measuring the difference — it's fundamentally a JPEG-artifact technique. Run it on a PNG (lossless, no compression artifacts to begin with) and the signal is close to meaningless. Two things follow: (1) if the input is a PNG, `ela.py` should either re-encode to JPEG first and flag this in `detail` so the explanation panel can say "re-encoded for analysis," or return a `reliability="low"` result rather than a confident-looking score computed on noise — don't let a PNG silently produce a high-confidence ELA score, since that's actively misleading. (2) Flag this limitation explicitly in whatever you hand ML Lead for `docs/KNOWN_LIMITS.md` — this is exactly the kind of thing a sharp judge might ask about.

**Why copy-move is worth the extra build time (P6 gets 3 hours, the most of any single pre-build task).** It's the layer most likely to produce an unambiguous, visually compelling result — two clearly duplicated regions connected by a line is immediately legible to a non-technical judge in a way a numeric score isn't. ORB is faster than SIFT but less robust to scaling/rotation of the duplicated region; SIFT is slower but more reliable. Given this runs once per uploaded image rather than at video frame rate, prefer SIFT's robustness unless you measure it being too slow for a responsive demo — if it is, ORB as a fallback is a reasonable tradeoff, just don't make that swap silently; note it in your handoff.

**Why the heatmap is a separate, un-blended PNG now.** In the original single-process plan, blending onto the original image (with an adjustable opacity) happened server-side on every slider interaction. In the split FastAPI+React architecture, re-calling the backend per slider tick would be slow and pointless. So `overlay.py`'s job narrows to: run `cv2.applyColorMap` on the tamper-probability map, encode as PNG, base64 it into the `LayerResult`. The *blending* — stacking it over the original with adjustable CSS opacity — is now a frontend concern, done instantly client-side with zero network calls. This also simplifies your function signature: no opacity parameter to pass through anymore, just "produce the heatmap," once.

**Why edge-case testing now also needs to cover the HTTP boundary, not just the Python functions.** In the old plan, "huge file" and "weird format" were purely in-process concerns. Now there's a real multipart upload over HTTP, which means new failure modes exist that didn't before: FastAPI/Starlette's default upload size limits, Render's request timeout on a slow-processing large image, and CORS-related failures that look like "nothing happened" from the browser's side rather than a clean error. When you run `generate_edge_cases.py`'s scenarios, test at least the "huge file" case against the actual deployed endpoint, not just `analyze()` called directly in a Python script — a failure at the HTTP layer looks completely different from a failure inside the pipeline, and only testing the latter will miss it.

---

## 8. Deployment — Your Role In It

You don't drive either deployment, but:

1. Once Backend Lead's Render service is live, **run your edge-case images against the real deployed endpoint**, not just your local copy — Render's CPU and memory profile differs from your laptop, and copy-move detection (SIFT, the slowest of your three layers) is the one most likely to behave differently under real deployment constraints.
2. Flag to Backend Lead immediately if you find the deployed version times out or behaves differently than local — this is diagnostic information they need, not something to quietly work around on your end.

---

## 9. Handoff Notes

- Nothing is built yet — pre-build hasn't started as of this plan.
- **The `image_io.py` "after hour 6 only" rule is a real constraint, not a suggestion** — if you find a need to patch it earlier (say, at hour 3), talk to Backend Lead directly rather than just doing it; there may be a reason it's gated that late, or there may not be and they'll say go ahead, but it should be a conversation, not a solo decision.
- **SIFT vs ORB is a decision worth revisiting once you have real timing data**, not something to lock in blind during pre-build. Note your actual measured per-image processing time somewhere visible (a code comment, a line in your PR description) so Backend Lead and ML Lead have context if the live demo feels slow.
- **The heatmap-blending split (Section 7) is a genuine architecture decision, not just "how it happened to get built"** — if anyone (including a future AI assistant picking up this project) tries to "fix" `overlay.py` by adding opacity blending back in server-side, that's a regression, not an improvement. Point them at this doc's Section 7 if it comes up.

---

## 10. Full Implementation Checklist

### Pre-Build (complete before event day — due "event hour 0")

- [ ] Clone `image-forensics-backend`, set up venv, confirm `cv2.SIFT_create()` works
- [ ] Grab 3-4 manual test images (don't wait on ML Lead's curated demo set to start developing)
- [ ] **P4:** `forensics/layers/ela.py` — including the PNG-reconversion/low-reliability handling from Section 7
- [ ] **P5:** `forensics/layers/noise_residual.py`
- [ ] **P6:** `forensics/layers/copy_move.py` + `forensics/viz/match_lines.py` (3-hour budget — the biggest single pre-build task, worth the time)

### Event Day (Hour 0 → 8)

- [ ] **Hour 3 (E3):** `forensics/viz/overlay.py` — colorized heatmap PNG, no blending logic
- [ ] **Hour 6 (E8):** `scripts/generate_edge_cases.py` + `data/edge_cases/` — PNG input, WhatsApp-recompressed JPEG, a plain screenshot, an oversized file; test against both the local pipeline **and** the live deployed endpoint
- [ ] **After hour 6, only if a real need surfaced in E8:** narrow patch to `forensics/utils/image_io.py`, reviewed by Backend Lead
- [ ] Hand off any measured timing data (especially copy-move's) to Backend Lead and ML Lead before final rehearsal
