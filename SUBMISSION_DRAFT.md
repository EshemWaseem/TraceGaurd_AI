# TraceGuard AI — Devpost Hackathon Submission Draft

**Project Title**: TraceGuard AI  
**Tagline**: Evidence-linked incident investigation workspace for SREs and DevOps engineers.  
**Track / Hackathon**: Build With AI: Basics / Systems & AI Reliability  

---

## 1. Project Overview & Elevator Pitch

When a high-severity production outage strikes, Site Reliability Engineers (SREs) and on-call developers face thousands of disorganized log lines across distributed services under intense pressure. Traditional approaches force engineers into two painful extremes:
1. **Manual Grepping & Scrolling**: High cognitive load, slow time-to-mitigation (MTTR), and prone to overlooking cascading root causes.
2. **Black-box LLM Chatbots**: Plagued by hallucinations, invented line numbers, and ungrounded "guesses" that no responsible engineer can trust in an active incident.

**TraceGuard AI** bridges this divide by introducing an **epistemically grounded incident investigation workspace**. TraceGuard parses unstructured and structured application logs, extracts timeline sequences, redacts sensitive credentials, and runs deterministic anomaly detection to identify retry storms, error rate spikes, and cascading service outages. Crucially, **every finding is rigorously categorized as an Observed Fact, a Detected Pattern, or an Unconfirmed Hypothesis**, and is directly hyperlinked to the exact source log line numbers that justify it. 

Engineers don't have to trust the AI's word—they can verify the raw evidence with one click.

---

## 2. Key Features & Capabilities

- **Multi-Format Log Ingestion**: Accepts up to 5 MB of logs via file upload or interactive paste. Handles structured JSON logs, plaintext Python/Java stack traces, and Nginx/Apache combined access logs. Unrecognized lines are surfaced visibly rather than discarded.
- **Automated Secret Redaction**: Identifies and masks sensitive API keys, bearer tokens, AWS credentials, and passwords prior to AI dispatch and workspace storage.
- **Deterministic Anomaly & Failure-Chain Engine**: Detects error spikes, rapid retry storms (e.g., 3+ retries in sub-second windows), and cascading downstream failures using rule-based temporal correlation.
- **Epistemic Classification**:
  - 🟢 **Observed Fact**: Direct, indisputable data points (e.g., "7 ERROR log lines observed in `db-connector`").
  - 🟡 **Detected Pattern**: Deterministically correlated sequences (e.g., "Database connection retry storm preceding HTTP 500 spike").
  - 🟣 **Unconfirmed Hypothesis**: Causal possibilities explicitly flagged for human verification with recommended diagnostic next steps.
- **Interactive Chronological Timeline**: Visually renders the incident progression with severity badges, timestamps, component tags, and direct source line navigation.
- **Multi-Tenant Collaboration Workspace**: Fully authenticated workspace with Argon2id password hashing, JWT HttpOnly cookie management, and strict organization-level anti-IDOR isolation.
- **Incident Lifecycle Management**: Persists investigations to a persistent PostgreSQL 16 database, allowing teams to search, filter, reopen, update titles/summaries, and review post-mortems.

---

## 3. How We Built It (Technical Architecture)

TraceGuard AI is designed with clean architectural boundaries and zero tolerance for fragile mocks:

```
┌────────────────────────────────────────────────────────┐
│                   React 18 + Vite UI                   │
│      Dark-mode SRE UI | Visual Timeline | Evidence     │
└───────────────────────────┬────────────────────────────┘
                            │ (JSON / REST API)
┌───────────────────────────▼────────────────────────────┐
│                  FastAPI Backend (8010)                │
│ ┌────────────────────────────────────────────────────┐ │
│ │ Ingestion & Redaction (5 MB cap, regex sanitizers)  │ │
│ ├────────────────────────────────────────────────────┤ │
│ │ Deterministic Engine (Timestamp norm, anomaly det) │ │
│ ├────────────────────────────────────────────────────┤ │
│ │ Security & Auth (Argon2id, JWT, 2-tier Rate Limit) │ │
│ ├────────────────────────────────────────────────────┤ │
│ │ Tenancy Guard (SQLAlchemy 2.0, Anti-IDOR filters)  │ │
│ └────────────────────────────────────────────────────┘ │
└───────────────────────────┬────────────────────────────┘
                            │ (psycopg driver)
┌───────────────────────────▼────────────────────────────┐
│               PostgreSQL 16 Database (5434)            │
│       Transactional Alembic DDL | Persistent Volumes   │
└────────────────────────────────────────────────────────┘
```

