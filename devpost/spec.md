---
doc: spec
status: approved
---

# TraceGuard AI — Technical Spec

## How This Works, In Plain Language

TraceGuard AI is two programs that talk to each other: a **backend** that does all the analysis, and a **frontend** that shows the results and lets you interact with them.

When you upload a log file, it goes from your browser to the backend. The backend reads it line by line, figures out which log format it is (JSON, Python/Java plaintext, or Nginx/Apache), and parses each line into a structured event with a timestamp, severity, service name, and message. Lines it can't parse are flagged and preserved.

Once parsed, the backend runs five deterministic detection rules over the sorted event list — looking for error spikes, repeated errors, retry storms, and failure chains. Each rule that fires produces a finding with the exact line numbers that triggered it. Failure-chain findings also generate a hypothesis card, explicitly labelled unconfirmed, with recommended investigation steps.

The backend returns one JSON response containing everything: the parsed events, the summary counts, the anomaly findings, the hypotheses, and the unrecognised lines. Nothing is stored. Each request is independent.

The frontend receives that response and renders it as a three-column workspace: a chronological timeline on the left, findings in the centre, and a persistent evidence inspector on the right. Selecting any finding or timeline event tells the inspector which source lines to highlight. Filters on the timeline update which events are visible but never change the underlying evidence references.

If an LLM API key is present and the AI-Enhanced mode is active, the backend sends each hypothesis's deterministic findings and evidence lines to the LLM, validates any returned line references against the original source, and adds a clearly labelled explanation section to the hypothesis card. The full workflow operates without this.

This shape — stateless backend, single round-trip analysis, no database — is the right fit for a hackathon PoC: nothing to provision, nothing to seed, reproducible results from the same input every time.

---

## The Core Journey Through the System

*Implements `prd.md > The Core Journey`.*

1. **User opens the app** → Browser loads the React frontend served by Vite (dev) or Nginx (Docker). The backend is not called yet.
2. **User uploads a file or pastes text** → Frontend validates size (≤ 5 MB client-side), then sends `POST /api/analyze` as `multipart/form-data` (file upload) or `application/json` (paste). Load Sample triggers `GET /api/sample` which returns the bundled fixture, then the frontend auto-submits it as `POST /api/analyze`.
3. **Processing view renders** → Frontend transitions to the staged processing screen. Since the backend processes synchronously and returns when complete, the frontend cycles through the stage labels with an indeterminate indicator until the response arrives.
4. **Backend receives the request** → `analyze.py` router hands the raw bytes and filename to the `AnalysisEngine`. The engine calls `FormatDetector` to identify the format, then the appropriate parser, then the `Normalizer`, then the `RulesEngine`. It assembles and returns an `AnalysisResult`.
5. **Response arrives** → Frontend receives the `AnalysisResult` JSON. State is set; the app transitions to the Analysis Workspace.
6. **User interacts** → Selecting a card or timeline event updates `selectedFindingId` in shared state. The Evidence Inspector watches this value and highlights the corresponding source lines from the `events` array (which always holds the full, unfiltered original events).
7. **Filters applied** → Severity and service filters update a local derived list of visible timeline events. The `events` array and all evidence references are untouched.
8. **LLM enhancement (optional)** → If the mode selector is set to AI-Enhanced and `LLM_API_KEY` is set, the backend appended `llm_explanation` fields to hypothesis objects before returning. The frontend renders these in a clearly labelled section. If the LLM call failed, the field is absent; the frontend falls back to deterministic content silently.

---

## Stack

### Frontend

| Piece | Choice | Rationale |
|---|---|---|
| Framework | React 18 + TypeScript | Already scaffolded with Vite; learner's chosen stack |
| Build tool | Vite 6 | Already present; fast HMR, built-in proxy for `/api` |
| Styling | Tailwind CSS v3 | Learner-specified; utility-first fits a dense dark UI |
| State | React `useState` + `useContext` | Single-session, no persistence; no external state library needed |
| HTTP client | Native `fetch` (typed wrapper) | No axios needed; keeps dependencies minimal |

**Tailwind installation** (not yet present in the scaffold):
```bash
cd frontend
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```
Doc: https://tailwindcss.com/docs/installation

