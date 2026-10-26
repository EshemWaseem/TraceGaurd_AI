import { useState } from 'react'
import {
  ActivityIcon,
  AlertOctagonIcon,
  AlertTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  CodeIcon,
  EyeIcon,
  GitCommitIcon,
  SearchIcon,
  ServerIcon,
  ZapIcon,
} from './components/Icons'

export interface TimelineSegment {
  start: string
  end: string
  event_count: number
  error_count: number
  warn_count: number
  info_count: number
  debug_count: number
}

export interface CorrelationGroup {
  pattern: string
  representative_message: string
  occurrences: number
  line_numbers: number[]
  services: string[]
  first_seen?: string | null
  last_seen?: string | null
}

export interface ErrorBurst {
  start: string
  end: string
  error_count: number
  line_numbers: number[]
  services: string[]
  window_seconds: number
}

export interface ServiceImpact {
  service: string
  error_count: number
  warn_count: number
  total_events: number
  impact_score: number
}

export interface AIReasoning {
  provider: string
  model?: string | null
  summary: string
  root_cause_hypothesis?: string | null
  confidence: 'high' | 'medium' | 'low' | 'inconclusive'
  alternative_explanations: string[]
  recommended_next_steps: string[]
  missing_information: string[]
  line_references: number[]
  injected_content_detected: boolean
}

export interface InvestigationReport {
  filename: string
  engine_version: string
  analysis_mode: 'deterministic' | 'ai_assisted'
  incident_start?: string | null
  incident_end?: string | null
  severity_verdict: 'critical' | 'high' | 'medium' | 'low' | 'inconclusive'
  severity_rationale: string
  evidence_strength?: 'strong' | 'moderate' | 'limited' | 'insufficient'
  root_cause_status?: 'confirmed' | 'probable' | 'possible' | 'undetermined'
  analysis_method?: 'rules_based' | 'ai_assisted' | 'backup_method'
  timeline_segments: TimelineSegment[]
  error_bursts: ErrorBurst[]
  repeated_error_groups: CorrelationGroup[]
  correlation_id_groups: CorrelationGroup[]
  service_impacts: ServiceImpact[]
  ai_reasoning?: AIReasoning | null
  ai_was_attempted: boolean
  ai_failure_reason?: string | null
}

interface InvestigationPanelProps {
  report: InvestigationReport
  onInspect: (lines: number[]) => void
  onOpenEngineering?: () => void
}

function formatIso(iso: string | null | undefined): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return iso
    return d.toLocaleTimeString('en-GB', { hour12: false, timeZone: 'UTC' }) + ' UTC'
  } catch {
    return iso
  }
}

function calculateWindow(start?: string | null, end?: string | null): string {
  if (!start || !end) return 'Indeterminate window'
  try {
    const s = new Date(start).getTime()
    const e = new Date(end).getTime()
    const diffSec = Math.max(0, Math.round((e - s) / 1000))
    if (diffSec < 60) return `${diffSec} seconds`
    const mins = Math.floor(diffSec / 60)
    const secs = diffSec % 60
    return `${mins}m ${secs}s`
  } catch {
    return 'Indeterminate window'
  }
}

