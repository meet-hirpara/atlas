import { getAccessToken } from '../authApi'

/** Authenticated fetch for Atlas APIs (JWT + credentials). */
export function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  const jwt = getAccessToken()
  if (jwt) headers.set('Authorization', `Bearer ${jwt}`)
  if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  return fetch(input, { ...init, headers, credentials: 'include' })
}
