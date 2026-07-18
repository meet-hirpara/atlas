import { apiFetch } from './utils/apiFetch'
export interface GithubRepo {
  id: string
  url: string
  owner: string
  name: string
  branch: string
  status: 'pending' | 'indexing' | 'ready' | 'failed'
  error_message: string
  file_count: number
  chunk_count: number
  created_at: string
  indexed_at: string | null
}

export interface GraphNode {
  id: string
  label: string
  type: string
  file: string
}

export interface GraphEdge {
  source: string
  target: string
  type: string
}

export interface RepoGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GithubQueryResult {
  answer: string
  sources: { file_path: string; chunk_index: number; similarity: number }[]
  relevant: boolean
  repo: string
}

const API = '/api/github'

export async function fetchGithubRepos(): Promise<GithubRepo[]> {
  const res = await apiFetch(`${API}/repos`)
  if (!res.ok) throw new Error('Failed to load GitHub repos')
  return res.json()
}

export async function addGithubRepo(payload: {
  url: string
  token?: string
  branch?: string
}): Promise<GithubRepo> {
  const res = await apiFetch(`${API}/repos`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to add repository')
  }
  return res.json()
}

export async function deleteGithubRepo(id: string): Promise<void> {
  const res = await apiFetch(`${API}/repos/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to remove repository')
}

export async function fetchRepoGraph(id: string): Promise<RepoGraph> {
  const res = await apiFetch(`${API}/repos/${id}/graph`)
  if (!res.ok) throw new Error('Failed to load code graph')
  return res.json()
}

export async function queryGithubRepo(id: string, question: string): Promise<GithubQueryResult> {
  const res = await apiFetch(`${API}/repos/${id}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Query failed')
  }
  return res.json()
}

export function repoLabel(repo: GithubRepo): string {
  return `${repo.owner}/${repo.name}`
}

export function statusLabel(status: GithubRepo['status']): string {
  const map: Record<GithubRepo['status'], string> = {
    pending: 'Queued',
    indexing: 'Indexing…',
    ready: 'Ready',
    failed: 'Failed',
  }
  return map[status] ?? status
}
