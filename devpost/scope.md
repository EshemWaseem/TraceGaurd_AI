---
doc: scope
status: approved
---

# TraceGuard AI

An incident investigation workspace where engineers upload logs and get an evidence-linked, auditable breakdown of what happened — not a black-box AI answer.

## The Unique Kernel

Every finding is epistemically labelled: observed fact, detected pattern, or unconfirmed hypothesis. Every label is linked to the exact source log lines that support it. If the logs don't support a conclusion, the app says so. This is what separates TraceGuard from a log viewer that summarises and a chatbot that guesses.

## Who It's For

A software engineer or SRE in the middle of a production incident. They have thousands of log lines, no clear starting point, and pressure to find the cause fast. Today they grep, scroll, and guess. TraceGuard gives them a structured sequence and the evidence to verify it themselves.

## The Core Loop

Upload or paste a log file → the app parses and normalises it, groups related events, detects anomaly patterns, and builds a chronological timeline → the engineer moves from a flagged anomaly to the exact supporting log lines in one click → they see a hypothesis card that names a possible failure chain, links to evidence, and recommends what to check next.

## Inspiration & Identity

Feels like a serious developer tool in the lineage of Datadog, Grafana, and Honeycomb — dark interface, precise typography, dense information without clutter. Glassmorphism used sparingly for hierarchy, not decoration. The tone is clinical and trustworthy; nothing should feel like a consumer AI product.

## Why This Matters to the Learner

A technically credible demo that solves a recognisable engineering problem. Practising the full plan-first workflow with an autonomous agent. Learning where deterministic analysis beats LLM guessing, and where an LLM explanation layer earns its place.

## What "Working" Looks Like

A realistic sample incident log — database timeouts, retries, HTTP 500 spike — is uploaded. The timeline renders the event sequence chronologically. An anomaly card flags the timeout/retry/500 failure chain. A hypothesis card states that database timeouts may have contributed to the HTTP 500 spike, explicitly labelled as unconfirmed. The evidence panel shows the original log lines beside the finding. A viewer can verify the reasoning without trusting the AI's word for it. The whole demo runs reproducibly with no external API key.

## The POC Boundary

**In:**
- Log ingestion: file upload (max 5 MB; files exceeding this are rejected with a clear error) and paste (same 5 MB character-equivalent limit; excess is flagged, not silently truncated).
- Three supported formats: structured JSON application logs; Python/Java plaintext with multiline stack traces; Nginx/Apache combined access log.
- Unrecognised lines flagged visibly, not silently discarded.
- Deterministic analysis pipeline: timestamp normalisation, severity grouping, error clustering, failure-chain pattern detection, line-number evidence linking.
- Incident timeline (chronological, filterable by severity/service).
- Anomaly list with evidence panel (source log lines for each finding).
- Hypothesis cards: labelled unconfirmed, evidence-linked, with recommended next steps.
- Evidence linking uses original source line numbers. Every finding references the exact source lines that support it.
- Evidence-strength display: show matched rules and supporting line count only when transparently derived from deterministic rule matches. No numeric confidence score; if it can't be justified, omit it entirely.
- Sample incident log file bundled for demo use.
- Docker Compose for local setup.

**Optional (time-permitting):**
- LLM explanation layer: summarises already-detected patterns and suggests hypotheses. Gated behind an API key; app works fully without it. Backend validates evidence references before surfacing any LLM output.

## Later

- Stable event IDs for cross-session evidence linking.
- Live log streaming or production integrations.
- Multi-file / distributed-trace correlation.
- Persistent sessions and investigation history.
- User authentication.
- Additional log format support.

## Explicitly Cut

- Kubernetes monitoring — not needed to prove the core loop.
- Billing and auth — no multi-user scope in the PoC.
- Multi-agent or orchestration architectures — complexity without PoC benefit.
- Any LLM output that isn't grounded in a prior deterministic finding — the app will not invent explanations.
- Evidence-strength scores that can't be justified from rule-match data — a fabricated number is worse than no number.
