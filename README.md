# QuantumSafe AI — SIH26165 Prototype (Phase 1–4)

AI/NLP safety intelligence platform for Oil India Limited: detects Serious
Injury & Fatality (SIF) precursors in free-text unsafe-act / unsafe-condition
/ near-miss reports, maps them to IOGP Life-Saving Rules, identifies failed
safety barriers, and surfaces recurring cross-report SIF patterns.

**Status: Phases 1–4 of the priority order are implemented and tested.**
(Phase 5 advanced ML, Phase 6 alerts, Phase 7 polish/deployment are next.)

## What's actually built right now

| Phase | What it does | Status |
|---|---|---|
| 1 — Analyzer | Text in → SIF classification, confidence, risk score, hazard, Life-Saving Rule, failed barriers, explanation, recommendation | ✅ Working |
| 2 — Persistence + Reports | SQLite storage, reports list with filters, CSV bulk upload | ✅ Working |
| 3 — Dashboard | KPI cards + top hazards/rules/locations, all DB-driven (no hardcoded numbers) | ✅ Working |
| 4 — Pattern Detection | Groups reports by hazard + location + failed barrier, flags recurring high-SIF-ratio patterns | ✅ Working |
| 5 — Advanced ML | Transformer-based classification | ⬜ Not started |
| 6 — Alerts | Auto-generated red/amber alerts off pattern trends | ⬜ Not started |
| 7 — Polish/Deploy | Auth, cloud deployment | ⬜ Not started |

I validated Phases 1–4 end-to-end in a sandboxed environment without
network access, so I could run the actual classifier/extraction/pattern
logic but **could not install or boot FastAPI itself there**. That means:
the API route code in `app/main.py` has not literally been hit over HTTP
by me — but every function it calls (`analyze_report`, the SQLite schema,
`detect_patterns`) has been run directly against all 800 synthetic reports
with correct results (see `tests/smoke_test_pipeline.py` output below).
**Run the steps below on your machine to confirm the HTTP layer itself —
that's the one thing I couldn't verify for you.**

## Important honesty note on the classifier

The baseline classifier hit 100% accuracy/precision/recall on the held-out
synthetic test set. **That is not a real result** — it's because the
synthetic dataset only has ~25 underlying sentence templates, so train and
test sets share near-identical phrasing. It proves the training pipeline
works end-to-end, not that the model generalizes. Once you get real (or
more diverse synthetic) OIL report text, re-run training and expect those
numbers to drop — that's normal and expected.

## Folder structure

```
quantumsafe-ai/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app, all API routes
│   │   ├── data/
│   │   │   ├── taxonomy.py            # configurable hazard/LSR/barrier lexicon
│   │   │   ├── generate_synthetic_data.py
│   │   │   └── synthetic_reports.csv  # 800 generated rows
│   │   ├── models/
│   │   │   ├── train_classifier.py
│   │   │   └── sif_classifier.joblib  # trained model (regenerate anytime)
│   │   └── services/
│   │       ├── extraction.py          # Module 3: rule-based entity/hazard extraction
│   │       ├── classifier.py          # Module 4: ML classify + rule-based fallback
│   │       ├── risk_engine.py         # Module 5: 0-100 risk scoring
│   │       ├── explain.py             # Module 18/19: explanation + recommendation
│   │       ├── pattern_detection.py   # Module 8: cross-report pattern detection
│   │       └── pipeline.py            # orchestrates all of the above
│   ├── tests/
│   │   └── smoke_test_pipeline.py     # end-to-end validation script
│   └── requirements.txt
├── frontend/
│   └── index.html                     # single-page UI: Dashboard/Analyze/Reports/Patterns
└── README.md
```

**Note on frontend stack:** the spec's preferred stack is React/Next.js.
I built this as a single dependency-free HTML/JS file instead so it runs
with zero build step and zero npm install — critical when you're moving
fast in a hackathon and want every team member able to open it and see it
work immediately. It talks to the same REST API a React app would, so
porting it to Next.js later (Phase 7 polish) is a matter of moving this
logic into components, not redesigning the API.

## How to run it

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Regenerate the synthetic dataset (already included, but this is how)
python3 app/data/generate_synthetic_data.py

# Train the baseline classifier (already included as .joblib, but this is how)
python3 -m app.models.train_classifier

# Start the API
uvicorn app.main:app --reload --port 8000
```

Visit `http://localhost:8000/docs` for interactive Swagger docs — good for
testing endpoints directly before wiring up frontend work.

### 2. Frontend

Just open `frontend/index.html` directly in a browser (double-click it, or
`open frontend/index.html` on Mac). It calls `http://localhost:8000` — make
sure the backend is running first. The sidebar shows a live connection
indicator (green dot = API reachable).

### 3. Run the smoke test (validates the whole pipeline without needing the API up)

```bash
cd backend
python3 tests/smoke_test_pipeline.py
```

Expected output (this is what I got in testing):
```
Seeding 800 synthetic reports through the real analyze_report() pipeline...
Seeded. Label mismatches vs synthetic ground truth: 0/800
Dashboard summary — Total: 800 | SIF-potential: 362 | Critical: 240
Emerging patterns detected: 137
  Confined Space @ Maintenance Yard | barrier: Atmospheric Testing | 10 reports, 10 SIF (100%), risk=CRITICAL
  ...
```

### 4. Try the exact SIH demo scenario

1. Open the frontend, go to **Analyze Report**.
2. Click the "Confined space example" chip (or paste): *"During
   maintenance, a worker entered a confined space without atmospheric
   testing. No standby person was present."*
3. Click **Analyze Report** → should return SIF=YES, CRITICAL risk,
   Confined Space hazard, both barriers (Atmospheric Testing, Standby
   Person) flagged, explanation, and a recommendation.
4. Click **Save Report**.
5. Go to **Reports** to see it listed.
6. Go to **Patterns** — needs 3+ similar saved reports to show a pattern
   (the smoke test above already proves this works at volume against the
   full synthetic set).

## Splitting remaining work across your 6 people

- **2 people**: Phase 5 — swap in a transformer classifier
  (DistilBERT/RoBERTa) behind the same `classify()` function signature in
  `app/services/classifier.py`, so nothing else needs to change.
- **1 person**: Phase 6 — alerts. You already have `detect_patterns()`
  output; an alert is just a threshold check on `sif_ratio` and
  `report_count` over a rolling time window, using the `date` field
  already in the schema.
- **2 people**: Port `frontend/index.html` into React/Next.js components
  for Phase 7, one per page (Dashboard, Analyze, Reports, Patterns) — the
  API contract won't change, so this is pure UI work.
- **1 person**: Real dataset work — if OIL provides sample data before the
  demo, adapt `generate_synthetic_data.py`'s schema mapping and re-run
  `train_classifier.py`.

## What to tell judges honestly

- Classifier metrics on synthetic data are **not** representative of
  real-world performance — say so proactively, it reads as rigor, not
  weakness.
- Risk score thresholds (0-30/31-60/61-80/81-100) are your prototype's own
  framework, not an official OIL methodology.
- This is decision support for HSE professionals, not a replacement for
  their judgment — the UI's recommendation text says this explicitly.
