/**
 * Centralized API Client for TraceGuard AI
 *
 * Handles:
 * - Base URL configuration (uses Vite proxy /api or VITE_API_BASE_URL)
 * - HttpOnly cookie credentials + Bearer token fallback from localStorage
 * - Structured HTTP error parsing (401, 403, 404, 413, 422, 500)
 * - Type-safe endpoints for Auth, Incidents, Analysis, and Health
 */

export class APIError extends Error {
  public status: number
  public detail?: any

  constructor(status: number, message: string, detail?: any) {
    super(message)
    this.name = 'APIError'
    this.status = status
    this.detail = detail
  }
}

const API_BASE = (import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`
  const headers = new Headers(options.headers || {})

  // Attach token if present in localStorage (backup for cross-origin or non-cookie clients)
  const token = localStorage.getItem('traceguard_token')
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  // Set default JSON Content-Type if sending a body that isn't FormData
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const config: RequestInit = {
    ...options,
    headers,
    credentials: 'include', // Send cookies for secure HttpOnly session support
  }

  let res: Response
  try {
    res = await fetch(url, config)
  } catch (netErr: any) {
    const hint = API_BASE
      ? `Could not reach ${url}. If using Render free tier, the service may be waking up (cold start ~30-50s) — please retry in a moment.`
      : `Could not reach ${url}. Is the backend running on port 8010?`
    throw new APIError(0, `Network connection failed. ${hint}`, netErr)
  }

  // Parse response
  const contentType = res.headers.get('content-type') || ''
  let responseData: any = null
  if (contentType.includes('application/json')) {
    try {
      responseData = await res.json()
    } catch {
      responseData = null
    }
  } else {
    try {
      responseData = await res.text()
    } catch {
      responseData = null
    }
  }

  if (!res.ok) {
    let message = 'An unexpected server error occurred.'
    if (responseData && typeof responseData === 'object' && responseData.detail) {
      if (typeof responseData.detail === 'string') {
        message = responseData.detail
      } else if (Array.isArray(responseData.detail)) {
        message = responseData.detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ')
      }
    } else if (typeof responseData === 'string' && responseData.trim()) {
      message = responseData
    } else {
      switch (res.status) {
        case 400:
          message = 'Bad request. Please verify your input.'
          break
        case 401:
          message = 'Authentication required or session expired. Please sign in.'
          break
        case 403:
          message = 'Access forbidden. You do not have permissions for this resource.'
          break
        case 404:
          message = 'Resource not found.'
          break
        case 413:
          message = 'Payload too large. Log input exceeds 5 MB limit.'
          break
        case 422:
          message = 'Validation error. Please verify the submitted data format.'
          break
        case 429:
          message = 'Too many requests. Please wait a moment before trying again.'
          break
        case 500:
        case 502:
        case 503:
          message = 'Backend service error. Please check server logs.'
          break
      }
    }

    throw new APIError(res.status, message, responseData)
  }

  return responseData as T
}

// ============================================================================
// API Endpoints
// ============================================================================

export const api = {
  auth: {
    async signup(payload: { email: string; password: string; full_name?: string; org_name?: string }) {
      return request<any>('/api/auth/signup', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    },

    async login(payload: { email: string; password: string }) {
      return request<any>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    },

    async logout() {
      try {
        await request<any>('/api/auth/logout', { method: 'POST' })
      } finally {
        localStorage.removeItem('traceguard_token')
      }
    },

    async me() {
      return request<any>('/api/auth/me', { method: 'GET' })
    },
  },

  incidents: {
    async list(params?: {
      org_id?: string
      search?: string
      format?: string
      sort?: 'asc' | 'desc'
      limit?: number
      offset?: number
    }) {
      const searchParams = new URLSearchParams()
      if (params?.org_id) searchParams.append('org_id', params.org_id)
      if (params?.search) searchParams.append('search', params.search)
      if (params?.format) searchParams.append('format', params.format)
      if (params?.sort) searchParams.append('sort', params.sort)
      if (params?.limit !== undefined) searchParams.append('limit', String(params.limit))
      if (params?.offset !== undefined) searchParams.append('offset', String(params.offset))

      const queryStr = searchParams.toString() ? `?${searchParams.toString()}` : ''
      return request<any[]>(`/api/incidents${queryStr}`, { method: 'GET' })
    },

    async stats(org_id?: string) {
      const queryStr = org_id ? `?org_id=${encodeURIComponent(org_id)}` : ''
      return request<{
        total_incidents: number
        total_errors: number
        total_anomalies: number
        by_format: Record<string, number>
        recent_incidents: any[]
      }>(`/api/incidents/stats${queryStr}`, { method: 'GET' })
    },

    async get(id: string) {
      return request<any>(`/api/incidents/${encodeURIComponent(id)}`, { method: 'GET' })
    },

    async create(payload: {
      organization_id?: string
      title: string
      filename: string
      file_format: string
      summary_json: any
      anomalies_json?: any[]
      hypotheses_json?: any[]
      events_json?: any[]
      raw_content_preview?: string
      investigation_report_json?: any
      engine_version?: string
      ai_was_used?: boolean
    }) {
      return request<any>('/api/incidents', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
    },

    async update(id: string, payload: { title?: string; raw_content_preview?: string }) {
      return request<any>(`/api/incidents/${encodeURIComponent(id)}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })
    },

    async delete(id: string) {
      return request<any>(`/api/incidents/${encodeURIComponent(id)}`, {
        method: 'DELETE',
      })
    },
  },

  analysis: {
    async analyze(content: string, filename: string, use_ai: boolean = false) {
      return request<any>('/api/analyze', {
        method: 'POST',
        body: JSON.stringify({ content, filename, use_ai }),
      })
    },

    async analyzeFile(file: File, use_ai: boolean = false) {
      const formData = new FormData()
      formData.append('file', file)
      const queryStr = use_ai ? '?use_ai=true' : ''
      return request<any>(`/api/analyze${queryStr}`, {
        method: 'POST',
        body: formData,
      })
    },

    async getSample() {
      return request<{ content: string; filename: string }>('/api/sample', { method: 'GET' })
    },
  },

  health: {
    async check() {
      return request<{ status: string }>('/api/health', { method: 'GET' })
    },

    async checkDb() {
      return request<{ status: string; backend?: string; host?: string; port?: number; error?: string }>('/api/health/db', { method: 'GET' })
    },
  },
}
