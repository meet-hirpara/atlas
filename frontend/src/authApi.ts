/** User account auth (JWT) — separate from localhost X-Atlas-Token. */

import { clearLocalAuthToken } from './utils/localAuth'

const TOKEN_KEY = 'atlas-jwt'
const USER_KEY = 'atlas-user'

export interface AuthUser {
  id: string
  email: string
  role: 'user' | 'admin' | string
  created_at: string
}

export interface AuthStatus {
  has_users: boolean
  allow_register: boolean
}

export interface AuthResponse {
  token: string
  user: AuthUser
}

export interface AdminUser {
  id: string
  email: string
  role: string
  created_at: string
  session_count: number
}

export interface AdminHealth {
  status: string
  users: number
  sessions: number
  messages: number
  connections: number
  mcp_servers: number
  time: string
}

type Listener = () => void
const listeners = new Set<Listener>()

function notify() {
  listeners.forEach((fn) => fn())
}

export function subscribeAuth(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function getAccessToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function getStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    if (!raw) return null
    return JSON.parse(raw) as AuthUser
  } catch {
    return null
  }
}

export function setSession(token: string, user: AuthUser) {
  try {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  } catch {
    /* ignore */
  }
  notify()
}

export function clearSession() {
  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  } catch {
    /* ignore */
  }
  clearLocalAuthToken()
  notify()
}

export async function userAuthHeaders(extra?: HeadersInit): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  const token = getAccessToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (extra) {
    const h = new Headers(extra)
    h.forEach((value, key) => {
      headers[key] = value
    })
  }
  return headers
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (typeof data?.detail === 'string') return data.detail
    if (Array.isArray(data?.detail)) {
      return data.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join(', ')
    }
  } catch {
    /* ignore */
  }
  return `Request failed (${res.status})`
}

export async function fetchAuthStatus(): Promise<AuthStatus> {
  const res = await fetch('/api/auth/status')
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function register(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  const data = (await res.json()) as AuthResponse
  setSession(data.token, data.user)
  return data
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  const data = (await res.json()) as AuthResponse
  setSession(data.token, data.user)
  return data
}

export async function logout(): Promise<void> {
  try {
    await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'include',
      headers: await userAuthHeaders(),
    })
  } catch {
    /* ignore */
  }
  clearSession()
}

export async function fetchMe(): Promise<AuthUser> {
  const res = await fetch('/api/auth/me', {
    credentials: 'include',
    headers: await userAuthHeaders(),
  })
  if (!res.ok) {
    clearSession()
    throw new Error(await parseError(res))
  }
  const user = (await res.json()) as AuthUser
  const token = getAccessToken()
  if (token) setSession(token, user)
  return user
}

export async function fetchAdminUsers(): Promise<AdminUser[]> {
  const res = await fetch('/api/admin/users', {
    credentials: 'include',
    headers: await userAuthHeaders(),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function updateUserRole(userId: string, role: 'user' | 'admin'): Promise<AdminUser> {
  const res = await fetch(`/api/admin/users/${userId}/role`, {
    method: 'PATCH',
    credentials: 'include',
    headers: await userAuthHeaders(),
    body: JSON.stringify({ role }),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function fetchAdminHealth(): Promise<AdminHealth> {
  const res = await fetch('/api/admin/health', {
    credentials: 'include',
    headers: await userAuthHeaders(),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export type StorageEngine = 'sqlite' | 'postgresql' | 'mysql' | 'mongodb' | 'redis'

export interface StorageCredentials {
  path?: string
  host?: string
  port?: number
  database?: string
  username?: string
  password?: string
  url?: string
  ssl?: boolean
}

export interface StorageBackendPublic {
  engine: StorageEngine
  enabled: boolean
  credentials: StorageCredentials
}

export interface StoragePlacement {
  purpose: string
  description: string
  engine: string
  location_hint: string
}

export interface StorageStatus {
  primary: StorageBackendPublic
  chat_cache: StorageBackendPublic | null
  placement: StoragePlacement[]
  env_database_url: string
  warning: string
  engines_available: Array<{ engine: string; driver_installed: boolean; hint?: string }>
}

export interface StorageTestResult {
  ok: boolean
  engine: StorageEngine
  message: string
  latency_ms?: number | null
}

export async function fetchStorageStatus(): Promise<StorageStatus> {
  const res = await fetch('/api/admin/storage', {
    credentials: 'include',
    headers: await userAuthHeaders(),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function testStorageConnection(body: {
  engine: StorageEngine
  credentials: StorageCredentials
  purpose?: 'primary' | 'chat_cache'
}): Promise<StorageTestResult> {
  const res = await fetch('/api/admin/storage/test', {
    method: 'POST',
    credentials: 'include',
    headers: await userAuthHeaders(),
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}

export async function applyStorageConfig(body: {
  primary: { engine: StorageEngine; credentials: StorageCredentials; enabled?: boolean }
  chat_cache?: { engine: StorageEngine; credentials: StorageCredentials; enabled?: boolean } | null
  confirm_destructive: boolean
  acknowledge_data_loss: boolean
}): Promise<StorageStatus> {
  const res = await fetch('/api/admin/storage/apply', {
    method: 'POST',
    credentials: 'include',
    headers: await userAuthHeaders(),
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json()
}