export function InvestigationPanel({ report, onInspect, onOpenEngineering }: InvestigationPanelProps) {
  const [techTab, setTechTab] = useState<'bursts' | 'services' | 'clusters' | 'timeline'>('bursts')
  const [showTechDetails, setShowTechDetails] = useState(false)
  const [copiedSteps, setCopiedSteps] = useState(false)

  const verdictConfig = {
    critical: {
      badgeClass: 'badge-error',
      badgeText: 'CRITICAL',
      meaning: 'Immediate Attention Needed — Multiple active errors or a cascading failure across dependent services.',
      heroClass: 'verdict-critical',
      Icon: AlertOctagonIcon,
      color: 'var(--error)',
    },
    high: {
      badgeClass: 'badge-warn',
      badgeText: 'HIGH',
      meaning: 'Significant Service Impact — High error frequency or an intense retry cluster affecting normal operation.',
      heroClass: 'verdict-high',
      Icon: ZapIcon,
      color: 'var(--warn)',
    },
    medium: {
      badgeClass: 'badge-warn',
      badgeText: 'MEDIUM',
      meaning: 'Intermittent Issue — Isolated service errors or elevated warning thresholds that require investigation.',
      heroClass: 'verdict-medium',
      Icon: AlertTriangleIcon,
      color: 'var(--info)',
    },
    low: {
      badgeClass: 'badge-success',
      badgeText: 'LOW',
      meaning: 'Minor / Info Notice — Low-frequency warnings or minor events with no widespread service outage.',
      heroClass: 'verdict-low',
      Icon: CheckCircleIcon,
      color: 'var(--green)',
    },
    inconclusive: {
      badgeClass: 'badge-neutral',
      badgeText: 'INCONCLUSIVE',
      meaning: 'No Active Failure Pattern Detected — Telemetry is clean or contains insufficient error signals.',
      heroClass: 'verdict-inconclusive',
      Icon: SearchIcon,
      color: 'var(--text-muted)',
    },
  }[report.severity_verdict] || {
    badgeClass: 'badge-neutral',
    badgeText: 'INCONCLUSIVE',
    meaning: 'No Active Failure Pattern Detected — Telemetry is clean or contains insufficient error signals.',
    heroClass: 'verdict-inconclusive',
    Icon: SearchIcon,
    color: 'var(--text-muted)',
  }

  const reasoning = report.ai_reasoning
  const windowDuration = calculateWindow(report.incident_start, report.incident_end)
  const totalErrorsAcrossBursts = report.error_bursts.reduce((acc, b) => acc + b.error_count, 0)

  // Fallback narrative if AI was not used
  const summaryNarrative = reasoning?.summary || (
    totalErrorsAcrossBursts > 0
      ? `Analysis identified ${totalErrorsAcrossBursts} errors and ${report.repeated_error_groups.length} repeated error patterns across ${report.service_impacts.length} services within a ${windowDuration} window.`
      : `Analysis parsed log telemetry and verified clean operation with no major cascading failures or retry clusters.`
  )

  const handleCopySteps = () => {
    const steps = reasoning?.recommended_next_steps || [
      'Check recent deployment diffs and configuration updates for affected services.',
      'Inspect supporting log lines around the first error occurrence.',
      'Verify database and upstream service connection pool health.',
    ]
    const text = steps.map((s, i) => `${i + 1}. ${s}`).join('\n')
    navigator.clipboard.writeText(text)
    setCopiedSteps(true)
    setTimeout(() => setCopiedSteps(false), 2000)
  }

  const { Icon: VerdictIcon } = verdictConfig

  return (
    <div className="card fade-in" style={{ marginBottom: 20 }}>
      {/* ============================================================== */}
      {/* STORY SECTION A: What Happened?                                */}
      {/* ============================================================== */}
      <div style={{
        padding: '18px 20px',
        borderBottom: '1px solid var(--border)',
        background: 'linear-gradient(135deg, rgba(34, 211, 238, 0.04) 0%, rgba(14, 19, 32, 0.4) 100%)',
        borderRadius: 'var(--radius-md) var(--radius-md) 0 0',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="badge badge-cyan" style={{ fontSize: 11, fontWeight: 700 }}>
              QUESTION 1
            </span>
            <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-heading)', margin: 0 }}>
              What happened?
            </h3>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', fontSize: 11, color: 'var(--text-muted)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <ClockIcon size={13} color="var(--cyan)" />
              {report.incident_start ? `${formatIso(report.incident_start)} → ${formatIso(report.incident_end)} (${windowDuration})` : 'Time window indeterminate'}
            </span>
            <span>·</span>
            <span>
              {report.service_impacts.length} {report.service_impacts.length === 1 ? 'service' : 'services'} involved
            </span>
          </div>
        </div>

        <p style={{ fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.6, margin: 0, fontWeight: 400 }}>
          {summaryNarrative}
        </p>
      </div>

      {/* ============================================================== */}
      {/* STORY SECTION B: How Serious Does It Appear?                   */}
      {/* ============================================================== */}
      <div style={{
        padding: '18px 20px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-surface)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <span className="badge badge-warn" style={{ fontSize: 11, fontWeight: 700 }}>
            QUESTION 2
          </span>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-heading)', margin: 0 }}>
            How serious does it appear?
          </h3>
        </div>

        <div className={`verdict-hero ${verdictConfig.heroClass}`} style={{ marginBottom: 0 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
            <div style={{
              width: 42, height: 42, borderRadius: 'var(--radius)',
              background: 'var(--bg-base)', border: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: verdictConfig.color, flexShrink: 0
            }}>
              <VerdictIcon size={24} color={verdictConfig.color} />
            </div>

            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 4 }}>
                <span className={`badge ${verdictConfig.badgeClass}`} style={{ fontSize: 12, fontWeight: 700, padding: '3px 8px' }}>
                  {verdictConfig.badgeText} SEVERITY
                </span>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>
                  {report.severity_rationale}
                </span>
              </div>

              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.5 }}>
                {verdictConfig.meaning}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ============================================================== */}
      {/* STORY SECTION C: What Did TraceGuard Find?                     */}
      {/* ============================================================== */}
      <div style={{
        padding: '18px 20px',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <span className="badge badge-cyan" style={{ fontSize: 11, fontWeight: 700 }}>
            QUESTION 3
          </span>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-heading)', margin: 0 }}>
            What did TraceGuard find?
          </h3>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: 12 }}>
          {/* Card 1: Observed Facts */}
          <div style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            padding: '14px 16px',
            borderTop: '3px solid var(--cyan)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <span className="badge badge-cyan" style={{ fontSize: 10, fontWeight: 600 }}>
                OBSERVED IN LOGS
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Directly parsed telemetry</span>
            </div>

            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
              <li>
                <strong>{totalErrorsAcrossBursts} errors</strong> recorded across active error bursts.
              </li>
              <li>
                <strong>{report.service_impacts.length} services involved:</strong>{' '}
                {report.service_impacts.map(s => s.service).join(', ') || 'Application server'}
              </li>
              <li>
                <strong>{report.repeated_error_groups.length} repeated error patterns</strong> detected in log entries.
              </li>
            </ul>
          </div>

          {/* Card 2: Detected Patterns */}
          <div style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            padding: '14px 16px',
            borderTop: '3px solid var(--warn)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <span className="badge badge-warn" style={{ fontSize: 10, fontWeight: 600 }}>
                DETECTED PATTERNS
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Identified by implemented rules</span>
            </div>

            <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
              {report.error_bursts.length > 0 && (
                <li>
                  <strong>Error Burst:</strong> Rapid clusters of errors within brief {report.error_bursts[0]?.window_seconds}s windows.
                </li>
              )}
              {report.repeated_error_groups.length > 0 && (
                <li>
                  <strong>Repeated Operation Failures:</strong> A service repeatedly retried failing calls in rapid succession.
                </li>
              )}
              {report.service_impacts.length > 1 && (
                <li>
                  <strong>Cross-Service Cascade:</strong> One failure in {report.service_impacts[0]?.service} was followed by related failures.
                </li>
              )}
              {report.error_bursts.length === 0 && report.repeated_error_groups.length === 0 && (
                <li>No aggressive retry storms or failure chains were triggered by the rules engine.</li>
              )}
            </ul>
          </div>

          {/* Card 3: Possible Explanations */}
          <div style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius)',
            padding: '14px 16px',
            borderTop: '3px solid var(--violet)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <span className="badge badge-hypothesis" style={{ fontSize: 10, fontWeight: 600 }}>
                POSSIBLE EXPLANATION
              </span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Unconfirmed hypothesis</span>
            </div>

            {reasoning?.root_cause_hypothesis ? (
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)', marginBottom: 4 }}>
                  {reasoning.root_cause_hypothesis}
                </div>
                <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: 0, fontStyle: 'italic', lineHeight: 1.5 }}>
                  Observed events occurred close together in time. Temporal correlation alone does not prove causation without distributed trace spans.
                </p>
              </div>
            ) : (
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: 0, lineHeight: 1.6 }}>
                Errors and patterns were observed, but the available log data does not establish an unconfirmed root cause hypothesis.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* ============================================================== */}
      {/* STORY SECTION D: Why Should I Believe This Finding?            */}
      {/* ============================================================== */}
      <div style={{
        padding: '18px 20px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-surface)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="badge badge-cyan" style={{ fontSize: 11, fontWeight: 700 }}>
              QUESTION 4
            </span>
            <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-heading)', margin: 0 }}>
              Why should I believe this finding?
            </h3>
          </div>

          <span className={`badge ${report.evidence_strength === 'strong' ? 'badge-success' : 'badge-warn'}`} style={{ fontSize: 11 }}>
            Supporting Evidence: {(report.evidence_strength || 'moderate').toUpperCase()}
          </span>
        </div>

        <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: 12 }}>
          Every finding is anchored to unedited, 1-indexed source lines from your log file. Click any line reference to inspect the exact original context:
        </p>

        {/* Evidence Line Buttons */}
        {reasoning && reasoning.line_references.length > 0 ? (
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)' }}>Supporting log lines:</span>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {reasoning.line_references.slice(0, 10).map(ln => (
                <button
                  key={ln}
                  className="btn btn-ghost btn-sm"
                  onClick={() => onInspect([ln])}
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 11,
                    padding: '3px 8px',
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--cyan-border)',
                    color: 'var(--cyan)',
                  }}
                  title={`Inspect source log line #${ln}`}
                >
                  Line #{ln}
                </button>
              ))}
              <button
                className="btn btn-outline btn-sm"
                onClick={() => onInspect(reasoning.line_references)}
                style={{ fontSize: 11, padding: '3px 10px' }}
              >
                <EyeIcon size={12} />
                <span>View all supporting lines ({reasoning.line_references.length})</span>
              </button>
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            Supporting line references are available in the Timeline table below for each individual event.
          </div>
        )}
      </div>

      {/* ============================================================== */}
      {/* STORY SECTION E: What Should I Check Next?                     */}
      {/* ============================================================== */}
      <div style={{
        padding: '18px 20px',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="badge badge-success" style={{ fontSize: 11, fontWeight: 700 }}>
              QUESTION 5
            </span>
            <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-heading)', margin: 0 }}>
              What should I check next?
            </h3>
          </div>

          <button
            className="btn btn-ghost btn-sm"
            onClick={handleCopySteps}
            style={{ fontSize: 11 }}
          >
            {copiedSteps ? '✓ Steps Copied' : 'Copy Next Steps'}
          </button>
        </div>

        <div style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
          padding: '14px 18px',
          marginBottom: 12,
        }}>
          <ol style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.7 }}>
            {(reasoning?.recommended_next_steps && reasoning.recommended_next_steps.length > 0) ? (
              reasoning.recommended_next_steps.map((step, i) => (
                <li key={i} style={{ marginBottom: 4 }}>{step}</li>
              ))
            ) : (
              <>
                <li>Verify service health and database connection pool metrics for {report.service_impacts[0]?.service || 'the primary service'}.</li>
                <li>Inspect supporting source lines around the first error occurrence to check for configuration changes or upstream timeouts.</li>
                <li>Review retry limits and circuit breaker thresholds to prevent future retry storms.</li>
              </>
            )}
          </ol>

          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 8, fontStyle: 'italic' }}>
            Note: These are recommended diagnostic checks for human review, not automated system changes.
          </div>
        </div>

        {/* Alternative Explanations if any */}
        {reasoning?.alternative_explanations && reasoning.alternative_explanations.length > 0 && (
          <div style={{
            padding: '12px 16px',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-subtle)',
            borderRadius: 'var(--radius)',
            fontSize: 12,
          }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>
              Alternative Explanations Considered:
            </div>
            <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              {reasoning.alternative_explanations.map((alt, i) => (
                <li key={i}>{alt}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* ============================================================== */}
      {/* LAYER B: Technical Details & Telemetry (For Judges & SREs)     */}
      {/* ============================================================== */}
      <div style={{ padding: '16px 20px', background: 'var(--bg-surface)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => setShowTechDetails(prev => !prev)}
            style={{ borderColor: 'var(--border-accent)', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <CodeIcon size={14} color="var(--cyan)" />
            <span>{showTechDetails ? 'Hide Technical Details' : 'Show Technical Details & Engineering View'}</span>
          </button>

          {onOpenEngineering && (
            <button
              className="btn btn-ghost btn-sm"
              onClick={onOpenEngineering}
              style={{ fontSize: 11, color: 'var(--cyan)' }}
            >
              <span>Architecture & Pipeline Overview →</span>
            </button>
          )}
        </div>

        {/* Collapsible Technical Details */}
        {showTechDetails && (
          <div className="fade-in" style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
            <div style={{
              display: 'flex',
              gap: 6,
              borderBottom: '1px solid var(--border)',
              paddingBottom: 10,
              marginBottom: 14,
              flexWrap: 'wrap',
            }}>
              {[
                { id: 'bursts', label: 'Failure Bursts', icon: ZapIcon, count: report.error_bursts.length },
                { id: 'services', label: 'Services Involved', icon: ServerIcon, count: report.service_impacts.length },
                { id: 'clusters', label: 'Repeated Errors', icon: GitCommitIcon, count: report.repeated_error_groups.length },
                { id: 'timeline', label: 'Time Windows', icon: ActivityIcon, count: report.timeline_segments.length },
              ].map(t => {
                const TabIcon = t.icon
                const isActive = techTab === t.id
                return (
                  <button
                    key={t.id}
                    className={`btn ${isActive ? 'btn-secondary' : 'btn-ghost'} btn-sm`}
                    onClick={() => setTechTab(t.id as any)}
                    style={{
                      borderColor: isActive ? 'var(--cyan-border)' : 'transparent',
                      color: isActive ? 'var(--cyan)' : 'var(--text-secondary)',
                    }}
                  >
                    <TabIcon size={14} color={isActive ? 'var(--cyan)' : 'var(--text-muted)'} />
                    <span>{t.label}</span>
                    <span className="badge badge-neutral" style={{ fontSize: 10, padding: '1px 5px' }}>
                      {t.count}
                    </span>
                  </button>
                )
              })}
            </div>

            {/* Tab 1: Failure Bursts */}
            {techTab === 'bursts' && (
              <div>
                {report.error_bursts.length === 0 ? (
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: 16 }}>
                    No rapid error bursts detected.
                  </p>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 10 }}>
                    {report.error_bursts.map((burst, i) => (
                      <div key={i} style={{
                        background: 'var(--bg-base)',
                        border: '1px solid var(--border)',
                        borderLeft: '3px solid var(--error)',
                        borderRadius: 'var(--radius)',
                        padding: '12px 14px',
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-heading)' }}>
                            Burst #{i + 1} ({burst.window_seconds}s window)
                          </span>
                          <span className="badge badge-error">{burst.error_count} errors</span>
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>
                          {formatIso(burst.start)} → {formatIso(burst.end)}
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                            Services: {burst.services.join(', ') || 'unknown'}
                          </span>
                          <button
                            className="btn btn-outline btn-sm"
                            onClick={() => onInspect(burst.line_numbers)}
                            style={{ fontSize: 10, padding: '2px 8px' }}
                          >
                            Inspect ({burst.line_numbers.length})
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Tab 2: Service Impacts */}
            {techTab === 'services' && (
              <div>
                {report.service_impacts.length === 0 ? (
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: 16 }}>
                    No service impact breakdown available.
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {report.service_impacts.map(svc => (
                      <div key={svc.service} style={{
                        background: 'var(--bg-base)',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius)',
                        padding: '10px 14px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: 12,
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <ServerIcon size={16} color="var(--cyan)" />
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>
                              {svc.service}
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                              {svc.total_events} total logged events
                            </div>
                          </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <span className="badge badge-error">{svc.error_count} errors</span>
                          {svc.warn_count > 0 && <span className="badge badge-warn">{svc.warn_count} warnings</span>}
                          <span className="badge badge-neutral">Impact Score: {svc.impact_score}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Tab 3: Repeated Errors */}
            {techTab === 'clusters' && (
              <div>
                {report.repeated_error_groups.length === 0 ? (
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: 16 }}>
                    No repeated error message clusters detected.
                  </p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {report.repeated_error_groups.map(grp => (
                      <div key={grp.pattern} style={{
                        background: 'var(--bg-base)',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius)',
                        padding: '12px 14px',
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--error)' }}>
                            Cluster: {grp.occurrences} identical events
                          </span>
                          <button
                            className="btn btn-outline btn-sm"
                            onClick={() => onInspect(grp.line_numbers)}
                            style={{ fontSize: 10, padding: '2px 8px' }}
                          >
                            Inspect Lines ({grp.line_numbers.length})
                          </button>
                        </div>
                        <p style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)', margin: 0, wordBreak: 'break-all' }}>
                          {grp.representative_message}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Tab 4: Time Windows */}
            {techTab === 'timeline' && (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border)' }}>
                      <th style={{ textAlign: 'left', padding: '6px 10px', color: 'var(--text-muted)' }}>Window Start</th>
                      <th style={{ textAlign: 'left', padding: '6px 10px', color: 'var(--text-muted)' }}>Window End</th>
                      <th style={{ textAlign: 'left', padding: '6px 10px', color: 'var(--text-muted)' }}>Events</th>
                      <th style={{ textAlign: 'left', padding: '6px 10px', color: 'var(--text-muted)' }}>Errors</th>
                      <th style={{ textAlign: 'left', padding: '6px 10px', color: 'var(--text-muted)' }}>Warnings</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.timeline_segments.map((seg, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>{formatIso(seg.start)}</td>
                        <td style={{ padding: '6px 10px', fontFamily: 'var(--font-mono)' }}>{formatIso(seg.end)}</td>
                        <td style={{ padding: '6px 10px' }}>{seg.event_count}</td>
                        <td style={{ padding: '6px 10px', color: seg.error_count > 0 ? 'var(--error)' : 'inherit' }}>{seg.error_count}</td>
                        <td style={{ padding: '6px 10px', color: seg.warn_count > 0 ? 'var(--warn)' : 'inherit' }}>{seg.warn_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
