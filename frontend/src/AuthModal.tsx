import { useState, useEffect } from 'react'
import { api, APIError } from './api/client'
import { AlertTriangleIcon, LockIcon, ShieldIcon, XIcon } from './components/Icons'

interface AuthModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: (userData: any) => void
  initialMode?: 'login' | 'signup'
}

export function AuthModal({ isOpen, onClose, onSuccess, initialMode = 'login' }: AuthModalProps) {
  const [mode, setMode] = useState<'login' | 'signup'>(initialMode)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [orgName, setOrgName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [prevInitialMode, setPrevInitialMode] = useState(initialMode)
  if (prevInitialMode !== initialMode) {
    setPrevInitialMode(initialMode)
    setMode(initialMode)
  }

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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const data = mode === 'login'
        ? await api.auth.login({ email, password })
        : await api.auth.signup({
            email,
            password,
            full_name: fullName.trim() || undefined,
            org_name: orgName.trim() || undefined,
          })

      // Store token in localStorage for backup / bearer header support
      if (data.access_token) {
        localStorage.setItem('traceguard_token', data.access_token)
      }

      onSuccess(data)
      onClose()
    } catch (err: any) {
      if (err instanceof APIError) {
        setError(err.message)
      } else {
        setError(err.message || 'An unexpected error occurred.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true" aria-labelledby="auth-modal-title">
      <div
        className="modal-dialog fade-in"
        style={{ maxWidth: 420 }}
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
              <LockIcon size={16} color="var(--cyan)" />
            </div>
            <div>
              <h3 id="auth-modal-title" style={{ fontSize: 15, fontWeight: 600 }}>
                {mode === 'login' ? 'Sign In to Workspace' : 'Create Workspace Account'}
              </h3>
              <p style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                {mode === 'login' ? 'Access your team\'s saved investigations' : 'Initialize a secure, isolated workspace'}
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

        {/* Tab Switcher */}
        <div style={{ padding: '16px 20px 0' }}>
          <div style={{
            display: 'flex',
            background: 'var(--bg-base)',
            borderRadius: 'var(--radius)',
            padding: 3,
            border: '1px solid var(--border)',
            gap: 4,
          }}>
            <button
              type="button"
              className="btn"
              onClick={() => { setMode('login'); setError(null) }}
              style={{
                flex: 1,
                fontSize: 12,
                padding: '6px 12px',
                background: mode === 'login' ? 'var(--bg-elevated)' : 'transparent',
                color: mode === 'login' ? 'var(--cyan)' : 'var(--text-muted)',
                borderColor: mode === 'login' ? 'var(--cyan-border)' : 'transparent',
              }}
            >
              Sign In
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => { setMode('signup'); setError(null) }}
              style={{
                flex: 1,
                fontSize: 12,
                padding: '6px 12px',
                background: mode === 'signup' ? 'var(--bg-elevated)' : 'transparent',
                color: mode === 'signup' ? 'var(--cyan)' : 'var(--text-muted)',
                borderColor: mode === 'signup' ? 'var(--cyan-border)' : 'transparent',
              }}
            >
              Register Workspace
            </button>
          </div>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} style={{ padding: 20 }}>
          {error && (
            <div style={{
              marginBottom: 16,
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

          {mode === 'signup' && (
            <>
              <div style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Full Name
                </label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g. Alex Morgan"
                  value={fullName}
                  onChange={e => setFullName(e.target.value)}
                  autoFocus
                />
              </div>

              <div style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  Workspace / Team Name (Optional)
                </label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g. Reliability Engineering"
                  value={orgName}
                  onChange={e => setOrgName(e.target.value)}
                />
              </div>
            </>
          )}

          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>
              Email Address
            </label>
            <input
              type="email"
              className="input"
              placeholder="sre@company.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoFocus={mode === 'login'}
            />
          </div>

          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>
              Password
            </label>
            <input
              type="password"
              className="input"
              placeholder={mode === 'signup' ? 'Minimum 8 characters' : 'Enter password'}
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              minLength={8}
            />
            {mode === 'signup' && (
              <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                Protected with Argon2id cryptographic password hashing.
              </p>
            )}
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-lg"
            disabled={loading}
            style={{ width: '100%' }}
          >
            {loading ? (
              <>
                <span className="spinner" style={{ width: 14, height: 14 }} />
                <span>{mode === 'login' ? 'Authenticating…' : 'Creating Account…'}</span>
              </>
            ) : (
              <span>{mode === 'login' ? 'Sign In' : 'Create Workspace Account'}</span>
            )}
          </button>

          <div style={{ marginTop: 14, textAlign: 'center', fontSize: 11, color: 'var(--text-muted)' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <ShieldIcon size={12} color="var(--green)" />
              Workspace-isolated data security & encrypted sessions
            </span>
          </div>
        </form>
      </div>
    </div>
  )
}