Vite config adds a proxy so `/api/*` in the browser forwards to `http://localhost:8000`:
```ts
// vite.config.ts
server: { proxy: { '/api': 'http://localhost:8000' } }
```

### Backend

| Piece | Choice | Version | Doc |
|---|---|---|---|
| Language | Python | 3.11+ | https://docs.python.org/3.11/ |
| Framework | FastAPI | 0.111+ | https://fastapi.tiangolo.com |
| ASGI server | Uvicorn | 0.29+ | https://www.uvicorn.org |
| Validation | Pydantic v2 | (bundled with FastAPI) | https://docs.pydantic.dev/latest/ |
| LLM client (optional) | `openai` library | 1.x | https://platform.openai.com/docs |

Python dependencies (`requirements.txt`):
```
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
python-multipart>=0.0.9
pydantic>=2.0.0
python-dateutil>=2.8.2
openai>=1.0.0   # optional; only imported if LLM_API_KEY is set
pytest>=8.0.0
httpx>=0.27.0   # for pytest with FastAPI TestClient
```

### Infrastructure

| Piece | Choice |
|---|---|
| Containerisation | Docker + Docker Compose |
| Dev workflow | `docker compose up` starts both services |
| Environment | `.env` file at repo root; never committed |

---

## Where It Runs and How Someone Tries It

**Local development (no Docker):**
```bash
# Terminal 1 — backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

**Docker Compose (recommended for demo):**
```bash
cp .env.example .env          # add LLM_API_KEY if desired
docker compose up --build
# Open http://localhost:5173
```

**Demo recording checklist:**
1. Open http://localhost:5173 — show the empty ingestion workspace.
2. Click "Load Sample Incident" — show the processing stages.
3. Walk the timeline, click the failure-chain anomaly card, show evidence lines highlighted.
4. Click the hypothesis card, show the "Unconfirmed hypothesis" label and next steps.
5. Click a line reference — show the evidence inspector navigate to that line.
6. (Optional) Enable AI-Enhanced mode if key is present — show the labelled LLM explanation.

Submission requires the demo video and a public GitHub repository. Deployment to a live URL is optional and not required.

---

## Look and Feel

*Carries forward `prd.md > Look and Feel` and `scope.md > Inspiration & Identity`.*

**Palette (Tailwind custom tokens):**
- Background: `#0d0f14` (near-black, slightly blue-tinted)
- Surface (glass panels): `rgba(255,255,255,0.04)` with `backdrop-filter: blur(12px)` and `border: 1px solid rgba(255,255,255,0.08)`
- Accent — cyan: `#22d3ee` (`cyan-400`) for interactive elements, selected states, evidence highlights
- Accent — violet: `#a78bfa` (`violet-400`) for hypothesis labels and related indicators
- Anomaly label: `#34d399` (`emerald-400`) pill — "Detected pattern"
- Hypothesis label: `#a78bfa` (`violet-400`) pill — "Unconfirmed hypothesis"
- Error severity: `#f87171` (`red-400`)
- Warn severity: `#fbbf24` (`amber-400`)
- Info severity: `#60a5fa` (`blue-400`)
- Body text: `#e2e8f0` (`slate-200`); muted: `#64748b` (`slate-500`)

**Typography:**
- UI text: Inter (Google Fonts) — clean, high legibility at small sizes
- Log content, line numbers, source evidence: `font-mono` (JetBrains Mono or system monospace)

**Density and tone:** Dense information layout; tight line spacing for the timeline and evidence inspector. Clinical, no marketing language. Glassmorphism on panel surfaces only — not on every element.

**Tailwind config additions:**
```js
// tailwind.config.js
fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'], mono: ['JetBrains Mono', 'monospace'] }
colors: { /* extend with bg-surface, border-glass, accent-cyan, accent-violet */ }
```

---

## Components

### Frontend Components

#### `App.tsx` — Root and routing
Single-page app; no router needed. Manages top-level app state: `AppState` = `idle | processing | results | error`. Renders the correct screen based on state.

#### `Header.tsx`
*Implements `prd.md > Screens and Layout > Screen 1 (top bar)` and `Screen 3 (top header)`.*
Logo, wordmark, "Local Analysis" badge. In results state: incident filename, analysis status, "New Investigation" button (resets to idle).

