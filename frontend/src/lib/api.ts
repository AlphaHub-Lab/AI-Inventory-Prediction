const API_ROOT = import.meta.env.VITE_API_URL || ''
let desktopApiRoot: Promise<string> | undefined

function apiRoot(): Promise<string> {
  if (API_ROOT) return Promise.resolve(API_ROOT)
  if (!window.stockwiseDesktop) return Promise.resolve('')
  desktopApiRoot ??= window.stockwiseDesktop.getApiBaseUrl()
  return desktopApiRoot
}

let inMemoryToken: string | null = null

export const getToken = (): string | null => {
  return inMemoryToken
}

export const setSession = (access: string) => {
  inMemoryToken = access
}

export const clearSession = () => {
  inMemoryToken = null
}

export async function apiResponse(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  const token = getToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(`${await apiRoot()}${path}`, {
      ...init,
      headers,
      credentials: 'include' // Always transmit HTTP cookies in real time (Zero localStorage)
    })
  } catch {
    throw new Error('Unable to reach the server. Please check that the backend is running and try again.')
  }

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    const message = payload?.error?.message || (typeof payload?.error === 'string' ? payload.error : null) || payload?.detail || payload?.message
    throw new Error(message || (response.status === 429 ? 'Too many sign-in attempts. Wait a minute, then try again.' : `The request failed (${response.status}). Please try again.`))
  }
  return response
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiResponse(path, init)
  if (response.status === 204) return undefined as T
  const payload = await response.json().catch(() => null)
  return payload as T
}
