import { useState, useCallback, useRef, useEffect } from 'react'
import './App.css'
import { AuthModal } from './AuthModal'
import { SavedIncidentsModal } from './SavedIncidentsModal'
import { WorkspaceDashboard } from './WorkspaceDashboard'
import { api, APIError } from './api/client'
import { InvestigationPanel, type InvestigationReport } from './InvestigationPanel'
import { EngineeringViewModal } from './EngineeringViewModal'
import {
  ActivityIcon,
  AlertOctagonIcon,
  AlertTriangleIcon,
  CheckCircleIcon,
  ClockIcon,
  CodeIcon,
  EyeIcon,
  FileTextIcon,
  FolderIcon,
  LockIcon,
  LogOutIcon,
  PlayIcon,
  RefreshCwIcon,
  SearchIcon,
  ShieldIcon,
  SparklesIcon,
  TerminalIcon,
  UploadCloudIcon,
  UserIcon,
  XIcon,
  ZapIcon,
} from './components/Icons'

const CONFIGURED_API_URL = (import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

export interface UserOut {
  id: string
  email: string
  full_name: string | null
  is_active: boolean
  created_at: string
}

export interface OrgOut {
  id: string
  name: string
  slug: string
  role: string
}

interface MatchedRule {
  name: string
  description: string
  threshold: string
}

interface Anomaly {
  id: string
  rule: string
  title: string
  epistemic_label: 'detected_pattern'
  relationship?: 'main_finding' | 'related_evidence' | 'additional_pattern'
  explanation: string
  matched_rule: MatchedRule
  evidence_line_numbers: number[]
  supporting_line_count: number
}

interface Hypothesis {
  id: string
  title: string
  epistemic_label: 'unconfirmed_hypothesis'
  plausibility: string
  supporting_anomaly_ids: string[]
  evidence_line_numbers: number[]
  next_steps: string[]
  llm_explanation: string | null
}

interface ParsedEvent {
  line_number: number
  line_range: [number, number] | null
  timestamp: string | null
  timestamp_parsed: boolean
  severity: 'ERROR' | 'WARN' | 'INFO' | 'DEBUG' | 'UNKNOWN'
  service: string | null
  message: string
  raw: string
  format: string
}

interface UnrecognisedLine {
  line_number: number
  raw: string
  reason: string
}

interface AnalysisSummary {
  total_lines: number
  parsed_events: number
  error_count: number
  warn_count: number
  anomalies_flagged: number
  unrecognised_lines: number
  detected_format: string
}

interface AnalysisResult {
  filename: string
  summary: AnalysisSummary
  events: ParsedEvent[]
  anomalies: Anomaly[]
  hypotheses: Hypothesis[]
  unrecognised_lines: UnrecognisedLine[]
  investigation?: InvestigationReport
}

function severityBadgeClass(sev: string) {
  switch (sev.toUpperCase()) {
    case 'ERROR':
      return 'badge badge-error'
    case 'WARN':
      return 'badge badge-warn'
    case 'INFO':
      return 'badge badge-info'
    default:
      return 'badge badge-neutral'
  }
}

function formatTs(ts: string | null, parsed: boolean): string {
  if (!parsed || !ts) return 'Time unavailable'
  try {
    const d = new Date(ts)
    if (isNaN(d.getTime())) return 'Time unavailable'
    return d.toLocaleTimeString('en-GB', { hour12: false, timeZone: 'UTC' }) + ' UTC'
  } catch {
    return 'Time unavailable'
  }
}

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(2)} MB`
}

// ============================================================
// Header Component
// ============================================================

export type HealthStatus = 'ready' | 'db_offline' | 'backend_offline' | 'connecting'

function Header({
  healthy,
  user,
  activeOrg,
  onOpenAuth,
  onLogout,
  onOpenSaved,
  onOpenEngineering,
}: {
  healthy: HealthStatus
  user: UserOut | null
  activeOrg: OrgOut | null
  onOpenAuth: () => void
  onLogout: () => void
  onOpenSaved: () => void
  onOpenEngineering: () => void
}) {
  return (
    <header className="app-header">
      <div className="app-brand" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
        <div className="brand-icon-box">
          <ShieldIcon size={20} color="var(--cyan)" />
        </div>
        <div>
          <div className="brand-title">
            TraceGuard AI
            <span className="badge badge-cyan" style={{ fontSize: 10, padding: '1px 5px' }}>v2.0</span>
          </div>
          <div className="brand-subtitle">
            Incident Investigation Workspace
          </div>
        </div>
      </div>

      <div className="app-header-actions">
        {/* Engineering View trigger for Judges & SREs */}
        <button
          className="btn btn-secondary btn-sm"
          onClick={onOpenEngineering}
          title="Inspect technical architecture, pipeline stages, and deterministic rules"
          style={{ borderColor: 'var(--cyan-border)' }}
        >
          <CodeIcon size={14} color="var(--cyan)" />
          <span>Engineering View</span>
        </button>

        {user ? (
          <>
            <button
              className="btn btn-secondary btn-sm"
              onClick={onOpenSaved}
            >
              <FolderIcon size={14} color="var(--cyan)" />
              <span>Saved Investigations</span>
            </button>

            <div className="user-profile-badge">
              <UserIcon size={14} color="var(--cyan)" />
              <span className="user-name">
                {user.full_name || user.email.split('@')[0]}
              </span>
              {activeOrg && (
                <span className="user-org">
                  · {activeOrg.name} ({activeOrg.role})
                </span>
              )}
            </div>

            <button
              className="btn btn-ghost btn-sm"
              onClick={onLogout}
              title="Sign out of workspace"
            >
              <LogOutIcon size={14} />
              <span>Log out</span>
            </button>
          </>
        ) : (
          <>
            <span className="badge badge-cyan" style={{ fontSize: 11 }}>
              <ZapIcon size={12} />
              Guest Sandbox
            </span>
            <button
              className="btn btn-primary btn-sm"
              onClick={onOpenAuth}
            >
              <LockIcon size={13} />
              <span>Sign In / Register</span>
            </button>
          </>
        )}

        {/* Health status pill */}
        <div
          className="status-pill"
          title={
            healthy === 'ready'
              ? 'Backend API and PostgreSQL database are connected and operational.'
              : healthy === 'db_offline'
              ? 'Log analysis engine is ready. Workspace persistence and authentication are offline (database disconnected).'
              : healthy === 'backend_offline'
              ? (CONFIGURED_API_URL
                  ? `TraceGuard backend API at ${CONFIGURED_API_URL} is unreachable. If hosted on Render free tier, it may take ~30-50s to wake up.`
                  : 'TraceGuard backend API is unreachable on port 8010. Please start the backend service.')
              : 'Verifying system connectivity…'
          }
        >
          <span className={`pulse-dot ${healthy === 'ready' ? 'green' : healthy === 'db_offline' ? 'yellow' : healthy === 'backend_offline' ? 'red' : 'yellow'}`} />
          <span style={{ color: healthy === 'ready' ? 'var(--green)' : healthy === 'db_offline' ? 'var(--warn)' : healthy === 'backend_offline' ? 'var(--error)' : 'var(--warn)' }}>
            {healthy === 'ready' ? 'System Ready' : healthy === 'db_offline' ? 'Engine Ready · DB Offline' : healthy === 'backend_offline' ? 'Backend Offline' : 'Connecting…'}
          </span>
        </div>
      </div>
    </header>
  )
}

// ============================================================
// Ingestion Panel (File Dropzone & Textarea)
// ============================================================

interface IngestionPanelProps {
  onAnalyze: (content: string, filename: string, useAi?: boolean) => void
  loading: boolean
}

const MAX_LOG_SIZE_BYTES = 5 * 1024 * 1024

function IngestionPanel({ onAnalyze, loading }: IngestionPanelProps) {
  const [activeTab, setActiveTab] = useState<'upload' | 'paste'>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [pastedLogs, setPastedLogs] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const [fileError, setFileError] = useState<string | null>(null)
  const [useAi, setUseAi] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(async (f: File) => {
    setFileError(null)
    if (f.size > MAX_LOG_SIZE_BYTES) {
      setFileError(`File is ${fmtBytes(f.size)} — exceeds 5 MB limit. Upload a smaller file or paste a subset.`)
      setFile(null)
      return
    }

    if (f.name.toLowerCase().endsWith('.pdf') || f.type === 'application/pdf') {
      setFileError('PDF reports are not supported log files. Upload .log, .txt, or JSON logs.')
      setFile(null)
      return
    }

    try {
      const slice = await f.slice(0, 1024).text()
      if (slice.startsWith('%PDF-') || slice.includes('%PDF-')) {
        setFileError('PDF documents are not supported log files. Upload .log, .txt, or JSON logs.')
        setFile(null)
        return
      }
      if (slice.includes('\0')) {
        setFileError('Binary or non-text file format detected. Upload text-based logs.')
        setFile(null)
        return
      }
    } catch {
      // slice read fallback
    }

    setFile(f)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }, [handleFile])

  const handleLoadSample = async () => {
    setFileError(null)
    try {
      const data = await api.analysis.getSample()
      onAnalyze(data.content, data.filename, useAi)
    } catch (e: unknown) {
      setFileError(e instanceof APIError ? e.message : 'Could not load sample incident log.')
    }
  }

  const handleAnalyzeFile = async () => {
    if (!file) return
    setFileError(null)
    try {
      const text = await file.text()
      onAnalyze(text, file.name, useAi)
    } catch (e: unknown) {
      setFileError(e instanceof APIError ? e.message : 'Could not read log file.')
    }
  }

  const handleAnalyzePasted = () => {
    if (!pastedLogs.trim()) return
    setFileError(null)
    if (new Blob([pastedLogs]).size > MAX_LOG_SIZE_BYTES) {
      setFileError('Pasted text exceeds the 5 MB limit. Please reduce the log size.')
      return
    }
    onAnalyze(pastedLogs, 'pasted_logs.txt', useAi)
  }

  return (
    <div className="ingestion-card">
      <div style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-heading)', margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileTextIcon size={18} color="var(--cyan)" />
          Start an Investigation
        </h3>
        <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '4px 0 0' }}>
          Upload your application log file or paste recent logs to detect crashes, retry storms, and cascading outages.
        </p>
      </div>

      <div className="ingestion-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <div className="ingestion-tabs">
            <button
              className={`ingestion-tab-btn ${activeTab === 'upload' ? 'active' : ''}`}
              onClick={() => setActiveTab('upload')}
            >
              <UploadCloudIcon size={14} />
              <span>Upload a Log File</span>
            </button>
            <button
              className={`ingestion-tab-btn ${activeTab === 'paste' ? 'active' : ''}`}
              onClick={() => setActiveTab('paste')}
            >
              <TerminalIcon size={14} />
              <span>Paste Logs</span>
            </button>
          </div>

          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <span className="badge badge-neutral" style={{ fontSize: 10 }}>JSON logs</span>
            <span className="badge badge-neutral" style={{ fontSize: 10 }}>Python / Java stack traces</span>
            <span className="badge badge-neutral" style={{ fontSize: 10 }}>Nginx / Apache logs</span>
            <span className="badge badge-cyan" style={{ fontSize: 10 }}>Up to 5 MB</span>
          </div>
        </div>

        <button
          className="btn btn-secondary btn-sm"
          onClick={handleLoadSample}
          disabled={loading}
          style={{ borderColor: 'var(--cyan-border)' }}
          title="Try it instantly without uploading your data — loads a real database deadlock & retry cascade"
        >
          <ZapIcon size={14} color="var(--cyan)" />
          <span>⚡ Try a Sample Incident</span>
        </button>
      </div>

      {/* Tab 1: Upload */}
      {activeTab === 'upload' && (
        <div>
          <div
            className={`dropzone ${dragOver ? 'drag-active' : ''}`}
            onDrop={handleDrop}
            onDragOver={e => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onClick={() => fileRef.current?.click()}
            role="button"
            tabIndex={0}
            aria-label="Upload log file"
            onKeyDown={e => e.key === 'Enter' && fileRef.current?.click()}
          >
            <input
              ref={fileRef}
              type="file"
              accept=".log,.txt,.json"
              style={{ display: 'none' }}
              onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
              id="log-file-input"
            />
            {file ? (
              <div>
                <div className="dropzone-icon-wrap" style={{ margin: '0 auto 8px' }}>
                  <FileTextIcon size={24} color="var(--cyan)" />
                </div>
                <div style={{ fontWeight: 600, color: 'var(--text-heading)', fontSize: 14 }}>
                  {file.name}
                </div>
                <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 2 }}>
                  {fmtBytes(file.size)}
                </div>
              </div>
            ) : (
              <div>
                <div className="dropzone-icon-wrap" style={{ margin: '0 auto 10px' }}>
                  <UploadCloudIcon size={24} color="var(--cyan)" />
                </div>
                <div style={{ color: 'var(--text-heading)', fontSize: 14, fontWeight: 500 }}>
                  Drop application log file here, or <span style={{ color: 'var(--cyan)', textDecoration: 'underline' }}>browse</span>
                </div>
                <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>
                  Supports structured JSON, Java/Python stack traces, and Nginx logs
                </div>
              </div>
            )}
          </div>

          {file && (
            <div style={{ marginTop: 14, display: 'flex', gap: 10, alignItems: 'center' }}>
              <button
                className="btn btn-primary"
                onClick={handleAnalyzeFile}
                disabled={loading}
              >
                {loading ? <><span className="spinner" /> Analyzing…</> : <><PlayIcon size={14} /> Analyze Logs</>}
              </button>
              <button
                className="btn btn-ghost"
                onClick={() => setFile(null)}
                disabled={loading}
              >
                Clear
              </button>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Paste */}
      {activeTab === 'paste' && (
        <div>
          <textarea
            className="textarea-mono"
            placeholder="Paste raw log lines here (e.g. 2026-10-26T10:00:00Z [ERROR] db-connector: Connection refused...)"
            value={pastedLogs}
            onChange={e => setPastedLogs(e.target.value)}
            disabled={loading}
          />
          <div style={{ marginTop: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              {pastedLogs.split('\n').filter(Boolean).length} lines · {fmtBytes(new Blob([pastedLogs]).size)}
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="btn btn-primary"
                onClick={handleAnalyzePasted}
                disabled={loading || !pastedLogs.trim()}
              >
                {loading ? <><span className="spinner" /> Analyzing…</> : <><PlayIcon size={14} /> Analyze Logs</>}
              </button>
              <button
                className="btn btn-ghost"
                onClick={() => setPastedLogs('')}
                disabled={loading || !pastedLogs}
              >
                Clear
              </button>
            </div>
          </div>
        </div>
      )}

      {/* AI Option Toggle & Warnings */}
      <div style={{
        marginTop: 14,
        paddingTop: 12,
        borderTop: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 10
      }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer', userSelect: 'none' }}>
          <input
            type="checkbox"
            checked={useAi}
            onChange={e => setUseAi(e.target.checked)}
            style={{ accentColor: 'var(--cyan)', cursor: 'pointer' }}
          />
          <SparklesIcon size={14} color="var(--violet)" />
          <span>
            <strong>AI-Assisted Reasoning</strong> (Enriches verified findings with causal narrative; automatic deterministic fallback)
          </span>
        </label>
      </div>

      {fileError && (
        <div style={{
          marginTop: 12,
          padding: '10px 14px',
          background: 'var(--error-bg)',
          border: '1px solid var(--error-border)',
          borderRadius: 'var(--radius)',
          color: 'var(--error)',
          fontSize: 12,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          <AlertTriangleIcon size={15} color="var(--error)" />
          <span>{fileError}</span>
        </div>
      )}
    </div>
  )
}

// ============================================================
// Progress State Display
// ============================================================

const STAGES = [
  'Reading your log file and detecting its format…',
  'Parsing log entries and extracting timestamps…',
  'Checking for error spikes, retry storms, and cascading failures…',
  'Building the timeline and linking findings to source lines…',
]

function ProcessingPanel() {
  const [stage, setStage] = useState(0)

  useEffect(() => {
    const id = setInterval(() => {
      setStage(s => Math.min(s + 1, STAGES.length - 1))
    }, 700)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="card fade-in" style={{ textAlign: 'center', padding: '36px 20px', marginBottom: 20 }}>
      <div className="spinner" style={{ width: 36, height: 36, margin: '0 auto 16px', borderWidth: 3 }} />
      <h3 style={{ fontSize: 15, color: 'var(--text-heading)', marginBottom: 20 }}>
        Analyzing your logs…
      </h3>
      <div style={{ textAlign: 'left', maxWidth: 440, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {STAGES.map((s, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 14, width: 20, textAlign: 'center' }}>
              {i < stage ? <CheckCircleIcon size={16} color="var(--green)" /> : i === stage ? <RefreshCwIcon size={16} color="var(--cyan)" /> : <span style={{ color: 'var(--text-muted)' }}>○</span>}
            </span>
            <span style={{
              fontSize: 12,
              color: i < stage ? 'var(--text-secondary)' : i === stage ? 'var(--cyan)' : 'var(--text-muted)',
              fontWeight: i === stage ? 600 : 400,
            }}>
              {s}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ============================================================
// Summary Overview Panel
// ============================================================

function SummaryPanel({
  result,
  user,
  onSave,
  saving,
  saved,
  onOpenAuth,
  onReset,
}: {
  result: AnalysisResult
  user: UserOut | null
  onSave: () => void
  saving: boolean
  saved: boolean
  onOpenAuth: () => void
  onReset?: () => void
}) {
  const { summary, filename } = result
  const fmtLabel: Record<string, string> = {
    json_application: 'JSON Log', plaintext: 'Plaintext Stacks', nginx_apache: 'Nginx / Apache', unknown: 'Unknown Format',
  }

  const stats = [
    { label: 'Total Log Lines', desc: 'Total lines submitted', value: summary.total_lines, color: 'var(--text-primary)', Icon: FileTextIcon },
    { label: 'Parsed Events', desc: 'Normalized log entries', value: summary.parsed_events, color: 'var(--cyan)', Icon: ActivityIcon },
    { label: 'Errors Found', desc: 'Observed error messages', value: summary.error_count, color: 'var(--error)', Icon: AlertTriangleIcon },
    { label: 'Warnings Found', desc: 'Warning notices flagged', value: summary.warn_count, color: 'var(--warn)', Icon: AlertOctagonIcon },
    { label: 'Unusual Patterns', desc: 'Retry storms & failure chains', value: summary.anomalies_flagged, color: summary.anomalies_flagged > 0 ? 'var(--warn)' : 'var(--text-secondary)', Icon: ZapIcon },
    { label: 'Unformatted Lines', desc: 'Preserved for auditability', value: summary.unrecognised_lines, color: summary.unrecognised_lines > 0 ? 'var(--warn)' : 'var(--text-muted)', Icon: SearchIcon },
  ]

  return (
    <div className="summary-container fade-in">
      <div className="summary-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
            <ActivityIcon size={16} color="var(--cyan)" />
            Investigation Summary
          </h3>
          <span className="badge badge-cyan" style={{ fontSize: 11 }}>
            {fmtLabel[summary.detected_format] || summary.detected_format}
          </span>
          <span style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            {filename}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {onReset && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={onReset}
              title="Clear active results and start a new investigation"
            >
              <span>+ New Investigation</span>
            </button>
          )}

          {user ? (
            <button
              className="btn btn-primary btn-sm"
              onClick={onSave}
              disabled={saving || saved}
            >
              {saved ? (
                <>
                  <CheckCircleIcon size={14} color="#041017" />
                  <span>Saved to Workspace</span>
                </>
              ) : saving ? (
                <>
                  <span className="spinner" style={{ width: 12, height: 12 }} />
                  <span>Saving…</span>
                </>
              ) : (
                <>
                  <FolderIcon size={14} color="#041017" />
                  <span>Save to Workspace</span>
                </>
              )}
            </button>
          ) : (
            <button
              className="btn btn-outline btn-sm"
              onClick={onOpenAuth}
            >
              <LockIcon size={13} />
              <span>Sign in to Save</span>
            </button>
          )}
        </div>
      </div>

      <div className="stats-grid">
        {stats.map(s => {
          const { Icon } = s
          return (
            <div key={s.label} className="stat-cell">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                <span className="stat-label">{s.label}</span>
                <Icon size={13} color="var(--text-muted)" />
              </div>
              <div className="stat-value" style={{ color: s.color }}>
                {s.value}
              </div>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, display: 'block' }}>
                {s.desc}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ============================================================
// Evidence Inspector
// ============================================================

interface EvidenceInspectorProps {
  rawLines: string[]
  highlightedLineNumbers: number[]
  onClose: () => void
}

function EvidenceInspector({ rawLines, highlightedLineNumbers, onClose }: EvidenceInspectorProps) {
  const [copied, setCopied] = useState(false)
  const highlighted = new Set(highlightedLineNumbers)
  const minLine = Math.max(0, Math.min(...highlightedLineNumbers) - 4)
  const maxLine = Math.min(rawLines.length, Math.max(...highlightedLineNumbers) + 3)
  const windowLines = rawLines.slice(minLine, maxLine)

  const handleCopy = () => {
    const text = windowLines.map((line, idx) => `Line ${minLine + idx + 1}: ${line}`).join('\n')
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="card fade-in" style={{ marginBottom: 20, borderColor: 'var(--cyan-border)', background: 'var(--bg-surface)' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 10 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
            <EyeIcon size={16} color="var(--cyan)" />
            <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--cyan)', margin: 0 }}>
              Supporting Log Lines
            </h3>
            <span className="badge badge-neutral" style={{ fontSize: 10 }}>
              Lines: {highlightedLineNumbers.sort((a, b) => a - b).join(', ')}
            </span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
            Showing unedited lines from your log file. Highlighted lines are what triggered this finding. Surrounding lines give you context.
          </div>
        </div>

        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <button
            className="btn btn-ghost btn-sm"
            onClick={handleCopy}
            style={{ fontSize: 11 }}
          >
            {copied ? '✓ Copied' : 'Copy Evidence Snippet'}
          </button>
          <button
            className="btn btn-ghost btn-sm"
            onClick={onClose}
            aria-label="Close inspector"
          >
            <XIcon size={15} />
            <span>Close</span>
          </button>
        </div>
      </div>

      <div style={{
        fontFamily: 'var(--font-mono)',
        fontSize: 12,
        background: 'var(--bg-base)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        overflow: 'auto',
        maxHeight: 280,
        padding: '6px 0',
      }}>
        {windowLines.length === 0 ? (
          <div style={{ padding: '20px 16px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
            The requested source line(s) ({highlightedLineNumbers.join(', ')}) are beyond the stored log preview buffer (20 KB limit for saved investigations). You can view the event in the Incident Timeline table below.
          </div>
        ) : (
          windowLines.map((line, idx) => {
            const lineNum = minLine + idx + 1
            const isHighlighted = highlighted.has(lineNum)
            return (
              <div
                key={lineNum}
                className={`evidence-line ${isHighlighted ? 'highlighted' : ''}`}
              >
                <span className="line-num">#{lineNum}</span>
                <span style={{ color: isHighlighted ? 'var(--text-heading)' : 'var(--text-secondary)', wordBreak: 'break-all' }}>
                  {line}
                </span>
              </div>
            )
          })
        )}
      </div>

      <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--text-muted)' }}>
        <span style={{ color: 'var(--cyan)' }}>ℹ</span>
        <span>
          <strong>Note:</strong> These are the exact original lines from your log. Events appearing close together in time suggest a relationship, but do not confirm causation on their own.
        </span>
      </div>
    </div>
  )
}

// ============================================================
// Anomaly Card Component
// ============================================================

interface AnomalyCardProps {
  anomaly: Anomaly
  hypothesis?: Hypothesis
  onInspect: (lines: number[]) => void
}

function AnomalyCard({ anomaly, hypothesis, onInspect }: AnomalyCardProps) {
  const [showTechRule, setShowTechRule] = useState(false)
  const isChain = anomaly.rule === 'failure_chain'
  const isStorm = anomaly.rule === 'retry_storm'
  const isSpike = anomaly.rule === 'error_spike'
  const itemClass = isChain ? 'anomaly-item chain' : isStorm ? 'anomaly-item storm' : isSpike ? 'anomaly-item spike' : 'anomaly-item'

  const rulePlainHelper: Record<string, string> = {
    failure_chain: 'Failure Chain: One failure was followed by another related failure.',
    retry_storm: 'Retry Storm: A service repeatedly retried a failing operation in rapid succession.',
    error_spike: 'Error Spike: A sharp rise in error frequency within a brief time window.',
  }

  return (
    <div className={itemClass}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10, marginBottom: 8, flexWrap: 'wrap' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
            <span style={{ fontWeight: 600, fontSize: 13, color: 'var(--text-heading)' }}>
              {anomaly.title}
            </span>
            <span className="badge badge-warn" style={{ fontSize: 10 }}>
              DETECTED PATTERN
            </span>
            {anomaly.relationship && (
              <span className="badge badge-neutral" style={{ fontSize: 10 }}>
                {anomaly.relationship.replace('_', ' ')}
              </span>
            )}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            {rulePlainHelper[anomaly.rule] || `Rule: ${anomaly.matched_rule.name}`}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setShowTechRule(prev => !prev)}
            style={{ fontSize: 11 }}
            title="Inspect formal algorithm threshold and rule parameters"
          >
            <CodeIcon size={12} color="var(--text-muted)" />
            <span>{showTechRule ? 'Hide Rule Spec' : 'Technical Rule Spec'}</span>
          </button>
          <button
            className="btn btn-outline btn-sm"
            onClick={() => onInspect(anomaly.evidence_line_numbers)}
            aria-label={`Inspect evidence for ${anomaly.title}`}
          >
            <EyeIcon size={12} />
            <span>View supporting log lines ({anomaly.supporting_line_count})</span>
          </button>
        </div>
      </div>

      <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
        {anomaly.explanation}
      </p>

      {/* Expandable Technical Rule Details for Judges & Engineers */}
      {showTechRule && (
        <div style={{
          marginTop: 10,
          padding: '10px 14px',
          background: 'var(--bg-base)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius-sm)',
          fontSize: 11,
          fontFamily: 'var(--font-mono)',
          color: 'var(--text-muted)',
          display: 'flex',
          flexDirection: 'column',
          gap: 3,
        }}>
          <div><strong style={{ color: 'var(--text-secondary)' }}>Rule ID:</strong> {anomaly.rule}</div>
          <div><strong style={{ color: 'var(--text-secondary)' }}>Formal Name:</strong> {anomaly.matched_rule.name}</div>
          <div><strong style={{ color: 'var(--text-secondary)' }}>Deterministic Threshold:</strong> {anomaly.matched_rule.threshold}</div>
          <div><strong style={{ color: 'var(--text-secondary)' }}>Detection Algorithm:</strong> {anomaly.matched_rule.description}</div>
          <div><strong style={{ color: 'var(--text-secondary)' }}>Anchored Line Numbers:</strong> {anomaly.evidence_line_numbers.join(', ')}</div>
        </div>
      )}

      {/* Linked Hypothesis if any */}
      {hypothesis && (
        <div className="hypothesis-box">
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
            <span className="badge badge-hypothesis" style={{ fontSize: 10 }}>
              POSSIBLE EXPLANATION — NEEDS VERIFICATION
            </span>
            <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--violet)' }}>
              {hypothesis.title}
            </span>
          </div>
          {hypothesis.next_steps.length > 0 && (
            <ul style={{ margin: '6px 0 0', paddingLeft: 16, fontSize: 11, color: 'var(--text-secondary)' }}>
              {hypothesis.next_steps.slice(0, 2).map((step, i) => (
                <li key={i} style={{ marginBottom: 2 }}>{step}</li>
              ))}
            </ul>
          )}
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, fontStyle: 'italic' }}>
            Note: Temporal proximity indicates correlation, but causation requires distributed tracing.
          </div>
        </div>
      )}
    </div>
  )
}

// ============================================================
// Incident Timeline Table
// ============================================================

interface TimelineItem {
  line_number: number
  is_unrecognised: boolean
  timestamp: string | null
  timestamp_parsed: boolean
  severity: string
  service: string | null
  message: string
  raw: string
  reason?: string
}

function TimelinePanel({
  events,
  unrecognisedLines = [],
  onInspect,
}: {
  events: ParsedEvent[]
  unrecognisedLines?: UnrecognisedLine[]
  onInspect: (lines: number[]) => void
}) {
  const [filter, setFilter] = useState<string>('ALL')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 50

  const allItems: TimelineItem[] = [
    ...events.map(ev => ({
      line_number: ev.line_number,
      is_unrecognised: false,
      timestamp: ev.timestamp,
      timestamp_parsed: ev.timestamp_parsed,
      severity: ev.severity,
      service: ev.service,
      message: ev.message,
      raw: ev.raw,
    })),
    ...unrecognisedLines.map(l => ({
      line_number: l.line_number,
      is_unrecognised: true,
      timestamp: null,
      timestamp_parsed: false,
      severity: 'UNINTERPRETED',
      service: null,
      message: l.raw,
      raw: l.raw,
      reason: l.reason,
    })),
  ].sort((a, b) => a.line_number - b.line_number)

  const filtered = allItems.filter(item => {
    if (filter === 'PARSED' && item.is_unrecognised) return false
    if (filter === 'UNINTERPRETED' && !item.is_unrecognised) return false
    if (['ERROR', 'WARN', 'INFO', 'DEBUG'].includes(filter) && item.severity !== filter) return false
    if (search) {
      const q = search.toLowerCase()
      const matchMsg = item.message.toLowerCase().includes(q)
      const matchSvc = (item.service || '').toLowerCase().includes(q)
      const matchRaw = item.raw.toLowerCase().includes(q)
      if (!matchMsg && !matchSvc && !matchRaw) return false
    }
    return true
  })

  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE)
  const filters = ['ALL', 'ERROR', 'WARN', 'INFO', 'UNINTERPRETED'] as const
  const filterLabels: Record<string, string> = { ALL: 'All', ERROR: 'Errors', WARN: 'Warnings', INFO: 'Info', UNINTERPRETED: 'Other' }

  return (
    <div className="timeline-card">
      <div className="timeline-header-wrap">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
            <ClockIcon size={16} color="var(--cyan)" />
            Incident Timeline
          </h3>
          <span className="badge badge-neutral" style={{ fontSize: 11 }}>
            {filtered.length} / {allItems.length} source lines
          </span>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', width: 220 }}>
            <SearchIcon size={13} color="var(--text-muted)" style={{ position: 'absolute', left: 9, top: '50%', transform: 'translateY(-50%)' }} />
            <input
              type="text"
              className="input"
              placeholder="Search timeline events…"
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(0) }}
              style={{ paddingLeft: 28, fontSize: 12, padding: '5px 10px 5px 28px' }}
            />
          </div>

          <div style={{ display: 'flex', gap: 4 }}>
            {filters.map(f => (
              <button
                key={f}
                className={`btn btn-sm ${filter === f ? 'btn-secondary' : 'btn-ghost'}`}
                onClick={() => { setFilter(f); setPage(0) }}
                style={{
                  fontSize: 11,
                  padding: '4px 8px',
                  borderColor: filter === f ? 'var(--cyan-border)' : 'transparent',
                  color: filter === f ? 'var(--cyan)' : 'var(--text-muted)',
                }}
              >
                {filterLabels[f] || f}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="timeline-table-wrapper">
        <table className="timeline-table">
          <thead>
            <tr>
              <th style={{ width: 60 }}>Line #</th>
              <th style={{ width: 110 }}>Time (UTC)</th>
              <th style={{ width: 100 }}>Level</th>
              <th style={{ width: 130 }}>Service</th>
              <th>Log Message</th>
            </tr>
          </thead>
          <tbody>
            {paged.map(row => (
              <tr
                key={row.line_number}
                className="timeline-row"
                onClick={() => onInspect([row.line_number])}
                title="Click to view evidence context"
              >
                <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  #{row.line_number}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                  {formatTs(row.timestamp, row.timestamp_parsed)}
                </td>
                <td>
                  {row.is_unrecognised ? (
                    <span className="badge badge-neutral" style={{ fontSize: 10 }}>Other</span>
                  ) : (
                    <span className={severityBadgeClass(row.severity)} style={{ fontSize: 10 }}>{row.severity}</span>
                  )}
                </td>
                <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--cyan)', maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {row.service || '—'}
                </td>
                <td style={{ wordBreak: 'break-all' }}>
                  {row.is_unrecognised ? (
                    <div>
                      <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{row.raw}</span>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                        Format not recognized — line preserved as-is
                      </div>
                    </div>
                  ) : (
                    <span>{row.message}</span>
                  )}
                </td>
              </tr>
            ))}
            {paged.length === 0 && (
              <tr>
                <td colSpan={5} style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No timeline events match the active search or severity filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 12, justifyContent: 'flex-end' }}>
          <button className="btn btn-ghost btn-sm" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>
            ← Previous
          </button>
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Page {page + 1} of {totalPages}</span>
          <button className="btn btn-ghost btn-sm" onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}>
            Next →
          </button>
        </div>
      )}
    </div>
  )
}

// ============================================================
// Empty State & Error Display
// ============================================================

function EmptyState({
  onLoadSample,
  onFocusUpload,
}: {
  onLoadSample: () => void
  onFocusUpload: () => void
}) {
  return (
    <div className="card fade-in" style={{ padding: '40px 24px', marginBottom: 20, textAlign: 'center' }}>
      <div style={{
        width: 52,
        height: 52,
        borderRadius: 'var(--radius-full)',
        background: 'var(--cyan-dim)',
        border: '1px solid var(--cyan-border)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        margin: '0 auto 16px',
        color: 'var(--cyan)',
      }}>
        <ShieldIcon size={26} color="var(--cyan)" />
      </div>

      <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-heading)', marginBottom: 8 }}>
        Find out what went wrong in your application.
      </h2>
      <p style={{ color: 'var(--text-secondary)', fontSize: 14, maxWidth: 540, margin: '0 auto 24px', lineHeight: 1.6 }}>
        Upload a log file or paste your logs. TraceGuard highlights errors, unusual patterns, and the log lines that support each finding.
      </p>

      {/* Primary & Secondary Actions */}
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', alignItems: 'center', flexWrap: 'wrap', marginBottom: 20 }}>
        <button className="btn btn-primary btn-lg" onClick={onLoadSample}>
          <ZapIcon size={16} />
          <span>Analyze a Sample Incident</span>
        </button>
        <button className="btn btn-secondary btn-lg" onClick={onFocusUpload}>
          <UploadCloudIcon size={16} />
          <span>Upload My Log</span>
        </button>
      </div>

      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 32 }}>
        You can try the bundled sample incident without uploading your own data — loads a real database deadlock & retry cascade.
      </div>

      {/* 3-Step Guided Explanation */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 16,
        textAlign: 'left',
        paddingTop: 24,
        borderTop: '1px solid var(--border)',
        maxWidth: 780,
        margin: '0 auto',
      }}>
        <div style={{ background: 'var(--bg-elevated)', padding: '16px', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span className="badge badge-cyan" style={{ fontSize: 11, fontWeight: 700 }}>1</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>Add your logs</span>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
            Upload a file or paste recent lines from application, web-server, or container logs (up to 5 MB).
          </p>
        </div>

        <div style={{ background: 'var(--bg-elevated)', padding: '16px', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span className="badge badge-warn" style={{ fontSize: 11, fontWeight: 700 }}>2</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>Pattern analysis</span>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
            TraceGuard examines error spikes, retry storms, and cascading cross-service failures using verified rules.
          </p>
        </div>

        <div style={{ background: 'var(--bg-elevated)', padding: '16px', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span className="badge badge-success" style={{ fontSize: 11, fontWeight: 700 }}>3</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>Review findings</span>
          </div>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0 }}>
            Read plain-language summaries with clickable links directly to the exact supporting source lines.
          </p>
        </div>
      </div>
    </div>
  )
}

function ErrorBanner({ message, onDismiss }: { message: string, onDismiss: () => void }) {
  return (
    <div style={{
      marginBottom: 20,
      padding: '14px 18px',
      background: 'var(--error-bg)',
      border: '1px solid var(--error-border)',
      borderRadius: 'var(--radius)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 12,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <AlertTriangleIcon size={18} color="var(--error)" />
        <span style={{ fontSize: 13, color: 'var(--error)' }}>{message}</span>
      </div>
      <button className="btn btn-ghost btn-sm" onClick={onDismiss} style={{ color: 'var(--error)' }}>
        Dismiss
      </button>
    </div>
  )
}

// ============================================================
// Main Application Component
// ============================================================

type AppState = 'empty' | 'loading' | 'done' | 'error'

export default function App() {
  const [state, setState] = useState<AppState>('empty')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [rawContent, setRawContent] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const [healthy, setHealthy] = useState<HealthStatus>('connecting')
  const [inspecting, setInspecting] = useState<number[] | null>(null)

  // Auth, Workspace & Engineering state
  const [user, setUser] = useState<UserOut | null>(null)
  const [organizations, setOrganizations] = useState<OrgOut[]>([])
  const [activeOrgId, setActiveOrgId] = useState<string | null>(null)
  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [savedModalOpen, setSavedModalOpen] = useState(false)
  const [engineeringModalOpen, setEngineeringModalOpen] = useState(false)
  const [savingIncident, setSavingIncident] = useState(false)
  const [savedSuccess, setSavedSuccess] = useState(false)
  const [refreshStats, setRefreshStats] = useState(0)

  // Session check on mount
  useEffect(() => {
    const fetchMe = async () => {
      try {
        const data = await api.auth.me()
        setUser(data.user)
        setOrganizations(data.organizations || [])
        setActiveOrgId(data.active_organization_id || null)
      } catch {
        // demo / guest mode
      }
    }
    fetchMe()
  }, [])

  // Health check on mount and periodic interval
  useEffect(() => {
    const check = async () => {
      try {
        const dbRes = await api.health.checkDb()
        if (dbRes.status === 'connected') {
          setHealthy('ready')
        } else {
          setHealthy('db_offline')
        }
      } catch {
        try {
          const apiRes = await api.health.check()
          if (apiRes.status === 'ok') {
            setHealthy('db_offline')
          } else {
            setHealthy('backend_offline')
          }
        } catch {
          setHealthy('backend_offline')
        }
      }
    }
    check()
    const id = setInterval(check, 15_000)
    return () => clearInterval(id)
  }, [])

  const rawLines = rawContent.split('\n')

  const handleAnalyze = useCallback(async (content: string, filename: string, useAi: boolean = false) => {
    setError(null)
    setResult(null)
    setInspecting(null)
    setRawContent(content)
    setState('loading')

    try {
      const data: AnalysisResult = await api.analysis.analyze(content, filename, useAi)
      setResult(data)
      setState('done')
      setSavedSuccess(false)
    } catch (e: any) {
      const msg = e instanceof APIError ? e.message : (e instanceof Error ? e.message : 'Analysis failed')
      setError(msg)
      setState('error')
    }
  }, [])

  const handleLoadSample = useCallback(async () => {
    setError(null)
    setState('loading')
    setResult(null)
    setInspecting(null)
    try {
      const data = await api.analysis.getSample()
      setRawContent(data.content)
      await handleAnalyze(data.content, data.filename, false)
    } catch (e: any) {
      const msg = e instanceof APIError ? e.message : (e instanceof Error ? e.message : 'Network error')
      setError(`Could not load sample. ${msg}`)
      setState('error')
    }
  }, [handleAnalyze])

  const handleFocusUpload = useCallback(() => {
    const section = document.getElementById('ingestion-section')
    if (section) {
      section.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
    setTimeout(() => {
      const el = document.getElementById('log-file-input')
      if (el) el.click()
    }, 350)
  }, [])

  const handleLogout = async () => {
    await api.auth.logout()
    setUser(null)
    setOrganizations([])
    setActiveOrgId(null)
    setRefreshStats(c => c + 1)
  }

  const handleSaveIncident = async () => {
    if (!result || !user) return
    setSavingIncident(true)
    try {
      await api.incidents.create({
        organization_id: activeOrgId || undefined,
        title: `Investigation: ${result.filename}`,
        filename: result.filename,
        file_format: result.summary.detected_format,
        summary_json: result.summary,
        anomalies_json: result.anomalies,
        hypotheses_json: result.hypotheses,
        events_json: result.events,
        raw_content_preview: rawContent.slice(0, 20480),
        investigation_report_json: result.investigation || null,
        engine_version: result.investigation?.engine_version || '2.0.0',
        ai_was_used: result.investigation?.analysis_mode === 'ai_assisted',
      })
      setSavedSuccess(true)
      setRefreshStats(c => c + 1)
    } catch (err: any) {
      alert(`Could not save incident: ${err.message}`)
    } finally {
      setSavingIncident(false)
    }
  }

  const handleLoadSavedIncident = (incidentDetail: any) => {
    setResult({
      filename: incidentDetail.filename,
      summary: incidentDetail.summary_json,
      events: incidentDetail.events_json || [],
      anomalies: incidentDetail.anomalies_json || [],
      hypotheses: incidentDetail.hypotheses_json || [],
      unrecognised_lines: [],
      investigation: incidentDetail.investigation_report_json || undefined,
    })
    setRawContent(incidentDetail.raw_content_preview || '')
    setState('done')
    setSavedSuccess(true)
  }

  const activeOrg = organizations.find(o => o.id === activeOrgId) || organizations[0] || null

  return (
    <div className="app-shell">
      <Header
        healthy={healthy}
        user={user}
        activeOrg={activeOrg}
        onOpenAuth={() => setAuthModalOpen(true)}
        onLogout={handleLogout}
        onOpenSaved={() => setSavedModalOpen(true)}
        onOpenEngineering={() => setEngineeringModalOpen(true)}
      />

      <main className="app-main">
        <WorkspaceDashboard
          user={user}
          activeOrg={activeOrg}
          onOpenSaved={() => setSavedModalOpen(true)}
          onOpenAuth={() => setAuthModalOpen(true)}
          onLoadIncident={handleLoadSavedIncident}
          onLoadSample={handleLoadSample}
          refreshTrigger={refreshStats}
        />

        {healthy === 'backend_offline' && (
          <div style={{
            marginBottom: 20,
            padding: '12px 18px',
            background: 'var(--error-bg)',
            border: '1px solid var(--error-border)',
            borderRadius: 'var(--radius)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            fontSize: 13,
            color: 'var(--error)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <AlertTriangleIcon size={18} color="var(--error)" />
              <div>
                <strong>Backend Service Offline:</strong>{' '}
                {CONFIGURED_API_URL ? (
                  <>Could not connect to the TraceGuard API at <code>{CONFIGURED_API_URL}</code>. If using Render free tier, the backend may take 30–50s to wake up from cold start — please refresh or wait a moment.</>
                ) : (
                  <>Could not connect to the TraceGuard API on port 8010. Please start the backend service (<code>python -m uvicorn app.main:app --port 8010</code>) to analyze logs or save investigations.</>
                )}
              </div>
            </div>
          </div>
        )}

        {error && <ErrorBanner message={error} onDismiss={() => { setError(null); setState(result ? 'done' : 'empty') }} />}

        {state === 'loading' && <ProcessingPanel />}

        {(state === 'empty' || (state === 'error' && !result)) && (
          <div className="fade-in">
            <EmptyState
              onLoadSample={handleLoadSample}
              onFocusUpload={handleFocusUpload}
            />
            <div id="ingestion-section">
              <IngestionPanel onAnalyze={handleAnalyze} loading={false} />
            </div>
          </div>
        )}

        {state === 'done' && result && (
          <div className="fade-in">
            <SummaryPanel
              result={result}
              user={user}
              onSave={handleSaveIncident}
              saving={savingIncident}
              saved={savedSuccess}
              onOpenAuth={() => setAuthModalOpen(true)}
              onReset={() => { setState('empty'); setResult(null); setInspecting(null) }}
            />

            {/* Investigation Synthesis & Causality */}
            {result.investigation && (
              <InvestigationPanel
                report={result.investigation}
                onInspect={setInspecting}
                onOpenEngineering={() => setEngineeringModalOpen(true)}
              />
            )}

            {/* Active Evidence Inspector Drawer */}
            {inspecting && rawLines.length > 0 && (
              <EvidenceInspector
                rawLines={rawLines}
                highlightedLineNumbers={inspecting}
                onClose={() => setInspecting(null)}
              />
            )}

            {/* Anomalies & Hypotheses */}
            {result.anomalies.length > 0 && (
              <div className="card" style={{ marginBottom: 20 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
                  <h3 style={{ fontSize: 14, fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <AlertTriangleIcon size={16} color="var(--warn)" />
                    Unusual Patterns Identified ({result.anomalies.length})
                  </h3>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <span className="badge badge-warn" style={{ fontSize: 10 }}>Detected Pattern = Verified by rule</span>
                    <span className="badge badge-hypothesis" style={{ fontSize: 10 }}>Possible Explanation = Temporal correlation</span>
                  </div>
                </div>

                <div>
                  {result.anomalies.map(a => (
                    <AnomalyCard
                      key={a.id}
                      anomaly={a}
                      hypothesis={result.hypotheses.find(h => h.supporting_anomaly_ids.includes(a.id))}
                      onInspect={setInspecting}
                    />
                  ))}
                </div>
              </div>
            )}

            {result.anomalies.length === 0 && (
              <div className="card" style={{ marginBottom: 20, textAlign: 'center', padding: 28 }}>
                <CheckCircleIcon size={32} color="var(--green)" style={{ margin: '0 auto 8px' }} />
                <h4 style={{ fontSize: 14, marginBottom: 4 }}>No Unusual Patterns Found</h4>
                <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  The deterministic rules evaluated clean telemetry with no error spikes, retry storms, or failure chains.
                </p>
              </div>
            )}

            <TimelinePanel
              events={result.events}
              unrecognisedLines={result.unrecognised_lines}
              onInspect={setInspecting}
            />
          </div>
        )}
      </main>

      <footer className="app-footer">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ShieldIcon size={14} color="var(--cyan)" />
          <span>TraceGuard AI · Deterministic Incident Investigation Platform</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => setEngineeringModalOpen(true)}
            style={{ fontSize: 11, color: 'var(--cyan)', padding: '2px 8px', display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <CodeIcon size={13} color="var(--cyan)" />
            <span>How TraceGuard Works</span>
          </button>
        </div>
      </footer>

      {/* Authentication Modal */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onSuccess={(data) => {
          setUser(data.user)
          setOrganizations(data.organizations || [])
          setActiveOrgId(data.active_organization_id || null)
        }}
      />

      {/* Saved Incidents Drawer / Modal */}
      <SavedIncidentsModal
        isOpen={savedModalOpen}
        onClose={() => setSavedModalOpen(false)}
        onLoadIncident={handleLoadSavedIncident}
      />

      {/* Engineering View Modal for Hackathon Judges & Developers */}
      <EngineeringViewModal
        isOpen={engineeringModalOpen}
        onClose={() => setEngineeringModalOpen(false)}
      />
    </div>
  )
}