#### `IngestionPanel.tsx`
*Implements `prd.md > Log Ingestion`, `prd.md > Screens and Layout > Screen 1`.*
- File drop zone: `onDragOver` / `onDrop` handlers; also a `<input type="file">` trigger.
- Paste tab: `<textarea>` + Analyse button.
- Load Sample button: calls `GET /api/sample`, receives text, auto-submits to `POST /api/analyze`.
- Client-side size validation before any network call (5 MB = 5 × 1024 × 1024 bytes for files; character count for paste).
- On submit: sets app state to `processing`, calls `useAnalysis.submit()`.

#### `ProcessingView.tsx`
*Implements `prd.md > Screens and Layout > Screen 2`.*
Four stages displayed in order. Cycles through them on an interval while the fetch is in-flight. On response: transitions to `results`. On error: transitions to `error` state with message and retry option.

#### `AnalysisWorkspace.tsx`
*Implements `prd.md > Screens and Layout > Screen 3`.*
Three-column grid container. Receives `AnalysisResult` and `selectedFindingId` from context. Passes slices to children. Handles responsive collapse (Tailwind breakpoints).

#### `SummaryStrip.tsx`
*Implements `prd.md > Summary Strip`.*
Four stat tiles: parsed events, errors detected, anomalies flagged, unrecognised lines. Values from `AnalysisResult.summary`; never fabricated.

#### `IncidentTimeline.tsx`
*Implements `prd.md > Left column — Incident Timeline`.*
- Renders filtered `events` array sorted by `timestamp` (falls back to `line_number` for events without valid timestamps).
- Severity multi-select filter and service multi-select filter; derived locally from visible events.
- Selected event: highlighted row; sets `selectedFindingId` to `event:{line_number}` in context.
- Events associated with a finding get a soft indicator (small coloured dot).

#### `FindingsPanel.tsx`
*Implements `prd.md > Centre column — Findings`.*
Renders anomaly cards first, then hypothesis cards. No-findings message when both lists are empty.

#### `AnomalyCard.tsx`
*Implements `prd.md > Findings > Anomaly card anatomy`.*
Title, "Detected pattern" pill (emerald), explanation, matched rule name + criteria, evidence line references (clickable), supporting line count.

#### `HypothesisCard.tsx`
*Implements `prd.md > Findings > Hypothesis card anatomy`.*
Title, "Unconfirmed hypothesis" pill (violet), plausibility text, evidence line references, recommended next steps list. Optional `llm_explanation` section with "AI-generated explanation" label — only rendered when the field is present in the response.

#### `EvidenceInspector.tsx`
*Implements `prd.md > Right column — Evidence Inspector`.*
- Empty state when `selectedFindingId` is null.
- Computes relevant line numbers from the selected finding or event. For multiline entries (e.g., stack traces), the relevant set is the full `line_range` — every line from first to last — not just the event's starting `line_number`. The inspector must highlight all lines in the range.
- Renders the full `events` array as a virtual-scrollable (or windowed) log view with line numbers. Highlights relevant lines (cyan left border + subtle background); dims others.
- Deselect (×) button clears `selectedFindingId`.
- Always uses the original unfiltered `events` array — timeline filters do not affect this.
- **Clarification (approved):** Evidence references from anomalies and hypotheses are sets of original source line numbers. The inspector resolves each line number to its original raw text. For multiline stack traces, all lines in `line_range` are shown and highlighted together.

#### `UnrecognizedLines.tsx`
*Implements `prd.md > Unrecognised Lines`.*
Collapsible section below the Findings column. Shows count badge when collapsed. Expanded: list of `{line_number, raw, reason}` entries.

### Shared State

```ts
// src/context/AnalysisContext.tsx
interface AnalysisContextValue {
  result: AnalysisResult | null;
  selectedFindingId: string | null;   // "anomaly:{id}" | "hypothesis:{id}" | "event:{line_number}" | null
  setSelectedFindingId: (id: string | null) => void;
  llmMode: 'deterministic' | 'ai_enhanced';
  setLlmMode: (mode: 'deterministic' | 'ai_enhanced') => void;
}
```

