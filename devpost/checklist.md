---
doc: checklist
status: approved
---

# Build Checklist

Build mode: learn (concise, practical explanations)

## Slices

- [ ] **1. Backend scaffold + JSON parsing + POST /api/analyze returns a valid AnalysisResult**
  Becomes usable: Running FastAPI backend that accepts a JSON-format log file, parses it, and returns a valid AnalysisResult JSON response with parsed events, summary counts, and placeholders for anomalies/hypotheses. The analysis pipeline is wired end-to-end for JSON.
  Why now: Gets the critical data path — ingest → parse → respond — working and testable before the other two parsers or detection rules are layered on. Reveals any schema or routing issues early.
  PRD ref: `prd.md > Log Ingestion`, `prd.md > Processing`, `prd.md > The Core Journey` (steps 2–5)
  Spec ref: `spec.md > Backend Components > app/main.py`, `spec.md > Backend Components > app/routers/analyze.py`, `spec.md > Backend Components > app/parsers/json_parser.py`, `spec.md > Backend Components > app/models/schemas.py`, `spec.md > Backend Components > app/analysis/engine.py`
  Build: Create `backend/` directory structure per spec file tree. Install dependencies (`requirements.txt`). Implement Pydantic schemas (`schemas.py`). Implement `json_parser.py`, `normalizer.py`, and a stub `AnalysisEngine` that runs JSON parsing + normalization and returns an `AnalysisResult` with empty `anomalies` and `hypotheses`. Wire `POST /api/analyze` (multipart file + JSON body). Add `GET /api/health`. Add CORS for localhost:5173. Enforce 5 MB limit server-side.
  Verify (mechanical): `cd backend && pip install -r requirements.txt && uvicorn app.main:app --port 8000` starts clean. `curl -X POST http://localhost:8000/api/analyze -F "file=@tests/fixtures/sample_json.log"` returns a JSON response that matches the `AnalysisResult` schema (no 500 errors, correct field names, `parsed_events > 0`).
  Learner check: Open http://localhost:8000/docs, use the interactive `/api/analyze` endpoint to upload a small JSON log snippet, and confirm you get a structured response back with line numbers and severity fields populated.
  Commit: `feat: backend scaffold, JSON parser, POST /api/analyze`

