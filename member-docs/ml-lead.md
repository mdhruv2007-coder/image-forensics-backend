# ML Lead — Role Doc

Project: **Image Tampering & Deepfake Forensics Suite**
Repo you work in: `image-forensics-backend` (same repo as Backend Lead — you don't own a separate repo, you own a slice of this one)
Architecture: FastAPI backend (Render) + React frontend (Vercel)
Devices: native Windows, Google Antigravity or VS Code

---

## 1. Identity & Role

**You are the ML Lead.** You own:
- The AI-generated-image classifier layer (`forensics/layers/ai_detector.py`) and the script that caches its weights locally (`scripts/download_models.py`).
- Dataset curation: the demo image set and the larger test/calibration set (`scripts/prepare_demo_set.py`, `data/demo_images/`, `data/test_images/`).
- Explainability: turning raw layer results into plain-English reasons a judge can read (`forensics/explain/explainer.py`, `config/explain_templates.yaml`).
- Calibration: tuning the fusion weights and verdict thresholds against real data (`scripts/evaluate.py`, `scripts/calibrate.py`), and writing up what you measured (`docs/CALIBRATION_REPORT.md`, `docs/KNOWN_LIMITS.md`).

**Total load:** per the task tracker, your pre-build work (P2, P3) plus event-day work (E5, E6) — you're the one who makes sure the "AI detector" part of this AI-image-forensics project is actually honest about what it can and can't do, which matters more for this project's credibility than almost anything else in it.

---

## 2. Full Environment Setup From Absolute Zero

### 2.1 Python + Git

Same base setup as Backend Lead's doc, Sections 2.1 and 2.3 — Python 3.11.x from python.org (not the Windows Store build), Git installed, PATH checked during Python install.

### 2.2 Clone the backend repo

Backend Lead creates and pushes `image-forensics-backend` first. Once you have the clone URL:

```powershell
cd D:\ImageForensics-Hackathon
git clone https://github.com/<your-github-username>/image-forensics-backend.git
cd image-forensics-backend
```

You work in this same repo as everyone else on the backend side — there's no separate "ML repo." Your files live under `forensics/layers/ai_detector.py`, `forensics/explain/`, `scripts/`, and `data/`.

### 2.3 venv + dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

**Don't skip the CPU-only torch index URL.** A plain `pip install torch` on Windows can pull a multi-GB CUDA build you don't need — you're running CPU inference the entire time, both locally and on Render.

### 2.4 Download and cache the model

Once `scripts/download_models.py` exists (you write it, P3):

```powershell
python scripts/download_models.py
```

This should cache `umm-maybe/AI-image-detector`'s weights into `models_cache/` (gitignored, path controlled by the `MODEL_CACHE_DIR` env var). Do this once, in pre-build, on good wifi — the model's weights are ~330MB. **Do not rely on downloading this live during the event**, and definitely don't rely on Render re-downloading it on every deploy if you can avoid it (check whether Render's disk persists between deploys on your plan, or bake the cache into the build step if not).

### 2.5 Confirm the model loads