### Backend Components

#### `app/main.py`
FastAPI app creation, CORS (allow `localhost:5173`), router registration. Startup: verify `fixtures/sample_incident.log` exists.

#### `app/routers/analyze.py`
*Implements `prd.md > Log Ingestion`, `prd.md > Processing`.*
- `POST /api/analyze`: accepts `multipart/form-data` with `file` field, OR `application/json` with `{"content": str, "filename": str}`. Enforces 5 MB limit (FastAPI `File` size validation + body size middleware). Returns `AnalysisResult`.
- `GET /api/sample`: reads `fixtures/sample_incident.log`, returns its content as `{"content": str, "filename": "sample_incident.log"}`.
- `GET /api/health`: returns `{"status": "ok"}`.

#### `app/parsers/detector.py`
Tries each parser in order. Returns the first format that successfully parses ≥ 80% of non-empty lines in a sample of the first 50 lines. Formats tried: JSON, Nginx/Apache, Python/Java plaintext. If none exceeds the threshold, returns `unknown`; the engine marks all lines as unrecognised.

**Known limitation (documented and tested):** The detector selects a single dominant format for the whole file. Mixed-format files (e.g., a JSON section followed by an Nginx section) will have lines from the non-dominant format flagged as unrecognised. This is by design for the PoC. The limitation is surfaced in the Unrecognised Lines section and never causes silent data loss — all lines are either parsed or preserved with their original content and line number. A `test_detector.py` test must verify that lines from the non-dominant format appear in `unrecognised_lines` with their original content intact.

#### `app/parsers/json_parser.py`
Expects one JSON object per line. Extracts: `timestamp` (ISO 8601 preferred; also accepts epoch float/int), `level`/`severity`/`log_level` (case-insensitive), `message`/`msg`, `service`/`logger`/`name`, `error`/`exception`/`err`. Lines that are valid JSON but missing all timestamp fields are parsed with `timestamp_parsed: false`. Lines that are not valid JSON are flagged as unrecognised.

#### `app/parsers/plaintext_parser.py`
Handles Python/Java-style logs. Primary line regex (Python example):
```
^(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[.,\d]*(?:Z|[+-]\d{2}:?\d{2})?)\s+(?P<level>DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL|FATAL|SEVERE)\s+(?P<message>.+)$
```
Stack trace continuation: lines starting with whitespace or `at `, `Caused by:`, `...` are appended to the preceding event's `stack_trace` field. The primary event's `line_number` is its first line; `line_range` = `[first, last]` for multiline entries. Each line in the range retains its original line number in the evidence inspector.

#### `app/parsers/nginx_parser.py`
NCSA Combined Log Format:
```
^(?P<remote_host>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] "(?P<request>[^"]*)" (?P<status>\d{3}) (?P<bytes>\S+)(?: "(?P<referer>[^"]*)" "(?P<agent>[^"]*)")?$
```
`level` derived from HTTP status: 5xx → ERROR, 4xx → WARN, 3xx/2xx/1xx → INFO.

#### `app/analysis/normalizer.py`
- Timestamp normalisation: try `python-dateutil` parse → ISO 8601 UTC. On failure: mark `timestamp_parsed: false`. Events without valid timestamps are sorted to the end (preserving their file order among themselves).
- Severity normalisation: `FATAL`/`CRITICAL`/`SEVERE` → `ERROR`; `WARNING` → `WARN`; rest pass through.

#### `app/analysis/rules.py` — Five detection rules

**Rule 1 — Error Spike** (`error_spike`)
Sort events with `timestamp_parsed: true` by timestamp. Slide a 60-second window. If any window contains ≥ 3 ERROR events: produce one anomaly with all events in the tightest matching window. Events without valid timestamps are excluded from this rule; their exclusion is noted in the finding explanation.

**Rule 2 — Repeated Error Cluster** (`repeated_error_cluster`)
Normalise each ERROR event's message: lowercase, strip UUIDs (`[0-9a-f-]{36}`), strip numbers (`\d+`), strip common noise words. Group by normalised message. If count ≥ 3: produce one anomaly. Evidence lines: all occurrences. Original messages preserved in the evidence display.

