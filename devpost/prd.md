---
doc: prd
status: approved
---

# TraceGuard AI — Product Requirements

An incident investigation workspace for software engineers and SREs: upload application logs, get an evidence-linked, epistemically honest breakdown of what happened.
Source: `scope.md > Who It's For`, `scope.md > The Unique Kernel`.

---

## The Core Journey

Source: `scope.md > The Core Loop`, `scope.md > What "Working" Looks Like`.

1. User opens TraceGuard AI and sees the Incident Workspace in its empty state.
2. User selects one of three ingestion actions: upload a log file (drag-and-drop or file picker), paste logs directly, or load the bundled sample incident.
3. The app validates the input (format hint, size limit), then transitions to a staged processing view showing which analysis stage is running.
4. Processing completes; the app transitions to the Analysis Workspace.
5. The Summary Strip shows actual counts: parsed events, errors detected, anomalies flagged, unrecognised lines.
6. The Incident Timeline (left column) shows events chronologically with timestamps, severity, and service labels.
7. The Findings column (centre) shows anomaly cards and hypothesis cards in order of significance.
8. The user clicks an anomaly or hypothesis card. The Evidence Inspector (right column) populates with the original log lines that support that finding, with relevant lines highlighted.
9. The user clicks a line reference in a card. The Evidence Inspector navigates to and highlights that exact source line.
10. The user clicks a timeline event. The Evidence Inspector shows its source line and any associated findings are indicated.
11. Optionally: if an API key is configured and the user selects "AI-Enhanced Explanations," hypothesis cards gain an LLM-generated explanation section, clearly labelled.
12. The user clicks "New Investigation" to return to the empty Incident Workspace.

---

## Screens and Layout

### Screen 1 — Incident Workspace (Empty State)

- Compact top navigation bar: TraceGuard AI logo + wordmark, "Local Analysis" status indicator (no external connection required).
- Main heading: "Understand what happened."
- Supporting text: "Upload application logs to reconstruct the incident timeline, detect suspicious patterns, and inspect evidence-backed findings."
- Central ingestion panel with three clearly labelled actions:
  - **Upload Log File** — primary action. Drag-and-drop target; also a file picker button.
  - **Paste Logs** — opens an inline text area with an Analyse button.
  - **Load Sample Incident** — loads the bundled sample log and runs the full analysis workflow.
- Supported-formats hint: "JSON application logs · Python/Java stack traces · Nginx/Apache combined access logs · Max 5 MB."
- No fake metrics, no placeholder analysis results, no fabricated incidents.

### Screen 2 — Processing View

Replaces the ingestion panel after input is accepted. Displays four named stages in sequence:
1. Validating input and detecting log format.
2. Parsing log entries and normalising timestamps.
3. Detecting anomalies and matching deterministic rules.
4. Building the timeline, findings, and evidence references.

Each stage shows: completed (checkmark), active (indeterminate indicator + label), pending (muted). Actual counts (lines parsed, events detected) are displayed from the completed result, not fabricated mid-stream. For the PoC, the backend may process synchronously and return a completed result; the UI shows honest stage messaging with an indeterminate indicator rather than fake progress.

On error: specific, actionable message (e.g., "Unsupported format — only JSON, plaintext, and Nginx/Apache combined access logs are accepted") plus a Retry / Start Over action.

### Screen 3 — Analysis Workspace

Three-column layout on desktop. All three columns visible simultaneously when viewport permits.

**Top header:** TraceGuard AI logo, current incident filename, analysis status badge, "New Investigation" button.

**Summary Strip (full width, below header):** actual counts for total parsed events, errors detected, anomalies flagged, unrecognised lines.

**Left column — Incident Timeline**
- Chronologically ordered log events, one row per event.
- Each row: timestamp (normalised), severity badge (ERROR / WARN / INFO), service label (if available in the log), short message preview.
- Severity filter and service filter (multi-select where applicable).
- Clicking a timeline event highlights the source line in the Evidence Inspector and indicates associated findings.

**Centre column — Findings**
- Anomaly cards (top) followed by hypothesis cards.
- No results state: "No anomalies detected. Review the timeline for individual events." (Not a fabrication.)

