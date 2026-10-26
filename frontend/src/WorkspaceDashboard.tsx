import { useState, useEffect } from 'react'
import { api, APIError } from './api/client'
import type { UserOut, OrgOut } from './App'
import {
  ActivityIcon,
  AlertTriangleIcon,
  CheckCircleIcon,
  FileTextIcon,
  FolderIcon,
  ShieldIcon,
  UserIcon,
  ZapIcon,
} from './components/Icons'

interface WorkspaceDashboardProps {
  user: UserOut | null
  activeOrg: OrgOut | null
  onOpenSaved: () => void
  onOpenAuth: () => void
  onLoadIncident: (incidentDetail: any) => void
  onLoadSample?: () => void
  refreshTrigger: number
}

interface StatsData {
  total_incidents: number
  total_errors: number
  total_anomalies: number
  by_format: Record<string, number>
  recent_incidents: any[]
}

export function WorkspaceDashboard({
  user,
  activeOrg,
  onOpenSaved,
  onOpenAuth,
  onLoadIncident,
  onLoadSample,
  refreshTrigger,
}: WorkspaceDashboardProps) {
  const [stats, setStats] = useState<StatsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [openingId, setOpeningId] = useState<string | null>(null)

  const orgId = activeOrg?.id
  const hasUser = !!user

  useEffect(() => {
    let active = true
    if (!hasUser) {
      return
    }

    const loadStats = async () => {
      setLoading(true)
      setError(null)
      try {
        const data = await api.incidents.stats(orgId)
        if (active) setStats(data)
      } catch (err: any) {
        if (!active) return
        if (err instanceof APIError) {
          setError(err.message)
        } else {
          setError('Could not load your workspace statistics. Please try refreshing.')
        }
      } finally {
        if (active) setLoading(false)
      }
    }

    loadStats()

    return () => {
      active = false
    }
  }, [hasUser, orgId, refreshTrigger])

  const handleOpenRecent = async (id: string) => {
    setOpeningId(id)
    try {
      const detail = await api.incidents.get(id)
      onLoadIncident(detail)
    } catch (err: any) {
      alert(err instanceof APIError ? err.message : 'Could not open incident.')
    } finally {
      setOpeningId(null)
    }
  }

  // Guest / Demo State
  if (!user) {
    return (
      <div className="card" style={{
        marginBottom: 20,
        padding: '14px 18px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 12,
        background: 'linear-gradient(135deg, rgba(34, 211, 238, 0.05) 0%, rgba(168, 85, 247, 0.03) 100%)',
        border: '1px solid var(--border-accent)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 'var(--radius)',
            background: 'var(--cyan-dim)', display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: 'var(--cyan)', border: '1px solid var(--cyan-border)',
            flexShrink: 0
          }}>
            <ShieldIcon size={20} color="var(--cyan)" />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
              Welcome to TraceGuard AI
              <span className="badge badge-cyan" style={{ fontSize: 10 }}>Analysis Sandbox</span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
              Quickly diagnose application crashes, cascading outages, and errors with clickable source-line proof.
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {onLoadSample && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={onLoadSample}
              style={{ padding: '6px 12px' }}
            >
              <ZapIcon size={14} color="var(--cyan)" />
              <span>Try Sample Incident</span>
            </button>
          )}
          <button
            className="btn btn-primary btn-sm"
            onClick={onOpenAuth}
            style={{ padding: '6px 14px' }}
          >
            <UserIcon size={14} />
            <span>Sign In to Save History</span>
          </button>
        </div>
      </div>
    )
  }

  // Authenticated Workspace State
  return (
    <div className="card fade-in" style={{ marginBottom: 20 }}>
      {/* Workspace Bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        paddingBottom: 14, borderBottom: '1px solid var(--border)', flexWrap: 'wrap', gap: 12,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 'var(--radius)',
            background: 'var(--bg-elevated)', display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: 'var(--cyan)', border: '1px solid var(--border)'
          }}>
            <ActivityIcon size={18} color="var(--cyan)" />
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-heading)', display: 'flex', alignItems: 'center', gap: 8 }}>
              {activeOrg?.name || 'Workspace'}
              <span className="badge badge-neutral" style={{ fontSize: 10, textTransform: 'uppercase' }}>
                {activeOrg?.role || 'member'}
              </span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              Your team's saved investigations
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={onOpenSaved}
          >
            <FolderIcon size={14} color="var(--cyan)" />
            <span>Saved Investigations {stats ? `(${stats.total_incidents})` : ''}</span>
          </button>
        </div>
      </div>

      {error && (
        <div style={{ marginTop: 12, padding: '8px 12px', background: 'var(--error-bg)', border: '1px solid var(--error-border)', borderRadius: 'var(--radius-sm)', color: 'var(--error)', fontSize: 12 }}>
          {error}
        </div>
      )}

      {/* Metrics Row or Genuine Empty State */}
      {stats && stats.total_incidents === 0 ? (
        <div style={{
          marginTop: 14,
          padding: '16px 20px',
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 14,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 'var(--radius)',
              background: 'var(--cyan-dim)', display: 'flex', alignItems: 'center',
              justifyContent: 'center', color: 'var(--cyan)', border: '1px solid var(--cyan-border)',
              flexShrink: 0
            }}>
              <CheckCircleIcon size={20} color="var(--green)" />
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>
                Workspace Ready for Investigations
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>
                No saved investigations yet. Run an analysis below and click <strong>Save to Workspace</strong> to store your team's first investigation.
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div className="status-pill" style={{ fontSize: 11 }}>
              <span className="pulse-dot green" />
              <span style={{ color: 'var(--green)' }}>System Online</span>
            </div>
            {onLoadSample && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={onLoadSample}
              >
                <ZapIcon size={13} color="var(--cyan)" />
                <span>Try Sample</span>
              </button>
            )}
          </div>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: 10,
          marginTop: 14,
        }}>
          <div className="stat-cell">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
              <span className="stat-label">Saved Investigations</span>
              <FileTextIcon size={14} color="var(--text-muted)" />
            </div>
            <div className="stat-value" style={{ color: 'var(--cyan)' }}>
              {loading ? '…' : (stats?.total_incidents ?? 0)}
            </div>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Saved in your workspace</span>
          </div>

          <div className="stat-cell">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
              <span className="stat-label">Errors Found</span>
              <AlertTriangleIcon size={14} color="var(--error)" />
            </div>
            <div className="stat-value" style={{ color: 'var(--error)' }}>
              {loading ? '…' : (stats?.total_errors ?? 0)}
            </div>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Across your saved investigations</span>
          </div>

          <div className="stat-cell">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
              <span className="stat-label">Unusual Patterns</span>
              <ZapIcon size={14} color="var(--warn)" />
            </div>
            <div className="stat-value" style={{ color: 'var(--warn)' }}>
              {loading ? '…' : (stats?.total_anomalies ?? 0)}
            </div>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Patterns identified</span>
          </div>

          <div className="stat-cell">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
              <span className="stat-label">System Status</span>
              <CheckCircleIcon size={14} color="var(--green)" />
            </div>
            <div className="stat-value" style={{ color: 'var(--green)', fontSize: 18 }}>
              Online & Ready
            </div>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Ready to check your logs</span>
          </div>
        </div>
      )}

      {/* Recent Incidents Bar if any */}
      {stats && stats.recent_incidents && stats.recent_incidents.length > 0 && (
        <div style={{ marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 8 }}>
            Recently Saved Investigations
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {stats.recent_incidents.slice(0, 3).map(inc => (
              <button
                key={inc.id}
                className="btn btn-ghost btn-sm"
                onClick={() => handleOpenRecent(inc.id)}
                disabled={openingId === inc.id}
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 11,
                  padding: '5px 10px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <FileTextIcon size={12} color="var(--cyan)" />
                <span style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {inc.title}
                </span>
                <span className="badge badge-error" style={{ fontSize: 10, padding: '1px 5px' }}>
                  {inc.error_count} err
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
