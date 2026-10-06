const API_ROOT = import.meta.env.VITE_API_URL || ''
let desktopApiRoot: Promise<string> | undefined

function apiRoot(): Promise<string> {
  if (API_ROOT) return Promise.resolve(API_ROOT)
  if (!window.stockwiseDesktop) return Promise.resolve('')
  desktopApiRoot ??= window.stockwiseDesktop.getApiBaseUrl()
  return desktopApiRoot
}

let inMemoryToken: string | null = null
let refreshRequest: Promise<string | null | false> | null = null

export const getToken = (): string | null => {
  return inMemoryToken
}

export const setSession = (access: string) => {
  inMemoryToken = access
}

export const clearSession = () => {
  inMemoryToken = null
}

async function send(path: string, init: RequestInit, token = getToken()): Promise<Response> {
  const headers = new Headers(init.headers)
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  try {
    const root = await apiRoot()
    return await fetch(`${root}${path}`, {
      ...init,
      headers,
      credentials: 'include' // Always transmit HTTP cookies in real time (Zero localStorage)
    })
  } catch {
    throw new Error('Unable to reach the server. Please check that the backend is running and try again.')
  }
}

async function refreshAccessToken(): Promise<string | null | false> {
  if (!refreshRequest) {
    refreshRequest = (async () => {
      let response: Response
      try {
        const root = await apiRoot()
        response = await fetch(`${root}/api/auth/refresh`, { method: 'POST', credentials: 'include' })
      } catch {
        return false
      }
      if (!response.ok) return response.status === 401 ? null : false
      const payload = await response.json().catch(() => null)
      if (typeof payload?.access_token !== 'string') return null
      setSession(payload.access_token)
      return payload.access_token
    })().finally(() => { refreshRequest = null })
  }
  return refreshRequest
}

export async function apiResponse(path: string, init: RequestInit = {}): Promise<Response> {
  let response = await send(path, init)
  const authRoute = ['/api/auth/login', '/api/auth/refresh', '/api/auth/logout'].includes(path)
  if (response.status === 401 && !authRoute) {
    const refreshedToken = await refreshAccessToken()
    if (typeof refreshedToken === 'string') {
      response = await send(path, init, refreshedToken)
    } else if (refreshedToken === null) {
      clearSession()
      window.dispatchEvent(new Event('session-expired'))
    }
  }

  if (!response.ok) {
    const text = await response.text().catch(() => '')
    let payload: any = null
    try {
      payload = JSON.parse(text)
    } catch {
      payload = null
    }
    const message =
      payload?.error?.message ||
      (typeof payload?.error === 'string' ? payload.error : null) ||
      payload?.detail ||
      payload?.message ||
      (text && !text.includes('<html') && text.length < 250 ? text : null)

    const fallback =
      response.status === 429
        ? 'Too many sign-in attempts. Wait a minute, then try again.'
        : response.status === 500 || response.status === 503
        ? 'Database connection error. Please verify DATABASE_URL is configured in your Vercel Project Settings.'
        : `The request failed (${response.status}). Please try again.`

    throw new Error(message || fallback)
  }
  return response
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiResponse(path, init)
  if (response.status === 204) return undefined as T
  const payload = await response.json().catch(() => null)
  return payload as T
}
