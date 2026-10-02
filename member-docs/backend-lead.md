# Backend Lead — Role Doc

Project: **Image Tampering & Deepfake Forensics Suite**
Team: 4 people, single team, no sub-teams
Architecture: split stack — `image-forensics-backend` (FastAPI, Python 3.11, deployed on Render) + `image-forensics-frontend` (Vite + React + Tailwind, deployed on Vercel)
Event: 8-hour hackathon day, preceded by a separate pre-build phase (17.5 team-hours of pre-build + 14 team-hours of event-day work, 31.5 total per the task tracker)
Devices: all four of you on native Windows, Google Antigravity or VS Code, your choice

This doc assumes you've read the task tracker (the Excel) and the original architecture notes. This is the detailed "how" for your slice of it.

---

## 1. Identity & Role

**You are the Backend Lead.** You own:
- The `image-forensics-backend` repo in full — architecture, the API contract, the integration point everyone else's modules plug into.
- `forensics/schemas.py` — **the contract**. Nobody else edits this file. If someone needs a field changed, they ask you.
- Pipeline integration (`pipeline.py`), score fusion (`fusion.py`, `verdicts.py`), metadata/EXIF (`layers/metadata.py`), the FastAPI app itself (`app/main.py`, `app/api/routes_analyze.py`), local-fallback/offline mode, and report export (stretch).
- The Render deployment of the backend service.

You are also the person everyone else is blocked on at Hour 0 of pre-build. P1 and the schema lock are the two things that gate P2–P8. Do them first, do them carefully, and communicate the instant they're done.

**Total load:** 8.5 hours (per the task tracker — 4.5 pre-build + 4 event-day) plus informal oversight of the contract throughout. If you fall behind, **E9 (report export) is the stretch item to cut first** — it's explicitly tagged "cut first if behind schedule" in the tracker, not reassigned to someone else. Don't let it eat into E1, E4, or E7.

---

## 2. Full Environment Setup From Absolute Zero

All four of you are on native Windows — no WSL, no Docker required for local dev. Everything here installs as native Windows wheels.

### 2.1 Install Python 3.11

