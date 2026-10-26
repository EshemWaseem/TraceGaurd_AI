import { useEffect } from 'react'
import {
  ActivityIcon,
  CodeIcon,
  ServerIcon,
  XIcon,
} from './components/Icons'

interface EngineeringViewModalProps {
  isOpen: boolean
  onClose: () => void
}

export function EngineeringViewModal({ isOpen, onClose }: EngineeringViewModalProps) {
  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="eng-modal-title">
      <div
        className="modal-dialog"
        onClick={e => e.stopPropagation()}
        style={{ maxWidth: 860, maxHeight: '90vh', overflowY: 'auto' }}
      >
        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          borderBottom: '1px solid var(--border)',
          paddingBottom: 16,
          marginBottom: 20,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 40,
              height: 40,
              borderRadius: 'var(--radius)',
              background: 'var(--cyan-dim)',
              border: '1px solid var(--cyan-border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--cyan)',
            }}>
              <CodeIcon size={22} color="var(--cyan)" />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <h3 id="eng-modal-title" style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-heading)', margin: 0 }}>
                  How TraceGuard AI Works
                </h3>
                <span className="badge badge-cyan" style={{ fontSize: 10 }}>Engineering Architecture</span>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '4px 0 0' }}>
                Technical pipeline, deterministic algorithms, verification mechanisms, and honest system boundaries.
              </p>
            </div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close dialog">
            <XIcon size={16} />
          </button>
        </div>

        {/* Core Philosophy Banner */}
        <div style={{
          padding: '14px 18px',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-accent)',
          borderRadius: 'var(--radius)',
          marginBottom: 20,
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--cyan)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>
            Core Engineering Principle: Deterministic Proof Before AI Inference
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6, margin: 0 }}>
            TraceGuard avoids the common pitfall of relying entirely on LLM guesswork for log analysis.
            Instead, all telemetry is first parsed and validated by a <strong>deterministic rules engine</strong>.
            Every error spike, retry storm, and service failure is mathematically anchored to 1-indexed source log lines.
            AI reasoning is strictly an optional narrative synthesizer that automatically yields to verified deterministic facts.
          </p>
        </div>

        {/* 6-Stage Pipeline Breakdown */}
        <div style={{ marginBottom: 24 }}>
          <h4 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-heading)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <ActivityIcon size={16} color="var(--cyan)" />
            6-Stage Incident Analysis Pipeline
          </h4>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 12 }}>
            {/* Stage 1 */}
            <div className="card" style={{ padding: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span className="badge badge-cyan" style={{ fontSize: 10 }}>Step 1</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>Input & Format Detection</span>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                Buffers are inspected for encoding validity (UTF-8) and checked against a strict 5 MB safety ceiling.
                Non-text binaries and PDF documents are intercepted before parsing. The format detector uses pattern scoring to identify structured JSON, Java/Python stack traces, or Nginx/Apache formats.
              </p>
            </div>

            {/* Stage 2 */}
            <div className="card" style={{ padding: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span className="badge badge-cyan" style={{ fontSize: 10 }}>Step 2</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>Normalization & UTC Alignment</span>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                Timestamps in diverse ISO, Syslog, or Epoch formats are converted to unified UTC time coordinates.
                Multi-line stack traces are collated into atomic event records. Unrecognized lines are never dropped; they are preserved as unformatted entries for complete forensic auditability.
              </p>
            </div>

            {/* Stage 3 */}
            <div className="card" style={{ padding: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span className="badge badge-warn" style={{ fontSize: 10 }}>Step 3</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>Deterministic Rule Matching</span>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                The engine evaluates formal detection algorithms:
                <br />• <strong>Error Spikes:</strong> Sliding window rate counters detect sudden error velocity.
                <br />• <strong>Retry Storms:</strong> Rapid clusters of identical client requests with exponential or linear repeat signatures.
                <br />• <strong>Failure Chains:</strong> Sequential cross-service failures (e.g., DB pool exhaustion followed by API gateway 504 timeouts).
              </p>
            </div>

            {/* Stage 4 */}
            <div className="card" style={{ padding: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span className="badge badge-cyan" style={{ fontSize: 10 }}>Step 4</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>Source-Line Evidence Anchor</span>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                Every anomaly, repeated cluster, and burst contains an exact array of 1-indexed source line numbers.
                In the frontend, clicking any citation renders the Evidence Inspector with the unedited raw log slice and contextual padding, preventing hallucinated citations.
              </p>
            </div>

            {/* Stage 5 */}
            <div className="card" style={{ padding: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span className="badge badge-hypothesis" style={{ fontSize: 10 }}>Step 5</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>Adversarial AI Defense</span>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                When AI synthesis is requested, input strings are scanned for prompt-injection markers (e.g. system instruction overrides, markdown escape attacks).
                If suspicious content is detected or the LLM is unconfigured/unreachable, TraceGuard safely switches to the deterministic fallback synthesizer.
              </p>
            </div>

            {/* Stage 6 */}
            <div className="card" style={{ padding: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span className="badge badge-success" style={{ fontSize: 10 }}>Step 6</span>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>Tenant-Isolated Persistence</span>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
                Saved investigations are stored in PostgreSQL 16 with organization-scoped multi-tenancy.
                All database queries validate user session tokens, organization memberships, and role authorizations with anti-IDOR checks.
              </p>
            </div>
          </div>
        </div>

        {/* Technology Stack Grid */}
        <div style={{ marginBottom: 24 }}>
          <h4 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-heading)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <ServerIcon size={16} color="var(--cyan)" />
            Verified Technology Stack
          </h4>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: 10,
          }}>
            <div className="stat-cell" style={{ background: 'var(--bg-surface)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Frontend Framework</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--cyan)' }}>React 18 + Vite</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>TypeScript, Zero UI Bloat</div>
            </div>

            <div className="stat-cell" style={{ background: 'var(--bg-surface)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Backend API</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--cyan)' }}>FastAPI (Python 3.11)</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>Pydantic v2 validation</div>
            </div>

            <div className="stat-cell" style={{ background: 'var(--bg-surface)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Database & ORM</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--green)' }}>PostgreSQL 16</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>SQLAlchemy 2.0 & Alembic</div>
            </div>

            <div className="stat-cell" style={{ background: 'var(--bg-surface)' }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Authentication</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--violet)' }}>Argon2id Hashes</div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>JWT Session Security</div>
            </div>
          </div>
        </div>

        {/* Honest Boundaries & Known Constraints */}
        <div style={{
          padding: '14px 18px',
          background: 'rgba(234, 179, 8, 0.05)',
          border: '1px solid rgba(234, 179, 8, 0.25)',
          borderRadius: 'var(--radius)',
        }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--warn)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 4 }}>
            System Boundaries & Honest Engineering Disclaimers
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            <li>
              <strong>Scope:</strong> TraceGuard analyzes single-session log batches up to 5 MB per run. It is not an unbounded real-time distributed stream consumer.
            </li>
            <li>
              <strong>Epistemic Humility:</strong> Observed events are facts; rule matches are patterns; root-cause suggestions are explicitly marked as <em>unconfirmed hypotheses</em>. TraceGuard never claims 100% causal certainty without distributed trace spans (e.g. OpenTelemetry trace IDs).
            </li>
            <li>
              <strong>Zero Secret Storage:</strong> TraceGuard never persists raw environment variables or credentials in client bundles or public payloads.
            </li>
          </ul>
        </div>

        {/* Footer actions */}
        <div style={{ marginTop: 20, display: 'flex', justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={onClose}>
            Close Engineering View
          </button>
        </div>
      </div>
    </div>
  )
}
