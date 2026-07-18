export interface McpEnvField {
  key: string
  label: string
  secret?: boolean
  required?: boolean
  hint?: string
}

import { authHeaders } from './utils/localAuth'

export interface McpPreset {
  id: string
  name: string
  description: string
  color: string
  transport: 'stdio' | 'sse'
  command: string
  args: string[]
  url: string
  setup_steps: string[]
  env_fields?: McpEnvField[]
  notes?: string
}

export interface McpServer {
  id: string
  name: string
  preset: string
  transport: string
  command: string
  args: string[]
  url: string
  env: Record<string, string>
  enabled: boolean
  tool_count: number
  connected_at: string | null
  test_message?: string
  updated?: boolean
  has_cached_tools?: boolean
}

const API = '/api/mcp'

export async function fetchMcpPresets(): Promise<McpPreset[]> {
  const res = await fetch(`${API}/presets`)
  if (!res.ok) throw new Error('Failed to load MCP presets — is the backend running on port 8000?')
  const data = await res.json()
  return (data.presets ?? []) as McpPreset[]
}

export async function fetchMcpServers(): Promise<McpServer[]> {
  const res = await fetch(`${API}/servers`)
  if (!res.ok) throw new Error('Failed to load MCP servers')
  const data = await res.json()
  return data.servers as McpServer[]
}

export async function addMcpServer(payload: {
  name: string
  preset: string
  transport: string
  command: string
  args: string[]
  url: string
  env?: Record<string, string>
}): Promise<McpServer> {
  const res = await fetch(`${API}/servers`, {
    method: 'POST',
    headers: await authHeaders(),
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to connect MCP server')
  }
  return res.json()
}

export async function deleteMcpServer(id: string): Promise<McpServer[]> {
  const res = await fetch(`${API}/servers/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to remove MCP server')
  const data = await res.json()
  return data.servers as McpServer[]
}

export async function testMcpServer(id: string): Promise<{ message: string; tool_count: number }> {
  const res = await fetch(`${API}/servers/${id}/test`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'MCP test failed')
  }
  return res.json()
}

export async function toggleMcpServer(id: string, enabled: boolean): Promise<McpServer> {
  const res = await fetch(`${API}/servers/${id}?enabled=${enabled}`, { method: 'PATCH' })
  if (!res.ok) throw new Error('Failed to update MCP server')
  return res.json()
}

export interface McpTool {
  name: string
  description: string
}

export async function fetchMcpServerTools(id: string): Promise<McpTool[]> {
  const res = await fetch(`${API}/servers/${id}/tools`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to load MCP tools')
  }
  const data = await res.json()
  return data.tools as McpTool[]
}
