import { useState, useEffect, useCallback } from 'react'
import { api, APIError } from './api/client'
import {
  AlertTriangleIcon,
  ClockIcon,
  FileTextIcon,
  FolderIcon,
  SearchIcon,
  TrashIcon,
  XIcon,
  ZapIcon,
} from './components/Icons'

export interface SavedIncidentItem {
  id: string
  organization_id: string
  created_by_user_id: string | null
  title: string
  filename: string
  file_format: string
  total_lines: number
  error_count: number
  anomalies_flagged: number
  created_at: string
}

interface SavedIncidentsModalProps {
  isOpen: boolean
  onClose: () => void
  onLoadIncident: (incidentDetail: any) => void
}

export function SavedIncidentsModal({ isOpen, onClose, onLoadIncident }: SavedIncidentsModalProps) {
  const [incidents, setIncidents] = useState<SavedIncidentItem[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingId, setLoadingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [formatFilter, setFormatFilter] = useState('')

  const fetchIncidents = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.incidents.list({
        search: searchTerm.trim() || undefined,
        format: formatFilter || undefined,
      })
      setIncidents(data)
    } catch (err: any) {
      if (err instanceof APIError) {
        setError(err.message)
      } else {
        setError(err.message || 'Could not fetch saved incidents.')
      }
    } finally {
      setLoading(false)
    }
  }, [searchTerm, formatFilter])

  useEffect(() => {
    if (!isOpen) return
    const timer = setTimeout(() => {
      fetchIncidents()
    }, 200)
    return () => clearTimeout(timer)
  }, [isOpen, fetchIncidents])

  // Handle escape key
  useEffect(() => {
    if (!isOpen) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const handleSelect = async (id: string) => {
    setLoadingId(id)
    setError(null)
    try {
      const detail = await api.incidents.get(id)
      onLoadIncident(detail)
      onClose()
    } catch (err: any) {
      setError(err instanceof APIError ? err.message : 'Failed to open incident.')
    } finally {
      setLoadingId(null)
    }
  }

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!window.confirm('Delete this investigation record from your workspace history? This action cannot be undone.')) return

    try {
      await api.incidents.delete(id)
      setIncidents(prev => prev.filter(i => i.id !== id))
    } catch (err: any) {
      setError(err instanceof APIError ? err.message : 'Delete operation failed.')
    }
  }

  const formatDate = (iso: string) => {
    try {
      const d = new Date(iso)
      return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) +
        ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
    } catch {
      return iso
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="saved-modal-title">
      <div
        className="modal-dialog fade-in"
        style={{ maxWidth: 760 }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 32, height: 32, borderRadius: 'var(--radius)',
              background: 'var(--cyan-dim)', display: 'flex', alignItems: 'center',
              justifyContent: 'center', color: 'var(--cyan)'
            }}>
              <FolderIcon size={18} color="var(--cyan)" />
            </div>
            <div>
              <h3 id="saved-modal-title" style={{ fontSize: 15, fontWeight: 600 }}>
                Saved Investigations
              </h3>
              <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Browse, reopen, and filter historical investigations in your workspace
              </p>
            </div>
          </div>
          <button
            className="btn btn-ghost"
            onClick={onClose}
            aria-label="Close dialog"
            style={{ padding: '6px' }}
          >
            <XIcon size={18} />
          </button>
        </div>

        {/* Search & Filter Bar */}
        <div style={{
          padding: '12px 20px',
          background: 'var(--bg-card)',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          gap: 10,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}>
          <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
            <SearchIcon
              size={15}
              color="var(--text-muted)"
              style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)' }}
            />
            <input
              type="text"
              className="input"
              placeholder="Search by title or log filename…"
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              style={{ paddingLeft: 32 }}
              autoFocus
            />
          </div>

          <select
            className="input"
            value={formatFilter}
            onChange={e => setFormatFilter(e.target.value)}
            style={{ width: 'auto', minWidth: 150 }}
            aria-label="Filter by log format"
          >
            <option value="">All Log Formats</option>
            <option value="json_application">JSON Application Logs</option>
            <option value="plaintext">Python / Java Stack Traces</option>
            <option value="nginx_apache">Nginx / Apache Logs</option>
          </select>

          <span style={{ fontSize: 12, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
            {incidents.length} {incidents.length === 1 ? 'investigation' : 'investigations'}
          </span>
        </div>

        {/* Content Body */}
        <div className="modal-body" style={{ maxHeight: '60vh' }}>
          {error && (
            <div style={{
              marginBottom: 14,
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
              <span>{error}</span>
            </div>
          )}

          {loading ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
              <div className="spinner" style={{ width: 24, height: 24, marginBottom: 12 }} />
              <div>Loading saved investigations…</div>
            </div>
          ) : incidents.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center' }}>
              <div style={{
                width: 44, height: 44, borderRadius: 'var(--radius-full)',
                background: 'var(--bg-elevated)', display: 'flex', alignItems: 'center',
                justifyContent: 'center', margin: '0 auto 12px', color: 'var(--text-muted)'
              }}>
                <SearchIcon size={20} />
              </div>
              <h4 style={{ fontSize: 14, marginBottom: 4 }}>No investigations found</h4>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', maxWidth: 360, margin: '0 auto' }}>
                {searchTerm || formatFilter
                  ? 'No investigations match your active search or format filter.'
                  : 'Save investigations from the main workspace to build your incident history.'}
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {incidents.map(inc => (
                <div
                  key={inc.id}
                  onClick={() => handleSelect(inc.id)}
                  style={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius)',
                    padding: '12px 16px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 14,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.borderColor = 'var(--cyan-border)'
                    e.currentTarget.style.background = 'var(--bg-elevated)'
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.borderColor = 'var(--border)'
                    e.currentTarget.style.background = 'var(--bg-card)'
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-heading)' }}>
                        {inc.title}
                      </span>
                      <span className="badge badge-neutral" style={{ fontSize: 10 }}>
                        {inc.file_format === 'json_application'
                          ? 'JSON Log'
                          : inc.file_format === 'plaintext'
                          ? 'Stack Traces'
                          : inc.file_format === 'nginx_apache'
                          ? 'Web-server Log'
                          : inc.file_format}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: 'var(--text-muted)', flexWrap: 'wrap' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <FileTextIcon size={12} />
                        {inc.filename}
                      </span>
                      <span>·</span>
                      <span>{inc.total_lines} lines</span>
                      <span>·</span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <ClockIcon size={12} />
                        {formatDate(inc.created_at)}
                      </span>
                    </div>
                  </div>

                  {/* Badges & Actions */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                    <span className="badge badge-error" style={{ fontSize: 11 }}>
                      {inc.error_count} {inc.error_count === 1 ? 'error' : 'errors'}
                    </span>
                    <span className="badge badge-warn" style={{ fontSize: 11 }}>
                      <ZapIcon size={11} />
                      {inc.anomalies_flagged} {inc.anomalies_flagged === 1 ? 'pattern' : 'patterns'}
                    </span>

                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={e => handleDelete(inc.id, e)}
                      title="Delete incident from workspace history"
                      aria-label="Delete incident"
                      style={{ color: 'var(--text-muted)', padding: '5px' }}
                    >
                      <TrashIcon size={14} />
                    </button>

                    <button
                      className="btn btn-outline btn-sm"
                      disabled={loadingId === inc.id}
                      style={{ fontSize: 11, padding: '4px 10px' }}
                    >
                      {loadingId === inc.id ? (
                        <>
                          <span className="spinner" style={{ width: 12, height: 12 }} />
                          <span>Opening…</span>
                        </>
                      ) : (
                        'Reopen'
                      )}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