*Anomaly card anatomy:*
- Title (concise, in the engineer's vocabulary).
- Epistemic label: **"Detected pattern"** (pill/badge).
- Short explanation of what was observed.
- Matched rule: rule name, match criteria (e.g., "≥ 3 occurrences within 60 s").
- Supporting evidence: source line references (line number, short preview). Clicking any reference navigates the Evidence Inspector to that line.
- Supporting line count (e.g., "5 matching lines").

*Hypothesis card anatomy:*
- Title.
- Epistemic label: **"Unconfirmed hypothesis"** (visually distinct from anomaly label — different colour/style).
- Why it's plausible: the deterministic patterns that support it, in plain language.
- Supporting evidence: same line-reference format.
- **Recommended next steps:** concrete investigation actions (e.g., "Check database connection pool metrics for this time window," "Review the service that emitted the first timeout").
- LLM section (only when AI-Enhanced mode is active and key is present): "AI-generated explanation" label, LLM-produced prose below. Never mixed into observed facts.

**Right column — Evidence Inspector**
- Persistent; never replaced by another panel.
- Empty state: "Select a finding or timeline event to inspect its source evidence."
- Active state: displays original log text, preserving exact whitespace and encoding. Line numbers shown. Relevant lines visually highlighted (background or left-border accent). Non-highlighted lines dimmed but readable.
- A deselect control (e.g., × or "Clear selection") returns the inspector to its empty state.
- Filters applied to the timeline do not alter evidence line references; the inspector always shows original source lines.

### Responsive Behaviour

- **Desktop (≥ 1280 px):** three columns visible simultaneously.
- **Tablet (768–1279 px):** Evidence Inspector collapses to a slide-in drawer. Selected finding and context are preserved when the drawer is open or closed.
- **Mobile (< 768 px):** single-column layout. Timeline, Findings, and Evidence Inspector accessible via tabs or expandable sections.

---

## Look and Feel

Source: `scope.md > Inspiration & Identity`, learner-supplied direction.

- **Colour palette:** dark graphite/navy background. Cyan and violet as restrained accent colours for interactive elements, labels, and highlights. No vibrant or saturated primaries.
- **Glassmorphism:** used sparingly for panel surfaces to convey hierarchy, not for decoration. Readability of dense log text takes priority over visual effects.
- **Typography:** clean, highly legible sans-serif for UI text. Monospace font for all log content, line numbers, and source evidence. Excellent contrast throughout.
- **Tone:** clinical and trustworthy. Feels like a professional developer tool (Datadog / Grafana / Honeycomb lineage), not a consumer AI product.
- **Epistemic labels:** anomaly and hypothesis labels must be visually distinct from each other and from plain body text — use differing colours and/or badge styles, never the same treatment.

---

## Features and Behavior

### Log Ingestion

Source: `scope.md > The POC Boundary`.

- **File upload:** drag-and-drop onto the ingestion panel, or file picker. Accepted MIME types: `application/json`, `text/plain`, `text/x-log` and unlabelled text. Max 5 MB. Files exceeding 5 MB are rejected with a specific error message and the file is not processed.
- **Paste:** text area with Analyse button. Applies the same 5 MB character-equivalent limit. Input exceeding the limit is flagged, not silently truncated.
- **Load Sample Incident:** loads the bundled realistic sample log (database timeouts → retries → HTTP 500 spike) and triggers the full analysis workflow. Requires no user preparation.
- Supported formats: structured JSON application logs (fields: timestamp, level, message, service, error); Python/Java-style plaintext with multiline stack traces; Nginx/Apache combined access log format.
- Unrecognised lines: flagged, counted, and surfaced in the Unrecognised Lines section (see below). Never silently discarded.

### Processing

- Input is validated before processing begins. Invalid format, oversized input, or empty input produces a specific error and a Retry / Start Over option.
- Staged processing view per Screen 2. No fake progress; if processing is synchronous, the UI displays honest stage labels with indeterminate indicators.
- On backend error or timeout: preserve any partial state, show a specific error message, offer retry.

### Incident Timeline

- Events ordered by normalised timestamp, earliest first.
- Severity filter (ERROR, WARN, INFO, DEBUG — multi-select). Service filter (derived from the log's service field; available only when logs contain service labels).
- Filtering updates the visible timeline events. Evidence references in findings are never altered by filters; they always point to original source lines.
- Selected event: highlighted in the timeline; its source line highlighted in the Evidence Inspector; any associated findings indicated (e.g., soft highlight on relevant finding cards).

### Findings

- **Anomaly cards** represent patterns detected by deterministic rules (error clustering, frequency thresholds, failure chains). Each is grounded in log evidence; nothing is invented.
- **Hypothesis cards** represent plausible but unconfirmed failure-chain explanations. Explicitly labelled unconfirmed. Supported by the anomaly evidence that leads to the hypothesis, not standalone claims.
- No anomalies found → genuine no-findings state. No fabricated issues.
- Cards are ordered by significance (error-level findings first; hypothesis cards after anomaly cards).

### Evidence Inspector

- Always displays original log text with source line numbers.
- Highlight behaviour: relevant lines receive a visual accent; surrounding lines are visible but dimmed.
- Multiline log entries (e.g., stack traces) are displayed intact, not truncated.
- Deselect control available at all times when a finding is selected.

### Unrecognised Lines

- Visible section in the Analysis Workspace (e.g., collapsible below the Findings column or in a dedicated tab).
- Shows count and the actual unrecognised line text with source line numbers.
- Reason for non-recognition where determinable (e.g., "Timestamp format not recognised").

### LLM-Enhanced Mode (Optional)

Source: `scope.md > The POC Boundary > Optional`.

- Available only when an API key is configured. Default mode is **Deterministic Only**; the core workflow is complete without this mode.
- Visible mode selector in the Analysis Workspace header area: **Deterministic Only** / **AI-Enhanced Explanations**.
- In AI-Enhanced mode: hypothesis cards gain an "AI-generated explanation" section below the deterministic content. Clearly labelled. Never placed in the observed facts or detected pattern sections.
- The LLM receives only deterministic findings and their supporting log lines. Any returned line references are validated against original source lines before display. Invalid references are discarded silently; the deterministic result is preserved.
- On LLM failure, timeout, or invalid response: non-blocking message (e.g., banner: "AI explanations unavailable — showing deterministic results"). Deterministic findings remain intact and fully functional.
- If LLM integration cannot be completed and tested reliably within the hackathon window, deterministic-only mode ships. The core workflow does not depend on an external provider.

---

## States and Boundaries

- **Empty state (Ingestion screen):** No prior analysis. Ingestion panel visible with all three actions. No fabricated content.
- **Validation error:** Specific message naming the problem (format unrecognised, file too large, empty input). Retry and Start Over available.
- **Processing:** Staged indicator, honest messaging, no fake counts. Error with retry on failure.
- **Analysis: results found:** Full three-column workspace populated. Summary strip shows actual counts.
- **Analysis: no anomalies found:** Timeline populated; Findings column shows genuine no-findings message. Evidence Inspector shows empty state.
- **Analysis: all lines unrecognised:** Summary strip reflects 0 parsed events. Findings empty. Unrecognised Lines section shows all input. User sees an actionable explanation.
- **Evidence Inspector empty:** "Select a finding or timeline event to inspect its source evidence." Nothing selected, nothing fabricated.
- **LLM unavailable (key missing or not configured):** Mode selector hidden or disabled. Deterministic-only mode operates normally.
- **LLM failure mid-session:** Non-blocking banner. Deterministic results unchanged.
- **Filter active:** Timeline and Findings update. Evidence references always point to original unfiltered source lines.
- **Session:** No persistence between sessions. Closing or refreshing the page returns to the empty state. No login or account required.

---

## Product Decisions

- **Line-number evidence linking over stable event IDs** — sufficient for the PoC; avoids hash-scheme complexity. Revisit for multi-session use later.
- **5 MB input limit, file and paste** — oversized input rejected with a clear error, never silently truncated.
- **Evidence-strength display: matched rules + supporting line count** — shown only when transparently derived from deterministic rule matches. No numeric confidence score; omitted entirely if it cannot be justified.
- **LLM as optional explanation layer only** — the detection engine is entirely deterministic. LLM receives findings and evidence, not raw logs for independent analysis.
- **Deterministic-only ships if LLM integration is unreliable** — core workflow does not depend on an external provider.
- **No auth, no persistence, no live integrations** — local analysis only, session-scoped.
- **Three log formats committed for PoC** — JSON application logs, Python/Java plaintext + stack traces, Nginx/Apache combined access log. Others are flagged as unrecognised.

---

## What We're Building

- Incident Workspace: empty state, ingestion panel (upload, paste, load sample), format hint, size limit.
- Validation and staged processing view with honest stage messaging.
- Analysis Workspace: three-column desktop layout; Summary Strip with actual counts.
- Incident Timeline with severity and service filters; bidirectional selection with Evidence Inspector.
- Findings column: anomaly cards and hypothesis cards with epistemic labels, evidence references, matched rule info, and recommended next steps.
- Evidence Inspector: persistent right column, original log text, line numbers, relevant-line highlighting, deselect control.
- Unrecognised Lines section: count, content, and reason where determinable.
- Responsive layout: drawer on tablet, tabbed single-column on mobile.
- Bundled sample incident log (database timeouts → retries → HTTP 500 spike).
- LLM-Enhanced mode (optional, time-gated): mode selector, AI explanation section in hypothesis cards, labelled attribution, evidence-reference validation, graceful fallback.
- Docker Compose for local setup.

---

## Deferred From the POC

- **Stable event IDs** — cross-session evidence linking; not needed for a single-session demo.
- **Live log streaming / production integrations** — scope explicitly excludes live data sources.
- **Multi-file or distributed-trace correlation** — single-file analysis only for the PoC.
- **Persistent sessions and investigation history** — no storage between sessions.
- **User authentication** — local analysis; no accounts.
- **Additional log format support** — only the three committed formats. Others flagged.
- **Real-time processing progress** — backend returns a completed result; UI shows honest indeterminate indicators.

---

## Non-Goals

- No live Kubernetes or infrastructure monitoring.
- No billing or multi-tenant features.
- No multi-agent orchestration architecture.
- The LLM does not independently analyse raw logs or verify findings — it only supplements already-detected deterministic results.
- No fabricated confidence scores, fake metrics, or invented incidents.
- No deployment to a public URL (submission requires a working local demo and a public repository; deployment is optional).

---

## Open Questions

- **LLM provider and model** — which provider and model, if LLM integration is included? This is a `4-spec` decision; does not block PRD approval.
- **Failure-chain detection rules** — the specific deterministic rules (frequency thresholds, time windows, pattern sequences) are a `4-spec` / build decision. The PRD specifies what the user sees; the rules are implementation detail.
- **Sample incident log** — content to be authored during the build to demonstrate the full failure chain (DB timeout → retry → HTTP 500). Needs to exercise all three supported log formats or document which formats it uses.