1. Download Python 3.11.x from [python.org/downloads](https://www.python.org/downloads/) (not the Windows Store version — it sandboxes paths in ways that cause venv headaches).
2. During install, check **"Add python.exe to PATH"**.
3. Verify:
   ```powershell
   python --version
   # Python 3.11.x
   ```

### 2.2 Install Node.js (for later, if you touch the frontend at all)

You won't own frontend files, but you'll want Node installed to sanity-check the frontend locally when wiring CORS. Grab the current LTS from [nodejs.org](https://nodejs.org/). Verify:
```powershell
node --version
npm --version
```

### 2.3 Install Git + create the backend repo

You're creating both repos as lead. Do this before anyone else needs to clone anything.

```powershell
# Create the parent folder both repos will live in
mkdir D:\ImageForensics-Hackathon
cd D:\ImageForensics-Hackathon

# Create and init the backend repo
mkdir image-forensics-backend
cd image-forensics-backend
git init
git branch -M main
```

Push an empty initial commit so teammates have something to clone immediately:
```powershell
git commit --allow-empty -m "chore: init backend repo"
git remote add origin https://github.com/<your-github-username>/image-forensics-backend.git
git push -u origin main
```

Do the same for the frontend repo (you create it; Frontend & Pitch Lead will own its contents):
```powershell
cd D:\ImageForensics-Hackathon
mkdir image-forensics-frontend
cd image-forensics-frontend
git init
git branch -M main
git commit --allow-empty -m "chore: init frontend repo"
git remote add origin https://github.com/<your-github-username>/image-forensics-frontend.git
git push -u origin main
```

Share both clone URLs with the team immediately — this is the literal first thing that has to happen before any of P2–P9 can start.

### 2.4 Set up the backend venv

```powershell
cd D:\ImageForensics-Hackathon\image-forensics-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks the activation script (`running scripts is disabled on this system`), run once as admin:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 2.5 Install dependencies

Your `requirements.txt` (see Section 4) pins:

```
fastapi
uvicorn[standard]
python-multipart
pydantic
pydantic-settings
Pillow
numpy
scipy
opencv-python-headless
transformers
huggingface_hub
exifread
PyYAML
reportlab
```

**Two gotchas to flag to the whole team up front:**

1. **`python-multipart` is easy to forget and FastAPI's error message when it's missing is unhelpful** — file uploads silently 422 or throw an opaque exception about form parsing. Pin it explicitly; don't rely on it being a transitive dependency.
2. **Don't let plain `pip install torch` run.** On Windows, PyPI's default wheel can pull in a CUDA-capable build that's multiple GB and useless to you (you're running CPU-only). Force the CPU-only index:
   ```powershell
   pip install torch --index-url https://download.pytorch.org/whl/cpu
   ```
   Then install everything else normally:
   ```powershell
   pip install -r requirements.txt
   ```

### 2.6 `.env` setup

Copy `.env.example` to `.env` and fill in:
```
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:5173
MODEL_CACHE_DIR=./models_cache
MAX_IMAGE_SIDE=1600
LOG_LEVEL=INFO
OFFLINE_MODE=false
```

### 2.7 Confirm the skeleton runs

Once `app/main.py` exists (you write it in P1):
```powershell
uvicorn app.main:app --reload --port 8000
```
Visit `http://127.0.0.1:8000/health` — should return `{"status": "ok"}`. Visit `http://127.0.0.1:8000/docs` — FastAPI's auto-generated interactive API docs should load. This `/docs` page is your single source of truth for the contract once routes exist; point teammates at it instead of re-explaining the schema verbally.

### 2.8 IDE setup

Either Google Antigravity or VS Code works identically here — this is a plain Python package with no IDE-specific config needed. If VS Code: install the Python extension and point it at `.venv\Scripts\python.exe` as the interpreter (bottom-right status bar → Select Interpreter).

---

## 3. Git Workflow

- **Branch naming:** `backend-<short-feature>`, e.g. `backend-schema-lock`, `backend-fusion`, `backend-offline-mode`.
- **Commits:** Conventional Commits lite — `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`. Keep them small; a commit per working increment, not one per file.
- **PRs:** since you're the architecture owner, you self-merge your own PRs against `schemas.py`, `pipeline.py`, `fusion.py`, `app/main.py` — there's no one else qualified to block you on these, but **do** open the PR anyway (even to yourself) so there's a record, and tag the Forensics or ML Lead as a reviewer on anything touching a shared config file (see Section 4's shared-file table).
- **Merge strategy:** squash-merge into `main`. Keep `main` always runnable — if `analyze()` is broken, nobody downstream can test against it.
- Push early, push often. The moment `app/main.py` + `/health` exist, push — that's the signal for the team the skeleton is alive.

---

## 4. Your Specific Ownership — Exact Files and Folders

```
image-forensics-backend/
├── README.md                          [BE]            setup, run, API overview
├── CONTRIBUTING.md                    [BE]            branches, commits, PR rules
├── requirements.txt                   [BE]  P1         exact pins
├── requirements-dev.txt               [BE]  P1         pytest, ruff
├── .env.example                       [BE]  P1         ENVIRONMENT, CORS_ORIGINS, MODEL_CACHE_DIR, MAX_IMAGE_SIDE, LOG_LEVEL, OFFLINE_MODE
├── .gitignore                         [BE]  P1         .venv, models_cache/, outputs/, data/datasets_raw/
├── app/
│   ├── main.py                        [BE]  P1         FastAPI app, CORS middleware, /health, router registration
│   ├── core/
│   │   └── config.py                  [BE]  P1         pydantic-settings — single source of env-driven config
│   └── api/
│       ├── routes_analyze.py          [BE]  E1         POST /api/analyze — the core endpoint
│       └── routes_report.py           [BE]  E9         report export endpoints (stretch, cut first if behind)
├── forensics/                         # pure Python, no FastAPI imports anywhere in here
│   ├── __init__.py                    [BE]
│   ├── schemas.py                     [BE]  ★★★ THE CONTRACT — AnalysisResult, LayerResult, ErrorResponse. Only you edit this.
│   ├── config.py                      [BE]            loads YAML configs (fusion_weights, thresholds)
│   ├── mock_result.py                 [BE]            fixed fake AnalysisResult — Frontend builds against this before E1 exists
│   ├── pipeline.py                    [BE]  E1         analyze(image_bytes) -> AnalysisResult
│   ├── fusion.py                      [BE]  P8/E4      weighted tamper score
│   ├── verdicts.py                    [BE]  E4         Authentic / Suspicious / Likely Tampered
│   ├── offline.py                     [BE]  E7         local-fallback + skipped-layer handling — see Section 7
│   ├── layers/
│   │   ├── base.py                    [BE]            Layer protocol + LayerResult helpers
│   │   ├── ai_detector.py             [ML]  P3
│   │   ├── ela.py                     [FX]  P4
│   │   ├── noise_residual.py          [FX]  P5
│   │   ├── copy_move.py               [FX]  P6
│   │   └── metadata.py                [BE]  P7         EXIF
│   ├── viz/
│   │   ├── overlay.py                 [FX]  E3         colorized heatmap PNG only — no blending, see Section 7
│   │   └── match_lines.py             [FX]  P6
│   ├── explain/
│   │   └── explainer.py               [ML]  E5
│   ├── report/
│   │   ├── json_report.py             [BE]  E9         formats AnalysisResult into a report shape (stretch)
│   │   └── pdf_report.py              [BE]  E9         reportlab PDF (stretch, cut first)
│   └── utils/
│       └── image_io.py                [BE creates P1 → FX patches E8]  load, validate, normalise size
├── config/
│   ├── fusion_weights.yaml            [BE creates P8 → ML tunes numbers E6]
│   ├── thresholds.yaml                [BE creates E4 → ML tunes numbers E6]
│   └── explain_templates.yaml         [ML]  E5
├── scripts/
│   ├── setup_windows.ps1              [BE]  P1
│   ├── run_local.ps1 / run_offline.ps1 [BE]  P1/E7     uvicorn local run; run_offline sets OFFLINE_MODE=true
│   ├── smoke_test.py                  [BE]            calls analyze() on every demo image, prints a table
│   ├── download_models.py             [ML]  P3
│   ├── prepare_demo_set.py            [ML]  P2
│   ├── evaluate.py / calibrate.py     [ML]  E6
│   └── generate_edge_cases.py         [FX]  E8
├── data/                               (ML owns contents; you own the folder existing)
├── models_cache/                      gitignored, filled by download_models.py
├── outputs/                           gitignored
├── tests/
│   ├── conftest.py                    [BE]
│   ├── test_schema_contract.py        [BE]  — validates real analyze() output against schemas.py
│   ├── test_pipeline.py / test_fusion.py / test_metadata.py / test_offline.py  [BE]
│   └── test_api_analyze.py            [BE]  — FastAPI TestClient hits the real HTTP endpoint, not just the Python function
└── docs/
    ├── RESULT_SCHEMA.md               [BE]  human-readable mirror of the contract
    ├── CALIBRATION_REPORT.md          [ML]  E6
    └── KNOWN_LIMITS.md                [ML]
```

### Shared-file conflict rules

| File | Rule |
|---|---|
| `forensics/schemas.py` | Only you edit it. Anyone needing a field change asks you directly — don't let someone else patch this to unblock themselves. |
| `config/fusion_weights.yaml`, `config/thresholds.yaml` | You create the structure (keys, nesting). ML Lead changes only the numeric values, in E6. If ML needs a new key, they ask you. |
| `forensics/utils/image_io.py` | You write it in P1. Forensics Lead patches it in E8 — and **only** after event hour 6, once the other layers are stable. Don't let this get touched earlier; it underlies every layer. |
| `app/main.py` | Yours alone. There's no shared `app.py` anymore the way the old single-Streamlit-process plan had — the split architecture actually removes a coordination point you used to have to manage. |

---

## 5. Your Dependencies — What You Need FROM Others, and When

| From | What | Due (event hr, if event-day) | Blocks |
|---|---|---|---|
| — | Nothing upstream. P1 and the schema lock are the first two things that happen, full stop. | Pre-build, hour 0 | Everyone |
| ML Lead | `layers/ai_detector.py` conforming to the `Layer` protocol in `base.py` | Pre-build (P3) | `pipeline.py` integration (E1) |
| Forensics Lead | `layers/ela.py`, `layers/noise_residual.py`, `layers/copy_move.py` conforming to the same protocol | Pre-build (P4–P6) | `pipeline.py` integration (E1) |
| Forensics Lead | `viz/overlay.py` producing the colorized heatmap PNG | Event hr 3 (E3) | Nothing blocks on this for you — it plugs into `AnalysisResult.heatmap_png_b64`, which you've already reserved a field for |
| ML Lead | calibrated values for `fusion_weights.yaml` / `thresholds.yaml` | Event hr 5 (E6) | Final verdict accuracy, not functionality — E4 works with your placeholder defaults until then |

**You are never blocked by Frontend.** The whole point of `mock_result.py` and the FastAPI `/docs` page is that Frontend builds against your contract without needing you to be done first, and you build without needing them to be done at all.

---

## 6. What Others Need FROM You, and When

| Who | What | Due | Why it blocks them |
|---|---|---|---|
| Everyone (ML, Forensics, Frontend) | The locked API contract: `schemas.py` field names/types + the `POST /api/analyze` request/response shape | **Pre-build, immediately after P1 — budget ~1 hour, before P2–P8 start** | P3–P8 are all pre-build tasks that produce data shaped by this contract. If you lock it late, they build against a guess and you get rework later. See Section 7 for exactly what this lock must settle. |
| Frontend & Pitch Lead | `forensics/mock_result.py`, exported as `src/data/mockResult.json` (same shape, just JSON) | Pre-build, same window as the schema lock | Frontend builds every component (`ScoreCard`, `ImageCompare`, `EvidenceTabs`...) against this before your real endpoint exists. If the mock doesn't match the real shape later, every component needs rework. |
| Everyone | `app/main.py` running with `/health` returning 200 | End of P1 | Confirms the skeleton is alive; Frontend can start pointing `fetch` calls at `http://127.0.0.1:8000` even before `/api/analyze` is real. |
| Forensics Lead | `layers/base.py`'s `Layer` protocol definition | P1 | Every layer module (ELA, noise, copy-move, AI detector) is written against this interface — if it changes later, four files need touching, not one. |
| ML Lead, Forensics Lead | Confirmation that `pipeline.py` successfully calls their layer and the result validates against `schemas.py` | Event hr 2 (E1) | This is the actual integration moment — the first time all four layers run end-to-end in one process. |
| Frontend & Pitch Lead | The live Render URL, once deployed | Pre-build, once deployment is set up (see Section 8) | They need it to set `VITE_API_BASE_URL` in Vercel's env vars before the production build. |

---

## 7. The Reasoning Behind Technical Decisions Relevant to Your Work

**Why split into FastAPI + React at all, given the original plan argued hard for one Streamlit process?** The original reasoning (no server, no CORS, nothing to deploy) was correct for a same-day, laptop-only demo. It stops being the right tradeoff the moment you want a persistent, shareable link that outlives the event — which is what a Render+Vercel deploy buys you. The added integration surface (an API contract, CORS, two deploy targets) is real cost, but it's cost you're paying in pre-build, where you have slack, not during the 8-hour event where you don't. That's the actual justification for doing this now rather than during the event itself.

**Why the heatmap is no longer blended server-side.** In the old single-process plan, `overlay.py` took an opacity parameter and did the blend in Python on every interaction, because Streamlit re-runs the whole script on each widget change — a slider drag meant a server-side re-render every tick. In a client-server split, that would mean a network round-trip per pixel of slider movement, which is both slow and pointless. Instead: `viz/overlay.py` now returns **just the colorized heatmap** (the `cv2.applyColorMap` output, PNG, base64-encoded) as one static image per analysis. The frontend stacks it over the original image and controls visibility with a CSS `opacity` value tied to a slider — instant, no network call, no backend involvement after the initial fetch. This also means `overlay.py`'s function signature gets simpler (no opacity parameter to thread through), which is a net simplification, not just a workaround.

**Why "offline mode" means something different now.** The original E7 was insurance against *venue wifi being too slow to download the HF model*. That risk still exists and is still solved the same way — `download_models.py` caches weights locally in pre-build, so the app never needs internet to load the model at runtime. But the split architecture adds a **new** risk the Streamlit plan never had: the live app now depends on reaching Render and Vercel over the internet at all. If venue wifi dies entirely, a laptop-only Streamlit app would have kept working; a Render+Vercel app won't. So `offline.py` and the `run_offline.ps1` script now do double duty: they still gate which layers run without internet, *and* they're what makes the **local fallback** (backend on `localhost:8000`, frontend either `npm run dev` or a pre-built static bundle, both pointed at each other, zero internet) a real, tested, ready-to-go option — not Render/Vercel with the wifi off, but the whole stack running locally instead. Rehearse this exact fallback at least once before the event; don't let it be a theoretical option you've never actually run.

**Why Render, and why not the free tier.** Render runs a long-lived Python process the way this app needs (FastAPI via `uvicorn`, no cold-per-request serverless weirdness). The problem is RAM: `umm-maybe/AI-image-detector`'s weights alone are ~330MB on disk, and loaded into memory alongside torch (~200-300MB overhead just from importing it), transformers, opencv-headless, numpy, and scipy, you're realistically looking at 900MB–1.3GB resident before a single image has been analyzed. Render's free *and* Starter tiers are both capped at 512MB RAM — this will OOM. You need the **Standard tier (2GB RAM, ~$25/month)** for the service that loads the AI detector. It's cheap enough to spin up for the event week and delete afterward. If budget genuinely doesn't allow it, the fallback is: run the AI-detector layer locally only (via the offline/local-fallback path above) and keep the live Render deploy running the classical layers (ELA, noise, copy-move, metadata) alone, which have a far smaller memory footprint — but confirm this tradeoff with ML Lead before deciding, since dropping the AI layer from the live demo changes what judges actually see.

**Why per-layer scores are returned, not just the fused verdict.** This is in the tracker's own note on E4, and it matters because a single "87% tampered" number invites the obvious judge question "how do you know." Returning each layer's individual score and reliability lets the UI show its work — this is also why `schemas.py` needs a `per_layer: list[LayerResult]` field, not just a `verdict: str`.

---

## 8. Deployment — Your Role In It

You own the **backend's** Render deployment end to end. Frontend & Pitch Lead owns Vercel and the final stitching (pointing the frontend's env var at your live URL) — see their doc for that half.

