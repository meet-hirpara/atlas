/** Local auth token for sensitive Atlas APIs (code run, MCP connect). */

const STORAGE_KEY = 'atlas-local-auth-token'
let memoryToken: string | null = null
let fetchPromise: Promise<string | null> | null = null

export function clearLocalAuthToken() {
  memoryToken = null
  fetchPromise = null
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    /* ignore */
  }
}

export async function ensureLocalAuthToken(): Promise<string | null> {
  if (memoryToken) return memoryToken
  try {
    const cached = sessionStorage.getItem(STORAGE_KEY)
    if (cached) {
      memoryToken = cached
      return cached
    }
  } catch {
    /* sessionStorage unavailable */
  }

  if (!fetchPromise) {
    fetchPromise = (async () => {
      try {
        const res = await fetch('/api/auth/token')
        if (!res.ok) return null
        const data = (await res.json()) as { token?: string }
        const token = (data.token || '').trim()
        if (!token) return null
        memoryToken = token
        try {
          sessionStorage.setItem(STORAGE_KEY, token)
        } catch {
          /* ignore */
        }
        return token
      } catch {
        return null
      } finally {
        fetchPromise = null
      }
    })()
  }
  return fetchPromise
}

export async function authHeaders(extra?: HeadersInit): Promise<Record<string, string>> {
  const { getAccessToken } = await import('../authApi')
  const token = await ensureLocalAuthToken()
  const base: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  const jwt = getAccessToken()
  if (jwt) base.Authorization = `Bearer ${jwt}`
  if (token) base['X-Atlas-Token'] = token
  if (extra) {
    const h = new Headers(extra)
    h.forEach((value, key) => {
      base[key] = value
    })
  }
  return base
}