**Rule 3 — Retry Storm / Repeated Error** (`retry_storm`)
For each ERROR event, look for ≥ 2 subsequent events within 30 seconds that share the same `service` field AND a normalised message indicating the same operation (e.g., same endpoint, same exception class, same query identifier). Both conditions — same service AND identifiable operation — must be present to label the finding a retry storm.

If repeated messages are found but the operation cannot be established (e.g., no `service` field, or messages differ beyond normalisation), produce a `repeated_error_cluster` anomaly instead of a retry storm. Never label a finding as a retry solely from repeated messages when the operation context is absent. Document the distinction in the finding explanation.

**Rule 4 — Failure Chain** (`failure_chain`)
Sort events with valid timestamps. For each ERROR event A, look for a distinct ERROR event B (different normalised message pattern) within 120 seconds. "Distinct" means the normalised messages differ by more than stopword substitution. A matching A→B pair produces one anomaly (detected pattern) and one hypothesis (unconfirmed). Deduplication: if multiple A events match the same B type, produce one anomaly with all contributing A events. Do not produce duplicate hypothesis cards for the same chain type.

**Rule 5 — Unrecognised Lines** (`unrecognized_line`)
Collected by parsers during parsing, not a post-hoc rule. Each parser reports its unrecognised lines to the engine. The engine aggregates them.

#### `app/analysis/engine.py`
`AnalysisEngine.analyze(content: str, filename: str) -> AnalysisResult`:
1. Run `FormatDetector`.
2. Parse with selected parser (line by line; collect unrecognised lines).
3. Run `Normalizer` over parsed events.
4. Run all four detection rules over normalised events.
5. Optionally call `LLMProvider.enhance_hypotheses()` if key is present and mode is `ai_enhanced`.
6. Assemble and return `AnalysisResult`.

#### `app/models/schemas.py` — Pydantic models

```python
class ParsedEvent(BaseModel):
    line_number: int
    line_range: list[int] | None = None   # for multiline entries
    timestamp: str | None                  # ISO 8601 UTC, or None
    timestamp_parsed: bool
    severity: Literal['ERROR', 'WARN', 'INFO', 'DEBUG', 'UNKNOWN']
    service: str | None
    message: str
    raw: str                               # exact original line(s)
    format: Literal['json_application', 'plaintext', 'nginx_apache', 'unknown']

class MatchedRule(BaseModel):
    name: str
    description: str
    threshold: str

class Anomaly(BaseModel):
    id: str
    rule: str
    title: str
    epistemic_label: Literal['detected_pattern']
    explanation: str
    matched_rule: MatchedRule
    evidence_line_numbers: list[int]
    supporting_line_count: int

class Hypothesis(BaseModel):
    id: str
    title: str
    epistemic_label: Literal['unconfirmed_hypothesis']
    plausibility: str
    supporting_anomaly_ids: list[str]
    evidence_line_numbers: list[int]
    next_steps: list[str]
    llm_explanation: str | None = None    # present only when LLM mode active and succeeded

class UnrecognisedLine(BaseModel):
    line_number: int
    raw: str
    reason: str

class AnalysisSummary(BaseModel):
    total_lines: int
    parsed_events: int
    error_count: int
    warn_count: int
    anomalies_flagged: int
    unrecognised_lines: int
    detected_format: str

class AnalysisResult(BaseModel):
    filename: str
    summary: AnalysisSummary
    events: list[ParsedEvent]
    anomalies: list[Anomaly]
    hypotheses: list[Hypothesis]
    unrecognised_lines: list[UnrecognisedLine]
```

#### `app/llm/interface.py` — Optional LLM layer

```python
from typing import Protocol

class LLMProvider(Protocol):
    def enhance_hypothesis(
        self,
        hypothesis: Hypothesis,
        evidence_lines: list[str]       # original raw log lines
    ) -> str:                           # LLM-generated explanation text
        ...
```

`app/llm/openai_provider.py` — implements `LLMProvider` using `openai` library. Prompt: sends hypothesis title, plausibility, and evidence lines (not raw full log). Validates that any line references in the returned text correspond to actual evidence line numbers before the response is used. On timeout, `RateLimitError`, or invalid response: raises `LLMUnavailableError`; the engine catches it and returns the result without `llm_explanation`.