### Steps

1. **Before deploying:** confirm `requirements.txt` is exact (no loose version ranges — pin everything, Render's build environment won't match your laptop otherwise).
2. Push `image-forensics-backend` to GitHub (already done in Section 2.3).
3. On [render.com](https://render.com), create a **New Web Service**, connect the GitHub repo.
4. **Instance type: Standard (2GB RAM)**, not Free or Starter — see Section 7 for why.
5. **Build command:** `pip install -r requirements.txt`
6. **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
7. **Environment variables**, set in the Render dashboard (not committed anywhere):
   ```
   ENVIRONMENT=production
   CORS_ORIGINS=https://<your-vercel-app>.vercel.app,http://localhost:5173
   MODEL_CACHE_DIR=/opt/render/project/src/models_cache
   MAX_IMAGE_SIDE=1600
   LOG_LEVEL=INFO
   OFFLINE_MODE=false
   ```
   You'll need to update `CORS_ORIGINS` once Frontend has an actual Vercel URL — do this early with a placeholder, then correct it the moment the real URL exists. A wrong CORS origin is a silent failure from the browser's perspective (requests just get blocked), so don't leave this for the last hour.
8. First deploy will download and cache the HF model on Render's disk — this takes a few minutes and should happen once, in pre-build, well before the event, not live during a demo.
9. **Confirm `/health` and `/docs` both load on the live Render URL** before telling Frontend it's ready.
10. **Cold-start mitigation, even on Standard:** Standard tier doesn't spin down the way Free/Starter does, so this matters less than it would have — but if you end up on a lower tier for cost reasons, set up a simple keep-alive: anything hitting `/health` every ~10 minutes (a cron job, a free uptime-monitoring service, or even a teammate's phone browser tab refreshing) prevents a judge-facing cold start.
11. **Share the live URL immediately** with Frontend & Pitch Lead the moment it's confirmed working — this is their blocker for finishing the Vercel setup.