```powershell
python -c "from forensics.layers.ai_detector import run_detector; print('ok')"
```
(exact import path depends on how `ai_detector.py` is structured — confirm against whatever `base.py`'s `Layer` protocol ends up specifying).

### 2.6 A note on memory, up front

This model (`umm-maybe/AI-image-detector`, a Swin Transformer, ~330MB of fp32 weights) plus torch plus transformers realistically needs close to 1GB+ RAM once loaded and running inference. This is fine on your own laptop. It is **not** fine on Render's free or Starter tiers (512MB cap) — Backend Lead is handling the Render tier choice (Standard, 2GB), but you should know this is why, in case the deployed service behaves differently than your local run.

---

## 3. Git Workflow

- **Branch naming:** `ml-<short-feature>`, e.g. `ml-ai-detector`, `ml-calibration`, `ml-demo-set`.
- **Commits:** Conventional Commits lite — `feat:`, `fix:`, `docs:`, `data:` (for dataset/manifest changes), `chore:`.
- **PRs:** Backend Lead reviews anything touching `forensics/layers/ai_detector.py` (since it has to conform to their `base.py` protocol) and anything touching `config/fusion_weights.yaml` / `config/thresholds.yaml` (since Backend Lead owns the structure of those files — you only change the numbers). Forensics Lead is a good second reviewer on `explainer.py` since their layer outputs feed directly into your explanation text.
- **Merge strategy:** squash-merge into `main`.
- Dataset files (`data/demo_images/`, `data/test_images/`) can get large — don't commit raw images if the manifest-and-script-regenerates-them pattern works instead; if you do commit actual image files, keep the demo set small (8-10 images) and the test set reasonable (20-30), per the tracker.

---

## 4. Your Specific Ownership — Exact Files and Folders

```
image-forensics-backend/
├── forensics/
│   ├── layers/
│   │   └── ai_detector.py             [ML]  P3    Layer 1 — HF classifier, conforms to base.py's Layer protocol
│   ├── explain/
│   │   └── explainer.py               [ML]  E5    LayerResults -> plain-English reasons
│   └── (you do not touch pipeline.py, fusion.py, verdicts.py, schemas.py, or any other layer file)
├── config/
│   ├── explain_templates.yaml         [ML]  E5    wording templates for "why flagged"
│   ├── fusion_weights.yaml            [BE creates structure → you tune the numeric values]  E6
│   └── thresholds.yaml                [BE creates structure → you tune the numeric values]  E6
├── scripts/
│   ├── download_models.py             [ML]  P3    caches HF weights into models_cache/
│   ├── prepare_demo_set.py            [ML]  P2    copies chosen images from raw datasets, writes manifest
│   ├── evaluate.py                    [ML]  E6    metrics on demo + test sets
│   └── calibrate.py                   [ML]  E6    tunes weights/thresholds, writes YAML
├── data/
│   ├── demo_images/                   [ML]  P2    8–10 curated: real / spliced / copy_move / ai_generated
│   │   └── manifest.csv               [ML]        filename, label, source, licence, expected_verdict
│   ├── test_images/                   [ML]  E6    20–30 extra
│   │   └── manifest.csv               [ML]
│   └── datasets_raw/                  gitignored — CASIA v2 / CoMoFoD (check licences before using)
├── tests/
│   ├── test_ai_detector.py            [ML]
│   └── test_explainer.py              [ML]
└── docs/
    ├── CALIBRATION_REPORT.md          [ML]  E6    measured results only — no invented numbers
    └── KNOWN_LIMITS.md                [ML]        facts for the "Known limits" slide
```

**Note:** `config/fusion_weights.yaml` and `config/thresholds.yaml` have their *structure* (keys, nesting) owned by Backend Lead. You only edit the numeric values inside, during E6. If you need a new key, ask Backend Lead — don't restructure the file yourself.

---

## 5. Your Dependencies — What You Need FROM Others, and When

| From | What | Due | Blocks |
|---|---|---|---|
| Backend Lead | `forensics/layers/base.py` — the `Layer` protocol | Pre-build, right after P1 | `ai_detector.py` has a concrete interface to implement against |
| Backend Lead | The locked schema (`schemas.py`'s `LayerResult` shape) | Pre-build, same window | Knowing exactly what fields your layer's output needs to populate |
| Forensics Lead | Their layer outputs (ELA, noise, copy-move `LayerResult`s) — at least representative examples, doesn't need to be their final code | Pre-build, informal | `explainer.py` needs to generate text for all four layers, not just yours — you need a sense of what their `detail` dicts look like |
| Backend Lead | A working `pipeline.py` producing real `AnalysisResult`s end-to-end | Event hr 2 (E1) | `evaluate.py` and `calibrate.py` need real pipeline output to measure against, not just your layer in isolation |

---

## 6. What Others Need FROM You, and When

| Who | What | Due | Why it blocks them |
|---|---|---|---|
| Backend Lead | `ai_detector.py` conforming to the `Layer` protocol | Pre-build (P3) | `pipeline.py` integration (E1) needs all four layers present |
| Everyone | The demo image set + manifest | Pre-build (P2) | `smoke_test.py` (Backend Lead's) and general dev testing need something to run against |
| Backend Lead | `explain_templates.yaml` + `explainer.py` producing real explanation strings | Event hr 4.5 (E5) | `AnalysisResult.explanation` needs real content, not a placeholder, for the UI's explain panel to be worth demoing |
| Frontend & Pitch Lead | Final calibrated `fusion_weights.yaml` / `thresholds.yaml` | Event hr 5 (E6) | The verdict labels shown in the demo should reflect tuned numbers, not pre-build placeholders, by the time rehearsal starts |
| Frontend & Pitch Lead | `docs/KNOWN_LIMITS.md` content | By E6/E12 | This becomes the "Known limits" slide in the pitch deck — Frontend & Pitch Lead needs your actual findings, not something they guess at |

---

## 7. The Reasoning Behind Technical Decisions Relevant to Your Work

**Why a pre-trained classifier, not training your own.** Training any reasonably robust AI-image classifier from scratch needs a real dataset, a real training loop, and real compute time — none of which exist in an 8-hour (or even a 17.5-hour pre-build) budget. `umm-maybe/AI-image-detector` is a Swin Transformer already fine-tuned for exactly this binary task. The job here is wrapping it well and being honest about its limits, not building a better one.

**Why this layer alone can never be the whole story.** A classifier trained to spot "does this look AI-generated" answers a different question than "was this specific real photo edited." A skillfully retouched real photo can score low on an AI-generation classifier while still being tampered — that's precisely why Layers 2–4 (ELA, noise residual, copy-move) exist alongside this one, and why the fused score weighs all four rather than deferring to the AI layer alone. When you write explanation text, don't let it imply the AI layer is the primary signal — it's one of four, and for localized splice/copy-move edits it's often the *least* informative one.

**Why calibration has to use real measured numbers, not round ones.** The task tracker's own risk register flags "team over-claims accuracy and gets challenged" as a real risk at the demo. If a judge asks "what's your false-positive rate" and the honest answer is "we measured 15% on our 20-image test set," say that — don't round up to a nicer-sounding number, and don't present the demo-set performance (which you tuned against) as if it were held-out performance. `CALIBRATION_REPORT.md` should distinguish clearly between numbers measured on the demo set (which you calibrated against, so they're optimistic) and numbers measured on the separate test set (which is the more honest signal, even if it's smaller and noisier).

**Why `explainer.py` needs templates, not generated prose.** `config/explain_templates.yaml` is a set of fill-in-the-blank phrasings keyed to score ranges and layer combinations, not an LLM call generating fresh text at request time. This is faster, fully deterministic for the demo (no risk of a weird or wrong sentence appearing live), and good enough — the point is translating four numeric scores into something a judge reads in two seconds, not literary quality.

---

## 8. Deployment — Your Role In It

You don't drive either deployment (Backend Lead owns Render, Frontend & Pitch Lead owns Vercel), but two things are on you before either deploy matters:

1. **Confirm the model actually fits and runs on Render's Standard tier (2GB RAM) before the event**, not after. Once Backend Lead's Render service is live, push a test image through the deployed `/api/analyze` endpoint yourself and watch for timeouts or 500s — don't assume your local success means the deployed version behaves the same. CPU inference speed on Render's shared compute may be slower than your laptop; if `ai_detector.py` takes more than a few seconds per image, consider whether that's acceptable for a live demo or needs a smaller/faster model swap.
2. **Hand Frontend & Pitch Lead your `KNOWN_LIMITS.md` content early** — they need real content for the architecture/pitch slides, not a placeholder they have to chase you for during the final hour.

---

## 9. Handoff Notes

- Nothing is built yet — pre-build hasn't started as of this plan.
- **Dataset licensing**: CASIA v2 and CoMoFoD both have usage terms — check them before committing raw images into the repo or using them in anything demo-facing judges might ask about. If licensing is unclear, prefer images you have clear rights to use, even if it means a smaller curated set.
- **The "known limits" slide is not optional polish** — per the risk register, an unexamined claim of accuracy is one of the likelier ways this project loses credibility with judges. Treat `KNOWN_LIMITS.md` as seriously as the detector code itself.
- **If you fall behind**, E6 (calibration) is more valuable to protect than polishing `explainer.py`'s wording — a correctly-thresholded verdict matters more than elegant explanation text. If you have to choose, keep the thresholds honest and let the explanation text be simpler.

---

## 10. Full Implementation Checklist

### Pre-Build (complete before event day — due "event hour 0")

- [ ] Clone `image-forensics-backend` once Backend Lead has pushed the initial skeleton
- [ ] Confirm CPU-only torch install, confirm `requirements.txt` has what you need
- [ ] **P2:** download/select CASIA v2 or CoMoFoD subset, check licensing, curate 8-10 demo images across real / spliced / copy-move / AI-generated categories, write `manifest.csv`
- [ ] **P3:** `forensics/layers/ai_detector.py` wrapping the HF pipeline, conforming to `base.py`'s `Layer` protocol; `scripts/download_models.py` caching weights locally
- [ ] Confirm the model loads and produces a sane score on at least one demo image, locally

### Event Day (Hour 0 → 8)

- [ ] **Hour 4.5 (E5):** `forensics/explain/explainer.py` + `config/explain_templates.yaml` — real plain-English explanations wired into the live pipeline
- [ ] **Hour 5 (E6):** `scripts/evaluate.py` + `scripts/calibrate.py` run against the test set; updated `fusion_weights.yaml` / `thresholds.yaml` values; `docs/CALIBRATION_REPORT.md` and `docs/KNOWN_LIMITS.md` written with real measured numbers
- [ ] Push calibrated config changes before Frontend & Pitch Lead's final rehearsal pass
- [ ] Spot-check the deployed Render endpoint once live, not just your local run
- [ ] Hand off `KNOWN_LIMITS.md` content to Frontend & Pitch Lead for the pitch deck
