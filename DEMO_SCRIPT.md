# TraceGuard AI — Demo Video Script (2–3 Minutes)

**Target Duration:** 2:30 – 3:00  
**Application URLs:** `http://localhost:5173` (Frontend) | `http://127.0.0.1:8010` (Backend API)  
**Tone:** Professional SRE, crisp, evidence-focused, authoritative.

---

## Pre-Flight Checklist Before Recording
1. **Docker Database:** Verify `traceguard-db` is running on host port `5434`.
2. **Backend API:** Verify Uvicorn is active on `http://127.0.0.1:8010` (`GET /api/health` returns `{"status":"ok"}`).
3. **Frontend UI:** Open `http://localhost:5173` in a clean browser window (100% zoom, 1920×1080 or 1366×768).
4. **Recording Tool:** Windows Game Bar (`Win + Alt + R`), OBS Studio, or Loom.

---

## Video Timeline & Narration

### [0:00 – 0:30] Introduction & The Problem
- **Visual:** Browser on `http://localhost:5173`. Show the landing page with the header badge `"Backend connected"`. Point cursor to the log ingestion area.
- **Narration:**
  > "When production incidents strike, engineering teams are inundated with thousands of raw, noisy log lines across distributed services. Today, engineers either waste hours manually grepping logs or blindly paste proprietary traces into public AI chats—leaking database credentials, risking prompt injection, and getting hallucinated line references.
  > 
  > This is **TraceGuard AI**—an evidence-first incident investigation workspace designed for site reliability engineers. It combines deterministic log parsing, causal anomaly detection, automated secret redaction, and bounded AI reasoning inside a secure, multi-tenant workspace."

---

### [0:30 – 1:00] Authentication & Multi-Tenant Workspace
- **Visual:** 
  1. Click **🔐 Sign In / Register** in the top navigation.
  2. Select **Sign In** (or Sign Up with `demo_sre_2026@traceguard.io`).
  3. Log in. Point to the header displaying `Demo SRE · Reliability Operations (owner)`.
- **Narration:**
  > "Security starts at the perimeter. TraceGuard enforces multi-tenant isolation with Argon2id password hashing, signed JWT sessions, and role-based access control. Every investigation is scoped to an organization with strict anti-IDOR protections, ensuring cross-tenant data requests are rejected at the database query level with HTTP 404 responses."

---

### [1:00 – 1:40] Log Ingestion & Secret Redaction
- **Visual:**
  1. Click **⚡ Load Sample Incident** in the ingestion card.
  2. Scroll through the populated JSON logs briefly.
  3. Click **Analyze Incident** (or toggle bounded AI).
  4. Wait ~1 second as results appear dynamically.
- **Narration:**
  > "Let's load a real-world multi-service incident log featuring authentication timeouts, connection retries, and database deadlocks.
  > 
  > TraceGuard handles multi-format logs—JSON, plaintext stack traces, and Nginx access logs. Notice what happens before processing: the engine automatically redacts bearer tokens, database passwords, and AWS keys from AI dispatch and persisted previews. Furthermore, untrusted log text is strictly isolated from system prompts, detecting and safely neutralizing adversarial prompt-injection patterns."

---

### [1:40 – 2:15] Investigation Synthesis & Event Timeline
- **Visual:**
  1. Highlight the **Investigation Synthesis** panel:
     - Point to the **What Happened** summary (e.g., *7 errors detected, db-connector failure*).
     - Point to the **Evidence Strength: STRONG** and **Root Cause Status: PROBABLE**.
  2. Scroll down to the **Causal Chain & Suspected Hypotheses**:
     - Show the correlation between the retry storm and the subsequent fatal deadlock.
  3. Scroll through the **Event Timeline**:
     - Point out the exact line numbers (`L#`), timestamp conversions (UTC ISO-8601), and preserved uninterpreted lines.
- **Narration:**
  > "Here is our investigation synthesis. TraceGuard's core reasoning is intentionally deterministic and reproducible.
  > 
  > It separates raw correlation from confirmed causation: it flags an error burst and a 3-attempt retry storm in the database connector, identifies the probable root cause, and cites the exact 1-indexed source line numbers. Crucially, zero valid lines are silently discarded—even unparsed or corrupted entries are preserved with original line numbers for full evidentiary auditability."

---

### [2:15 – 2:45] Workspace Persistence & Search
- **Visual:**
  1. Click **💾 Save to Workspace**. Confirm the button reflects `✅ Saved`.
  2. Click **📁 Saved Incidents** in the top navigation.
  3. Show the modal list with metadata: line count, error count, and timestamp.
  4. Type `sample` in the search box to demonstrate real-time filtering.
  5. Close modal.
- **Narration:**
  > "Once analyzed, SREs can save the investigation directly to the organization workspace. The incident is stored in PostgreSQL with bounded preview sizes (capped at 20 KB) and strict tenant scoping. Teammates can search, filter, and review historical post-mortems in seconds."

---

### [2:45 – 3:00] Conclusion & Architecture
- **Visual:**
  1. Switch briefly to the terminal or architecture overview slide.
  2. Show `pytest` 171 passed tests and Docker Compose container health.
- **Narration:**
  > "TraceGuard AI is verified end-to-end: 171 automated backend tests, production-built React frontend, Alembic transactional migrations, and Docker containerization. It delivers the speed and clarity incident responders need, grounded in empirical evidence.
  > 
  > Thank you for reviewing TraceGuard AI."