---

## 9. Handoff Notes

As of this plan, nothing is built yet — this is pre-build, hour 0. A few things worth flagging for whoever picks this doc up (including future-you, mid-event, when context is thin):

- **The schema lock is the single highest-leverage hour you'll spend.** Everything else in this doc assumes it happened cleanly. Don't rush it to "looks roughly right" — a wrong field name discovered at event hour 4 costs far more than the extra 15 minutes would have at hour 0.
- **`mock_result.py` needs to be realistic, not minimal.** If it's a one-line stub, Frontend builds a UI that only handles the happy path. Give it a believable spread: at least one high-confidence tampered result, one authentic result, and one result with a skipped layer (so the offline/degraded-layer UI path gets exercised before E7 even happens).
- **The RAM finding is new and important enough to repeat here:** don't let anyone assume Render's free tier "should be fine" without checking this doc first. It won't be.
- **The old plan's `SHARED_LAPTOP.md` doesn't apply anymore** — all four of you are on your own Windows machines. If that changes, flag it; the guidance would need to be rebuilt (separate Windows user account, not shared credentials — ask if this comes up).
- **Demo-script implication you should know even though Frontend owns the script itself:** the original "turn off wifi mid-demo" beat doesn't work the same way now — turning off wifi kills reachability to Render *and* Vercel both, not just the model download. If that beat survives into the final script, it should demo the **local fallback stack**, not "the live site with wifi off." Flag this to Frontend & Pitch Lead directly; don't assume they've independently derived it.