### Tech Stack:
- **Backend API**: Python 3.14 / 3.10+, FastAPI, Pydantic v2, Uvicorn.
- **Database & Persistence**: PostgreSQL 16, SQLAlchemy 2.0 (Declarative Mapped), Alembic migration framework with strict transactional DDL.
- **Frontend Application**: React 18, TypeScript, Vite, Vanilla CSS design system with custom SRE dark mode and glassmorphic telemetry cards.
- **Security Engineering**: Argon2id password hashing (`argon2-cffi`), PyJWT with HttpOnly SameSite=Lax cookies, process-level brute force protection, and strict tenant-scoped ORM queries.
- **Infrastructure & Containerization**: Docker Compose (`compose.yaml` for isolated host port 5434 DB; `compose.prod.yaml` with Nginx multi-stage proxy on port 8080).

---

## 4. The Deterministic vs. AI Boundary

One of TraceGuard AI's core architectural tenets is **honest engineering**:
- **Log parsing, metric aggregation, anomaly detection, and timeline sequencing are 100% deterministic.** They do not rely on an LLM, meaning they execute in milliseconds, cost $0 in API tokens, operate flawlessly offline in air-gapped environments, and never hallucinate non-existent log lines.
- **AI / LLM enrichment is bounded and optional.** When an external LLM is configured, it is strictly used to synthesize human-readable executive summaries of *already-extracted deterministic patterns*. If an LLM call fails, times out, or hallucinates an ungrounded line number, the engine falls back seamlessly to the verified deterministic report.

---

## 5. Security & Verification Evidence

TraceGuard AI was developed with exhaustive automated verification:
- **171 Automated Tests Passing**:
  - `test_parsing.py` & `test_anomaly.py`: Verified multi-format log parsing and failure chain detection.
  - `test_redaction.py`: Verified zero leak of tokens, AWS keys, and database passwords.
  - `test_auth.py` & `test_multi_tenancy.py`: Verified Argon2id password verification, JWT cookie generation, and cross-tenant anti-IDOR protection (404 on cross-organization queries).
  - `test_phase2_remediation_and_workflows.py`: Verified two-tier IP/email brute-force rate limiting and incident patch workflows.
- **Production Build Clean**: Frontend TypeScript compiles with 0 errors (`npm run build` generates 289 kB bundle).
- **Alembic Transactional Migrations**: Full PostgreSQL DDL verified without schema drifting or data loss.
- **Docker Compose Validated**: Both local dev and production multi-stage Compose files validated.

---

## 6. Challenges & Lessons Learned

1. **Combating LLM "Hand-Waving" in Ops**: Early in the design, we recognized that pure generative AI tools are actively dangerous in root cause analysis because they hallucinate logs that look plausible. Constraining the engine to deterministic extraction first and evidence linking second was our most valuable architectural decision.
2. **PostgreSQL Port & Networking Isolation**: Avoiding port collisions with preexisting host databases required mapping container port 5432 to host port 5434, and dynamically resolving hosts across local Python venv executions and containerized production networking.
3. **Hardening Against Insecure Defaults**: Eliminating unsafe proxy headers (`--forwarded-allow-ips "*"`), implementing two-tier login rate limits to defeat distributed IP credential spraying, and setting strict 5 MB ingestion boundaries ensured operational resilience.

---

## 7. What's Next for TraceGuard AI

- **OpenTelemetry & Distributed Tracing**: Correlate span IDs and trace IDs across distributed microservices alongside raw log lines.
- **Real-Time Log Ingestion**: Support WebSocket-based live streaming from FluentBit or Vector agents during active war rooms.
- **Multi-Incident Clustering**: Cross-correlate incidents over 30-day windows to detect recurring infrastructure regressions.
- **Automated Post-Mortem Export**: One-click Markdown/PDF export formatted for Jira, PagerDuty, and GitHub Issues.

---

## 8. Devpost Submission Checklist for User

- [x] **Project Name**: TraceGuard AI
- [x] **Tagline**: Evidence-linked incident investigation workspace for SREs and DevOps engineers.
- [ ] **Demo Video URL**: Record a 2–3 minute video walking through the live app using `DEMO_SCRIPT.md` (or convert `traceguard_live_demo_1792992692373.webp` to MP4 and upload to YouTube/Vimeo).
- [ ] **GitHub Repository URL**: Set repository to Public (verify no `.env` files are pushed).
- [x] **Submission Copy**: Sections above can be directly pasted into Devpost's "Inspiration", "What it does", "How we built it", "Challenges we ran into", "Accomplishments", "What we learned", and "What's next" text boxes.