LLM key loaded from `LLM_API_KEY` environment variable only. Never passed through the frontend. The frontend sends a `llm_mode` query parameter (`deterministic` | `ai_enhanced`) to `POST /api/analyze`; the backend decides whether to call the LLM.

---

## Data Model

No database. All data is session-scoped and lives in React state on the frontend, and in Python memory on the backend for the duration of the request.

| Data | Where it lives | How it gets there | What happens on close |
|---|---|---|---|
| Raw log content | Backend memory during request | HTTP upload/paste | Discarded after response |
| `AnalysisResult` | React state (`useState`) | HTTP response | Lost on page refresh |
| `selectedFindingId` | React context | User interaction | Lost on page refresh |
| Filter state | Local component state | User interaction | Lost on page refresh |
| `llmMode` | React context | User interaction | Lost on page refresh |
| LLM API key | Backend env var | `.env` / Docker env | Never in frontend |

---

## File Structure

```
traceguard-ai/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI app + CORS + router mount
│   │   ├── routers/
│   │   │   └── analyze.py              # POST /api/analyze, GET /api/sample, GET /api/health
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # ParsedEvent builder helpers
│   │   │   ├── detector.py             # Format auto-detection
│   │   │   ├── json_parser.py          # JSON application logs
│   │   │   ├── plaintext_parser.py     # Python/Java + stack traces
│   │   │   └── nginx_parser.py         # Nginx/Apache combined
│   │   ├── analysis/
│   │   │   ├── __init__.py
│   │   │   ├── normalizer.py           # Timestamp + severity normalisation
│   │   │   ├── rules.py                # Five detection rules
│   │   │   └── engine.py              # Orchestration + AnalysisEngine class
│   │   ├── models/
│   │   │   └── schemas.py              # All Pydantic models
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── interface.py            # LLMProvider Protocol
│   │   │   └── openai_provider.py      # Optional OpenAI implementation
│   │   └── fixtures/
│   │       └── sample_incident.log     # Bundled sample: DB timeout→retry→HTTP 500
│   ├── tests/
│   │   ├── conftest.py                 # Shared fixtures + TestClient
│   │   ├── fixtures/
│   │   │   ├── sample_json.log         # JSON format fixture
│   │   │   ├── sample_plaintext.log    # Python/Java plaintext fixture
│   │   │   └── sample_nginx.log        # Nginx/Apache fixture
│   │   ├── test_parsers.py             # Unit: each parser against its fixture
│   │   ├── test_rules.py               # Unit: each of 5 rules against constructed events
│   │   └── test_api.py                 # Integration: POST /api/analyze roundtrip
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.tsx
│   │   │   ├── IngestionPanel.tsx
│   │   │   ├── ProcessingView.tsx
│   │   │   ├── AnalysisWorkspace.tsx
│   │   │   ├── SummaryStrip.tsx
│   │   │   ├── IncidentTimeline.tsx
│   │   │   ├── FindingsPanel.tsx
│   │   │   ├── AnomalyCard.tsx
│   │   │   ├── HypothesisCard.tsx
│   │   │   ├── EvidenceInspector.tsx
│   │   │   └── UnrecognizedLines.tsx
│   │   ├── context/
│   │   │   └── AnalysisContext.tsx     # selectedFindingId, llmMode, result
│   │   ├── hooks/
│   │   │   └── useAnalysis.ts          # submit(), state machine, API calls
│   │   ├── api/
│   │   │   └── client.ts               # Typed fetch wrappers for /api endpoints
│   │   ├── types/
│   │   │   └── analysis.ts             # TypeScript interfaces matching Pydantic schemas
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css                   # Tailwind directives + custom CSS tokens
│   ├── public/
│   │   └── favicon.svg
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── vite.config.ts                  # /api proxy to localhost:8000
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   ├── tsconfig.node.json
│   ├── package.json
│   └── Dockerfile
├── devpost/
│   ├── learner-profile.md
│   ├── scope.md
│   ├── prd.md
│   └── spec.md
├── .env.example                        # LLM_API_KEY= (empty, uncommitted)
├── .gitignore                          # .env, node_modules, __pycache__, devpost/learner-profile.md
├── docker-compose.yml
└── README.md
```