- [ ] **2. All three parsers + format detector + all five detection rules + all backend tests passing**
  Becomes usable: The complete deterministic analysis pipeline. Any of the three supported log formats can be uploaded and produces anomaly cards, hypothesis cards, and evidence line references. The sample incident fixture triggers the failure-chain detection.
  Why now: This is the unique kernel. Every line number in every finding must point to a real source line — the evidence integrity test makes that verifiable right now, before frontend obscures bugs.
  PRD ref: `prd.md > Features and Behavior > Log Ingestion`, `prd.md > Features and Behavior > Findings`, `prd.md > Features and Behavior > Unrecognised Lines`
  Spec ref: `spec.md > Backend Components > app/parsers/`, `spec.md > Backend Components > app/analysis/rules.py`, `spec.md > Backend Components > app/analysis/engine.py`, `spec.md > Test Strategy`
  Build: Implement `plaintext_parser.py` (Python/Java + multiline stack traces with `line_range`), `nginx_parser.py` (combined access log), `detector.py` (≥80% threshold, single-format limitation documented). Implement all five detection rules in `rules.py`: error spike (60s window), repeated error cluster (≥3 occurrences, normalised message), retry storm / repeated error (same service + identifiable operation; fallback to repeated-error label), failure chain (A→B within 120s, generates one hypothesis, deduplicated). Wire rules into `AnalysisEngine`. Author `fixtures/sample_incident.log` (DB timeout → retry → HTTP 500 failure chain, timestamped consistently). Author `tests/fixtures/` (sample_json.log, sample_plaintext.log, sample_nginx.log). Write `test_parsers.py` (field extraction, multiline grouping, line numbers, unrecognised lines), `test_rules.py` (each rule fires/doesn't fire, deduplication, missing-timestamp handling, retry fallback), `test_api.py` (schema valid; summary counts match; every `evidence_line_number` maps to a real `events` entry; multiline `line_range` lines present with correct `raw` — the evidence integrity integration test). Add `GET /api/sample`.
  Verify (mechanical): `pytest tests/ -v` — all tests green. `curl http://localhost:8000/api/sample | python -m json.tool` returns the sample fixture content. `curl -X POST http://localhost:8000/api/analyze -F "file=@app/fixtures/sample_incident.log"` returns at least one anomaly and one hypothesis with `evidence_line_numbers` populated.
  Learner check: Review `test_api.py` — specifically the evidence integrity assertions — and confirm the test is checking what you expect. Then run `pytest tests/test_api.py -v` yourself and read the output.
  Commit: `feat: plaintext+nginx parsers, format detector, all five detection rules, backend tests green`

- [ ] **3. Frontend ingestion screen → backend → processing view → raw result in state**
  Becomes usable: The React app ingests a log (upload, paste, or load sample), sends it to the backend, shows the staged processing view while the request is in-flight, and stores the AnalysisResult in context. No analysis workspace UI yet — result is confirmed via browser devtools.
  Why now: Proves the full data path browser→backend→state before building the workspace UI on top of it. Surfaces CORS, proxy, or TypeScript schema issues now rather than buried inside component work.
  PRD ref: `prd.md > Screens and Layout > Screen 1`, `prd.md > Screens and Layout > Screen 2`, `prd.md > The Core Journey` (steps 1–5)
  Spec ref: `spec.md > Stack > Frontend`, `spec.md > Components > Frontend Components > IngestionPanel.tsx`, `spec.md > Components > Frontend Components > ProcessingView.tsx`, `spec.md > Components > Shared State`, `spec.md > Look and Feel`
  Build: Install and configure Tailwind CSS v3 in the existing `frontend/` Vite project (do not create a new project). Configure Vite `/api` proxy to `http://localhost:8000`. Define TypeScript types in `src/types/analysis.ts` matching backend Pydantic schemas. Implement `src/api/client.ts` (typed `analyzeFile`, `analyzeText`, `loadSample` fetch wrappers). Implement `src/context/AnalysisContext.tsx` (`result`, `selectedFindingId`, `llmMode`). Implement `src/hooks/useAnalysis.ts` (app state machine: idle → processing → results | error). Replace boilerplate `App.tsx` with state-driven rendering. Implement `Header.tsx` (logo, "Local Analysis" badge). Implement `IngestionPanel.tsx` (file drag-and-drop, paste tab, load sample button, 5MB client-side validation, error messages). Implement `ProcessingView.tsx` (four named stages, indeterminate indicator, error + retry). Apply dark background and glass panel base styles per Look and Feel.
  Verify (mechanical): `npm run dev` (in `frontend/`) starts with no TypeScript errors. Backend running on 8000. Click "Load Sample Incident" — network tab shows `POST /api/analyze` returns 200 with a valid AnalysisResult. Browser console logs the result or React devtools shows it in AnalysisContext.
  Learner check: Open the app, drag-and-drop one of the test fixture files (e.g. `sample_json.log`), watch the processing stages cycle, then open React DevTools and confirm the `AnalysisResult` in context has `parsed_events > 0` and at least one `anomalies` entry.
  Commit: `feat: frontend ingestion screen, processing view, API client, context wired`

- [ ] **4. Full analysis workspace: timeline + findings + evidence inspector wired end-to-end**
  Becomes usable: The complete three-column analysis workspace. Selecting any anomaly, hypothesis, or timeline event populates the evidence inspector with the correct highlighted original source lines. The epistemic labels, evidence line references, next steps, and summary counts are all visible and correct. This is the demo-ready state.
  Why now: This is the unique kernel in the UI. Everything before this was setup; this is the proof.
  PRD ref: `prd.md > Screens and Layout > Screen 3`, `prd.md > Features and Behavior > Incident Timeline`, `prd.md > Features and Behavior > Findings`, `prd.md > Features and Behavior > Evidence Inspector`, `prd.md > Features and Behavior > Unrecognised Lines`, `prd.md > States and Boundaries`
  Spec ref: `spec.md > Components > Frontend Components > AnalysisWorkspace.tsx` through `UnrecognizedLines.tsx`, `spec.md > Components > Shared State`, `spec.md > Look and Feel`
  Build: Implement `AnalysisWorkspace.tsx` (three-column grid; responsive collapse — drawer on tablet, tabs on mobile). Implement `SummaryStrip.tsx` (four stat tiles from actual `summary` data). Implement `IncidentTimeline.tsx` (chronological events, severity badge, service label, severity + service filters; selecting an event sets `selectedFindingId` to `event:{line_number}`). Implement `FindingsPanel.tsx` (anomaly cards first, then hypothesis cards; no-findings message). Implement `AnomalyCard.tsx` (title, "Detected pattern" emerald pill, explanation, matched rule, evidence line refs, line count). Implement `HypothesisCard.tsx` (title, "Unconfirmed hypothesis" violet pill, plausibility, evidence refs, next steps; optional `llm_explanation` section). Implement `EvidenceInspector.tsx` (full event list with line numbers; highlights all lines in `line_range` for multiline entries; deselect control; dims non-relevant lines; always reads from unfiltered `events` array). Implement `UnrecognizedLines.tsx` (collapsible, count badge). Wire `selectedFindingId` through context so all three columns respond. "New Investigation" button resets to idle. Update `Header.tsx` to show filename and status in results state.
  Verify (mechanical): `npm run dev` + backend running. Load sample incident. Assert in browser: (a) SummaryStrip shows non-zero counts; (b) timeline has ≥ 3 events; (c) at least one anomaly card and one hypothesis card appear; (d) clicking the hypothesis card populates the evidence inspector with highlighted lines; (e) the hypothesis card shows "Unconfirmed hypothesis" label — never "Confirmed"; (f) clicking a line reference in a card scrolls/highlights that line in the inspector; (g) severity filter hides non-matching timeline rows without changing evidence inspector content.
  Learner check: Load the sample incident. Click the failure-chain hypothesis card. Read the evidence panel and the "Unconfirmed hypothesis" label. Confirm you can trace the reasoning from the hypothesis → the anomaly → the original log lines without trusting the AI's word for it. That's the thing this app is supposed to do.
  Commit: `feat: analysis workspace — timeline, findings, evidence inspector, fully wired`

- [ ] **5. Docker Compose, .env.example, README, project hygiene, demo verified**
  Becomes usable: The complete app runs with `docker compose up --build` from a fresh clone. The README explains how to start it and what to demo. The repository is clean and ready to make public.
  Why now: Last step — validates the full demo path a reviewer will follow, catches any path or config discrepancies before ship.
  PRD ref: `prd.md > Non-Goals` (no deployment required), `prd.md > States and Boundaries > Session`
  Spec ref: `spec.md > Where It Runs and How Someone Tries It`, `spec.md > Stack > Infrastructure`, `spec.md > File Structure`
  Build: Write `backend/Dockerfile` (Python 3.11-slim, install requirements, run uvicorn). Write `frontend/Dockerfile` (node:20-alpine, npm install, `npm run build`, serve with nginx or node preview; or use Vite dev in Docker for the PoC). Write `docker-compose.yml` (`backend` on 8000, `frontend` on 5173 or 4173; `LLM_API_KEY` env passthrough; correct `build:` context paths `./backend` and `./frontend`). Write `.env.example` (`LLM_API_KEY=`). Audit `frontend/vite.config.ts` proxy — dev: `http://localhost:8000`, Docker: `http://backend:8000` (use `VITE_API_URL` env var or Vite mode). Write `README.md` (what it is, local dev setup, Docker Compose setup, demo walkthrough steps per spec). Confirm `.gitignore` excludes `.env`, `devpost/learner-profile.md`, `node_modules/`, `__pycache__/`, `dist/`. Stage and review diff before first commit — confirm no secrets, no learner-profile.md.
  Verify (mechanical): `docker compose up --build` from repo root. Both services start. Open http://localhost:5173 (or 4173). Load sample incident. Confirm full analysis workspace renders and evidence inspector works. `docker compose down` cleanly. `git status` shows only intended files. `git diff --cached` before committing shows no secrets or private files.
  Learner check: Clone the repo into a fresh directory, follow the README from scratch, and confirm you can demo the complete incident workflow (load sample → timeline → hypothesis card → evidence lines) without any prior setup knowledge.
  Commit: `feat: Docker Compose, README, project hygiene, demo verified`

## Hands-on Checkpoints

- [ ] Early feedback — after Slice 3 (frontend ingests and gets a real result): try the app and confirm the data flow feels right before building the workspace UI
- [ ] Final kick-the-tires exploration and feedback completed — after Slice 5 (Docker demo works end-to-end)

## Final Review

- [ ] Final review complete — feedback resolved and learner confirms ready to ship

## Code Tour and App Map

- [ ] Learning activity complete — guided route, focused alternative, prior practice connected, or brief recap
- [ ] Optional edit and transfer reflection addressed — offered/declined/already covered/not applicable as appropriate
- [ ] `devpost/app-map.html` generated from finished code, checked, and shown, including a project-grounded practice to reuse

Activity and evidence: [what actually happened; real document/test/code references; unfinished work if interrupted]
Route and stops: [actual paths and symbols; guided stops completed, or reference-only route]
Edit outcome: [tried/kept/reverted/declined/not applicable; verification if changed]
Reflection: [offered/answered/declined/already covered — personal answer belongs only in the ignored profile]
Activity mode: [live app and editor, explicit static fallback, focused alternative, prior practice, or recap]

## Revisions
