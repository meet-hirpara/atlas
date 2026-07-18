import { apiFetch } from './utils/apiFetch'
export interface ConnectionStatus {
  provider: string
  connected: boolean
  label: string
  connected_at: string | null
}

export interface ProviderField {
  key: string
  label: string
  type: 'text' | 'password' | 'email' | 'url'
  placeholder: string
  required: boolean
  hint: string
  default: string
}

export interface ProviderCatalogItem {
  id: string
  name: string
  category: string
  category_label: string
  description: string
  color: string
  tool_summary: string
  fields: ProviderField[]
  auth_type: 'api_key' | 'oauth' | 'manual_token' | 'none'
  status: 'available' | 'coming_soon' | 'oauth_required' | 'manual_token'
  setup_help: string
  docs_url: string
  capabilities: string[]
}

const API = '/api/connections'

export async function fetchConnections(): Promise<ConnectionStatus[]> {
  const res = await apiFetch(API)
  if (!res.ok) throw new Error('Failed to load connections')
  return res.json()
}

export async function fetchProviders(): Promise<ProviderCatalogItem[]> {
  const res = await apiFetch(`${API}/providers`)
  if (!res.ok) throw new Error('Failed to load providers — is the backend running on port 8000?')
  const data = await res.json()
  const items = (data.providers ?? []) as ProviderCatalogItem[]
  return items.map((p) => ({
    ...p,
    capabilities: p.capabilities ?? [],
    fields: p.fields ?? [],
  }))
}

export async function connectProvider(
  provider: string,
  credentials: Record<string, string>,
): Promise<ConnectionStatus[]> {
  const res = await apiFetch(`${API}/${provider}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credentials }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const detail = err.detail
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join('; ') || 'Connection failed'
          : 'Connection failed'
    throw new Error(message)
  }
  return res.json()
}

export async function disconnectProvider(provider: string): Promise<ConnectionStatus[]> {
  const res = await apiFetch(`${API}/${provider}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to disconnect')
  return res.json()
}