---

## External Services and Dependencies

### FastAPI / Uvicorn
- Docs: https://fastapi.tiangolo.com / https://www.uvicorn.org
- No account or key required.

### python-dateutil
- Docs: https://dateutil.readthedocs.io
- Used for flexible timestamp parsing. No account required.

### OpenAI API (optional)
- Docs: https://platform.openai.com/docs
- Key: `LLM_API_KEY` env var (backend only).
- Recommended model: `gpt-4o-mini` — fast, low cost (~$0.15/1M input tokens as of mid-2024; **verify current pricing at build time**).
- Rate limits: check current tier limits; the PoC sends one request per analysis, so limits are unlikely to be hit in demo conditions.
- **Verify at build time:** confirm the `openai` Python library version (1.x API) and that the chosen model is available on the configured account.

### Google Fonts (Inter, JetBrains Mono)
- Loaded via `<link>` in `index.html`; fallback to system fonts if offline. No account required.

---

## Important Failure Modes

- **File exceeds 5 MB** → Backend returns `413 Request Entity Too Large` with `{"detail": "Log input exceeds 5 MB limit."}`. Frontend shows specific error message and Retry / Start Over options.
- **No recognisable format** → Backend returns `422 Unprocessable Entity` with `{"detail": "Could not detect log format. Ensure logs match JSON application, Python/Java plaintext, or Nginx/Apache combined access log format."}`. Frontend shows error with Retry option.
- **Backend unreachable** → `fetch` throws a network error. Frontend catches it and shows: "Unable to reach the analysis service. Check that the backend is running on port 8000."
- **LLM timeout or error** → Backend catches `openai.APIError` / `openai.RateLimitError`, logs the error server-side, returns the `AnalysisResult` without `llm_explanation` fields. Frontend shows a non-blocking banner: "AI explanations unavailable — showing deterministic results."
- **All lines unrecognised** → Backend returns a valid `AnalysisResult` with `parsed_events: 0`, `anomalies: []`, `hypotheses: []`, and all lines in `unrecognised_lines`. Frontend renders the no-findings state and the Unrecognised Lines section; Summary Strip shows `0` parsed events.

---

## What Was Simplified and Why

- **Synchronous backend processing** instead of streaming progress — the backend returns a completed result in one response; the frontend cycles through honest stage labels with an indeterminate indicator. Real-time progress would require WebSockets or SSE, adding meaningful complexity for no additional demo value.
- **React context instead of a state management library** — the app has one user, one session, one analysis result. Zustand or Redux would be overcomplicated; `useState` + `useContext` is sufficient.
- **No database** — results live in React state. Persistence would require a database, migrations, and cleanup; none of this proves the core idea.
- **Evidence inspector renders the full event list** (not a virtualised subset) for the PoC. If log files are very large, the inspector may render slowly. For the 5 MB limit and typical log density this is acceptable; virtualisation can be added later.
- **Single LLM provider** — if LLM integration is included, implement OpenAI only. A multi-provider interface is defined so switching later is straightforward, but implementing multiple providers is not worth the time in the PoC.

---

## Test Strategy

*Implements `prd.md > Open Questions > test strategy` (learner-specified).*

**Backend unit tests** (`pytest`):

| Test file | What it covers |
|---|---|
| `test_parsers.py` | Each parser against its format fixture: correct field extraction, multiline stack trace grouping, line numbers preserved, unrecognised lines flagged; `test_detector.py` verifies non-dominant-format lines appear in `unrecognised_lines` with original content intact |
| `test_rules.py` | Each of the 5 rules: fires correctly at threshold, does not fire below it, deduplicates correctly, handles missing timestamps; retry rule tests verify the operation-context requirement and the fallback to repeated-error-cluster |
| `test_api.py` | `POST /api/analyze` with sample fixture: (a) response schema valid; (b) summary counts match event list; (c) every `evidence_line_number` in every anomaly and hypothesis maps to a real entry in `events`; (d) for multiline events, all lines in `line_range` are present in `events` with correct `raw` content — **this is the evidence integrity integration test** |

