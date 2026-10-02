# Frontend & Pitch Lead — Role Doc

Project: **Image Tampering & Deepfake Forensics Suite**
Repo you own: `image-forensics-frontend` (Vite + React + Tailwind, deployed on Vercel) — this is a separate repo from the backend; you own it in full
Architecture: FastAPI backend (Render) + React frontend (Vercel)
Devices: native Windows, Google Antigravity or VS Code

---

## 1. Identity & Role

**You are the Frontend & Pitch Lead.** You own:
- The entire `image-forensics-frontend` repo — every component, the app shell, theming, build config.
- The Vercel deployment, and the final step of stitching frontend to backend (pointing `VITE_API_BASE_URL` at Backend Lead's live Render URL).
- The pitch and demo narrative — wireframe, pitch outline, demo script, architecture diagram, slide deck.
- The final rehearsed, judge-facing demo, including the local-fallback contingency (built with Backend Lead, rehearsed by you).

You're the only one of the four with a repo entirely to yourself, which also means you're the only one with zero file-level coordination overhead inside it — the tradeoff is you're also the one who has to turn three other people's backend work into something a judge actually experiences in under four minutes.

---

## 2. Full Environment Setup From Absolute Zero

### 2.1 Install Node.js

Download the current LTS release from [nodejs.org](https://nodejs.org/). Verify:
```powershell
node --version
npm --version
```

### 2.2 Install Python (only if you want to run the backend locally too)

You don't own any Python files, but you'll want to run the backend locally while developing (pointing your dev frontend at `localhost:8000` instead of the live Render URL, especially early on). Same setup as the other docs — Python 3.11.x from python.org.

### 2.3 Create and push the frontend repo

Backend Lead creates both repos as part of their P1. Once `image-forensics-frontend` exists with its empty initial commit:

```powershell
cd D:\ImageForensics-Hackathon
git clone https://github.com/<your-github-username>/image-forensics-frontend.git
cd image-forensics-frontend
```

### 2.4 Scaffold the Vite + React project

```powershell
npm create vite@latest . -- --template react
npm install
```

(Running `npm create vite@latest .` into the already-cloned, non-empty-but-just-has-a-README folder may prompt about the directory not being empty — confirm to proceed, or scaffold into a temp folder and move files in if it refuses.)

### 2.5 Add Tailwind

```powershell
npm install tailwindcss @tailwindcss/vite
```

Add the Tailwind plugin to `vite.config.js`:
```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
})
```

And add a single import line to your main CSS file (`src/index.css` or similar):
```css
@import "tailwindcss";
```

This is Tailwind's current Vite-plugin setup — no separate `tailwind.config.js` or `postcss.config.js` needed for a basic setup. If you hit version conflicts with any other library later, pin explicit versions rather than letting npm resolve loosely.

### 2.6 `.env` setup

```
VITE_API_BASE_URL=http://127.0.0.1:8000
```
Note the `VITE_` prefix is required — Vite only exposes environment variables to client-side code if they're prefixed exactly this way. An env var without it will silently be `undefined` in your components, not an error.

### 2.7 Confirm the skeleton runs

```powershell
npm run dev
```
Should open at `http://localhost:5173`. Confirm Tailwind classes actually apply (add `className="bg-red-500"` to something temporarily and check it renders red) before building real components on top of a possibly-broken setup.

### 2.8 IDE setup

Either Google Antigravity or VS Code works well here. If VS Code: install the "ES7+ React/Redux/React-Native snippets" and "Tailwind CSS IntelliSense" extensions — the latter especially, since Tailwind's utility-class approach is much faster to write with autocomplete.

---

## 3. Git Workflow

- **Branch naming:** `frontend-<short-feature>`, e.g. `frontend-uploader`, `frontend-scorecard`, `frontend-polish`.
- **Commits:** Conventional Commits lite — `feat:`, `fix:`, `style:` (for Tailwind/visual tweaks), `docs:`, `chore:`.
- **PRs:** this is your repo alone — no one else is qualified to review React/Tailwind code in depth. Self-merge is fine. If you want a sanity second pair of eyes on the API-integration parts specifically (does this correctly consume what Backend Lead's contract promises), tag Backend Lead as a reviewer on just those PRs.
- **Merge strategy:** squash-merge into `main`.
- Keep `main` deployable at all times once Vercel is connected — every push to `main` triggers a production deploy by default on Vercel, so broken commits go live immediately unless you use preview branches for anything risky close to the event.

---

## 4. Your Specific Ownership — Exact Files and Folders

```
image-forensics-frontend/
├── README.md                              [UI]  E12   setup, run, demo steps
├── CONTRIBUTING.md                        [UI]
├── package.json                           [UI]  P1
├── vite.config.js                         [UI]  P1
├── index.html                             [UI]  P1
├── .env.example                           [UI]  P1    VITE_API_BASE_URL
├── .gitignore                             [UI]  P1
├── src/
│   ├── main.jsx                           [UI]  P1
│   ├── App.jsx                            [UI]  P1
│   ├── index.css                          [UI]  P1    Tailwind import + any global styles
│   ├── api/
│   │   └── client.js                      [UI]  E1/E2  fetch wrapper; reads VITE_API_BASE_URL; one place to swap mock → live
│   ├── data/
│   │   └── mockResult.json                [BE provides shape → you maintain]  used before Backend's live endpoint exists
│   ├── state/
│   │   └── useAnalysis.js                 [UI]  E2    upload + fetch + loading/error state, one hook the whole app consumes
│   ├── theme/
│   │   └── branding tokens                [UI]  E10
│   └── components/
│       ├── Uploader.jsx                   [UI]  E2
│       ├── ImageCompare.jsx               [UI]  E2/E3  original vs heatmap, CSS-opacity slider — see Section 7
│       ├── ScoreCard.jsx                  [UI]  E2/E4  verdict + per-layer scores
│       ├── EvidenceTabs.jsx               [UI]  E2    ELA / noise / copy-move / AI tabs
│       ├── MetadataPanel.jsx              [UI]  E2
│       ├── ExplainPanel.jsx               [UI]  E5
│       ├── Downloads.jsx                  [UI]  E9    report download buttons (stretch — client-side JSON blob + PDF fetch)
│       └── StatusBanner.jsx               [UI]  E10   loading, errors, offline/cold-start banner
├── tests/
│   └── App.test.jsx                       [UI]  basic smoke test
└── docs/
    ├── WIREFRAME.md                       [UI]  P9
    ├── PITCH_OUTLINE.md                   [UI]  P9
    ├── DEMO_SCRIPT.md                     [UI]  — see Section 7 for a required adaptation
    ├── ARCHITECTURE.md + diagram          [UI]  E12, with inputs from Backend Lead
    ├── slides/pitch_deck.pptx             [UI]  E12
    └── demo_backup/                       [ALL] E13  screen recording — keep on shared Drive, not in git
```

---

## 5. Your Dependencies — What You Need FROM Others, and When

| From | What | Due | Blocks |
|---|---|---|---|
| Backend Lead | `forensics/mock_result.py`'s output, exported as `src/data/mockResult.json` | Pre-build, right after the schema lock | Every component you build before the real API exists |
| Backend Lead | The locked API contract (field names, `/api/analyze` shape, `/docs` page live locally) | Pre-build, same window | Building components against the right shape the first time, not rebuilding later |
| Backend Lead | `app/main.py` running with `/health` returning 200 | End of P1 | Confirms there's something at `VITE_API_BASE_URL` to even point at during early dev |
| Forensics Lead | `overlay.py` producing the real heatmap PNG | Event hr 3 (E3) | `ImageCompare.jsx` needs a real heatmap to blend over the original, not just the mock's placeholder |
| ML Lead | Calibrated verdict thresholds | Event hr 5 (E6) | What `ScoreCard.jsx` displays should reflect tuned numbers by rehearsal time |
| ML Lead | `docs/KNOWN_LIMITS.md` content | By E6/E12 | You need this for the pitch deck's "Known limits" slide — it's their findings, not something you can write yourself |
| Backend Lead | The live Render URL | Pre-build, once their deploy is confirmed | You need this before you can set `VITE_API_BASE_URL` in Vercel's production env vars |

---

## 6. What Others Need FROM You, and When

| Who | What | Due | Why it blocks them |
|---|---|---|---|
| Backend Lead | Confirmation of the exact CORS origin to whitelist (your Vercel URL) | As soon as Vercel assigns it | Their `CORS_ORIGINS` env var needs your real URL, not a placeholder, before cross-origin requests will work at all |
| Whole team | The rehearsed demo script and the decision on what the "resilience" beat of the demo actually shows now | Before final rehearsal (E11) | See Section 7 — the original "turn off wifi" beat doesn't work the same way anymore, and whoever's presenting needs to know what they're actually demonstrating |
| Whole team | The architecture diagram, accurate to the real split-repo setup | E12 | This is presentation material judges see directly — it needs to reflect what was actually built, not the original single-process plan |

---

## 7. The Reasoning Behind Technical Decisions Relevant to Your Work

**Why build against mock data before the real API exists.** `mockResult.json` lets you build and visually iterate on every component — `ScoreCard`, `ImageCompare`, `EvidenceTabs`, the works — without being blocked on Backend Lead finishing `pipeline.py`. The one discipline this requires: keep `src/api/client.js` as the *only* place that knows whether it's talking to mock data or the live endpoint, so flipping the switch later is a one-line change, not a rewrite of every component that currently imports the mock JSON directly.

**Why loading and error states are now a real engineering concern, not a nicety.** In the original single-process Streamlit plan, the framework handled "please wait" and error display automatically — there was no network boundary to fail at. Now there is one: every analysis is a real HTTP request to a separately-deployed service, which means it can be slow (Render cold start, CPU inference time) or fail outright (CORS misconfiguration, a dropped connection, a 500 from the pipeline). `useAnalysis.js` needs explicit `loading` / `error` / `success` states, and `StatusBanner.jsx` needs to render all three distinctly — a UI that only shows the happy path will look broken, not just incomplete, the first time a judge's upload takes eight seconds instead of one.

**Why the heatmap is blended client-side, not server-side.** Forensics Lead's `overlay.py` now returns just the colorized heatmap PNG — no opacity, no blending. `ImageCompare.jsx` stacks two `<img>` elements (original underneath, heatmap on top) and controls the heatmap's visibility with a CSS `opacity` style bound to a slider's state. Dragging the slider updates a React state value and re-renders instantly — zero network calls, zero backend involvement after the initial fetch. This is both the correct adaptation for a client-server split and a genuinely smoother interaction than a server round-trip per slider tick would have been.

**Why per-layer scores get their own visual treatment, not just the fused verdict.** A single "87% tampered" number invites "how do you know" from a skeptical judge. `ScoreCard.jsx` showing four individual layer scores (with their reliability levels visibly distinct — a "low reliability" ELA score on a PNG input should look visually different from a "high reliability" copy-move match, not just have a smaller number) lets the system show its work, which is more persuasive than a single confident-looking digit.

**A required adaptation to the demo script.** The original plan's demo included a "turn off wifi, show the app still works" beat, meant to demonstrate resilience against bad venue internet. In the split Render+Vercel architecture, turning off wifi during the live demo kills reachability to *both* deployed services — the live site goes fully dark, which demonstrates the opposite of resilience. If this beat survives into the final script, it needs to be reframed: show the **local-fallback stack** (backend running on `localhost:8000`, frontend either `npm run dev` or a pre-built static bundle, both pointed at each other) running with wifi off, not the live Render/Vercel site with wifi off. Coordinate this directly with Backend Lead — they own making the local fallback actually work (their `offline.py` and `run_offline.ps1`); you own deciding whether this beat is worth the rehearsal time it needs to land cleanly, and scripting it accurately in `DEMO_SCRIPT.md` either way.

---

## 8. Deployment — Your Role In It

You own the Vercel deployment and the final stitching step.

### Steps

1. Push `image-forensics-frontend` to GitHub (Section 2.3 covers the clone; push your work back regularly).
2. On [vercel.com](https://vercel.com), import the GitHub repo. Vercel auto-detects a Vite project — accept the default build command (`npm run build` or `vite build`) and output directory (`dist`).
3. **Before the production build**, set the environment variable in Vercel's dashboard:
   ```
   VITE_API_BASE_URL=https://<backend-lead's-render-url>.onrender.com
   ```
   This requires Backend Lead's Render URL to already exist and be confirmed working — get it from them directly, don't guess at the URL format.
4. Deploy. Vercel gives you a `*.vercel.app` URL (and supports a custom domain if you want one for the pitch, though the default is fine for a hackathon).
5. **Send your live Vercel URL to Backend Lead immediately** — they need to add it to their Render service's `CORS_ORIGINS` env var, or every request from your deployed frontend will be silently blocked by the browser with a CORS error that looks like nothing happened.
6. Confirm the full loop works: open the live Vercel URL, upload a real test image, confirm you get back a real result from the live Render backend — not mock data, not a CORS failure, the actual round trip.
7. **Cold-start awareness:** if Backend Lead's Render service is on anything other than a tier that avoids spin-down, the first request after idle time can take 30-60+ seconds (longer, likely, given this service loads torch + transformers + a ~330MB model). Don't let this surprise you mid-rehearsal — warm the backend with a throwaway request a few minutes before any live run, including the actual judging slot.
8. Rehearse the **local fallback** at least once with Backend Lead (Section 7) — not as a theoretical option, as a thing you've actually run and timed.

---

## 9. Handoff Notes

- Nothing is built yet — pre-build hasn't started as of this plan.
- **You are the one person whose work is entirely invisible until it's connected to someone else's** — a beautifully built UI against `mockResult.json` that never gets pointed at the real API isn't a demo, it's a prototype. Don't let "component polish" expand to fill all available time before "actually wired to the live backend" happens. Wire it early, even roughly, then polish.
- **The pitch outline and demo script are not just logistics — they're where the project's honesty gets tested in front of judges.** Lean on ML Lead's `KNOWN_LIMITS.md` and real `CALIBRATION_REPORT.md` numbers rather than writing confident-sounding pitch copy that overstates what the system actually measured. This connects directly to the project's own risk register, which flags over-claiming accuracy as a real way to lose credibility.
- **The architecture diagram needs to reflect the real split-repo, two-deployment setup**, not a simplified or outdated version of the plan. If you draft it early (which is reasonable, for E12 prep), revisit it once the actual deploy is live in case anything changed from what was planned here.

---

## 10. Full Implementation Checklist

### Pre-Build (complete before event day — due "event hour 0")

- [ ] Clone `image-forensics-frontend` once Backend Lead has pushed the initial skeleton
- [ ] `npm create vite@latest`, Tailwind via `@tailwindcss/vite`, confirm `npm run dev` renders styled content
- [ ] `.env.example` with `VITE_API_BASE_URL`
- [ ] **P9:** `docs/WIREFRAME.md` (component-level, not Streamlit-column-based — plan the actual React component tree: Uploader, ImageCompare, ScoreCard, EvidenceTabs, MetadataPanel, ExplainPanel, Downloads, StatusBanner) and `docs/PITCH_OUTLINE.md`
- [ ] Get `mockResult.json` from Backend Lead; set up `src/api/client.js` with a clean mock/live switch
- [ ] Build early component skeletons against mock data, even roughly — don't wait for full polish before confirming the shape works

### Event Day (Hour 0 → 8)

- [ ] **Hour 3 (E2):** `Uploader.jsx`, `ScoreCard.jsx`, `MetadataPanel.jsx`, `useAnalysis.js` wired to the real (or still-mock, if E1 isn't done yet) API
- [ ] **Hour 3 (E3):** `ImageCompare.jsx` — original vs. heatmap, CSS-opacity slider, once Forensics Lead's `overlay.py` output is available
- [ ] **Hour 4.5 (E5):** `ExplainPanel.jsx` wired to real explanation text
- [ ] **Hour 6.5 (E9, stretch):** `Downloads.jsx` — client-side JSON blob download + PDF fetch button, only if Backend Lead's report endpoints exist
- [ ] **Hour 6.5 (E10):** `StatusBanner.jsx`, branding/theme pass, loading and error states for every async path
- [ ] **Vercel deploy + CORS stitching** — as early as the backend has a stable live URL, don't leave this to the final hour
- [ ] **Hour 7 (E12):** finalize `README.md`, `docs/ARCHITECTURE.md` + diagram, `docs/slides/pitch_deck.pptx`
- [ ] **Before final rehearsal (E11):** resolve and script the local-fallback demo beat with Backend Lead (Section 7) — don't leave this undecided into the last hour
- [ ] **Hour 7+ (E13):** code freeze, confirm the live Vercel+Render loop one final time, record the backup screen capture (whole team, kept off git)