---

## 10. Full Implementation Checklist

### Pre-Build (complete before event day — due "event hour 0")

- [ ] Create `image-forensics-backend` and `image-forensics-frontend` repos, push empty initial commits, share clone URLs
- [ ] `requirements.txt`, `requirements-dev.txt`, `.env.example`, `.gitignore` (P1)
- [ ] `app/main.py` skeleton — FastAPI app, CORS middleware wired to `CORS_ORIGINS`, `/health` endpoint (P1)
- [ ] `app/core/config.py` — pydantic-settings reading all env vars (P1)
- [ ] `scripts/setup_windows.ps1` — one-command environment setup for teammates (P1)
- [ ] **Lock the API contract** — `forensics/schemas.py` (`AnalysisResult`, `LayerResult`, `ErrorResponse`), the exact `POST /api/analyze` request/response shape, and the six contract questions below. Budget ~1 hour, immediately after P1, before P2–P8 begin:
  1. Coordinate space — every layer works on the same normalized image, longest side capped at `MAX_IMAGE_SIDE` (1600px default)
  2. Heatmap representation — base64-encoded colorized PNG, not a float array (settled by the HTTP transport itself)
  3. Per-layer score/reliability meaning — 0–1 float, plus a `low`/`medium`/`high` reliability enum
  4. Skipped/failed layer representation — needed for offline/degraded mode
  5. Fused result's per-layer contribution reporting
  6. The HTTP contract itself — endpoint path, method, `multipart/form-data` request shape, response content-type, error response shape (422 vs 500)