Run with: `cd backend && pytest tests/ -v`

**Frontend:** manual testing against the live backend during the build. No automated frontend test framework for the PoC — it would consume build time without proving the core idea. The acceptance criteria from `prd.md > States and Boundaries` serve as the manual test checklist.

---

## Decisions and Open Issues

**Build priority order (approved):**
1. Backend: parsers, normalizer, all five detection rules, `AnalysisResult` schema.
2. Backend tests: `test_parsers.py`, `test_rules.py`, `test_api.py` (evidence integrity integration test) — all passing.
3. Sample incident fixture and parser test fixtures authored and verified.
4. FastAPI routes wired; manual `curl`/HTTP test of `POST /api/analyze` with sample.
5. Frontend: Tailwind setup, components, context, API client — integrated and verified against live backend.
6. End-to-end demo walkthrough confirmed working.
7. LLM layer only if steps 1–6 are complete with time remaining.
Do not start the frontend until backend tests pass. Do not implement LLM until the full end-to-end demo works.

**Repository layout (approved):**
The React + Vite app is already scaffolded in `frontend/`. Do not create a nested or duplicate frontend project. The Docker Compose `build:` context for the frontend service must point to `./frontend`. The Vite `/api` proxy target must be `http://backend:8000` in the Docker Compose environment and `http://localhost:8000` in local dev (use `VITE_API_BASE` env var or Vite's `server.proxy` to keep this configurable). Confirm paths before writing Dockerfiles.

**Security (approved):**
- 5 MB limit enforced on the backend (FastAPI `File` size check + body size middleware). Client-side check is UX only, not a security boundary.
- Raw source lines and line numbers are preserved exactly as received; never mutated before storage in `AnalysisResult`.
- `LLM_API_KEY` loaded exclusively from `LLM_API_KEY` environment variable. Never interpolated into frontend code or logged.
- `.env` is in `.gitignore`. `devpost/learner-profile.md` is in `.gitignore`. Both are confirmed excluded before any commit.
- `.env.example` contains only `LLM_API_KEY=` (empty value) and is safe to commit.

**Learner's genuine uncertainty — autonomous agent orchestration:**
This is the learner's first time with an agent that writes, runs, and modifies code in a repository. The agreed approach: treat each build step as a review checkpoint. After the agent writes a component, read the key logic before approving the next step — especially timestamp parsing (off-by-one in window calculations is the most likely subtle bug) and the evidence line number integrity check in `test_api.py`. The test that verifies every evidence line number in every anomaly and hypothesis points to a real entry in `events` is the single most important correctness test to review carefully.

**Stack decisions (learner-specified):**
- React + TypeScript + Tailwind CSS — accepted as-is; already scaffolded.
- Python FastAPI — accepted as-is.
- Docker Compose — accepted for local demo.

**Detection rule thresholds:**
- Error spike: 3 events / 60 s window — accepted.
- Repeated error cluster: 3 occurrences — accepted.
- Retry storm: 2 attempts / 30 s after error, same service + operation — accepted.
- Failure chain: A→B within 120 s, distinct message types — accepted.
- All thresholds are constants in `rules.py`; adjustable without architecture changes.

**LLM provider:** OpenAI (`gpt-4o-mini`) if implemented. Provider interface is defined; concrete implementation deferred until deterministic workflow + tests pass. **Verify at build time:** model name, current pricing, and library API version.

**Deduplication of hypothesis cards:** One hypothesis per unique failure-chain type pair (e.g., one "DB timeout → HTTP 500" card regardless of how many timeout events contributed). Enforced in `engine.py`.

**Timestamp ordering fallback:** Events without valid timestamps are sorted to the end of the timeline, preserving their relative file order. This is documented in the finding explanation for any rule that excludes them.

**Open issues carried from `prd.md`:**
- Sample incident log content to be authored during the build step that creates it. Must include: a JSON service log (DB timeout errors + retry messages), a plaintext/stack-trace log (exception), and optionally Nginx access log (HTTP 500 entries). All events must be timestamped consistently so failure-chain detection fires correctly.
- `LLM_API_KEY` verification: confirm the key works with `gpt-4o-mini` before implementing the LLM path, to avoid blocking time on API issues.