- [ ] `forensics/mock_result.py` with a realistic spread of fake results; export as `src/data/mockResult.json` for Frontend
- [ ] `forensics/layers/base.py` — the `Layer` protocol everyone else's modules implement
- [ ] `forensics/layers/metadata.py` — EXIF inspection (P7)
- [ ] `forensics/fusion.py` structure + `config/fusion_weights.yaml`, `config/thresholds.yaml` keys (P8)
- [ ] `forensics/utils/image_io.py` — load, validate, normalize size (P1, FX patches later at E8)
- [ ] Set up Render service (Standard tier), confirm `/health` and `/docs` live, share URL with Frontend
- [ ] Rehearse the local-fallback path at least once (`run_offline.ps1` + frontend dev server, zero internet)

### Event Day (Hour 0 → 8)

- [ ] **Hour 2 (E1):** `pipeline.py` wires all four layers behind `analyze()`; `app/api/routes_analyze.py` exposes it as `POST /api/analyze`; real output validates against `schemas.py`
- [ ] **Hour 3.5 (E4):** `fusion.py` + `verdicts.py` producing Authentic / Suspicious / Likely Tampered labels with per-layer contribution
- [ ] **Hour 5 (E7):** confirm offline/local-fallback mode works with the final pipeline (not just the pre-build stub)
- [ ] **Hour 6.5 (E9, stretch — cut first if behind):** `app/api/routes_report.py` + `pdf_report.py` for downloadable reports
- [ ] **Hour 7+ (E13):** code freeze — confirm `main` branch is stable, Render deploy matches it, no last-minute pushes
- [ ] Throughout: respond fast to any "does the contract support X" question from ML/Forensics/Frontend — you're the blocker if you're slow here
