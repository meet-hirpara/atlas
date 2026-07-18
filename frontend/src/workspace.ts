import { apiFetch } from './utils/apiFetch'

const API = '/api/workspace'

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `Request failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

export interface WorkspaceProject {
  id: string
  name: string
  description: string
  clientId?: string | null
  created_at: string
  updated_at: string
}

export interface Proposal {
  id: string
  title: string
  content: string
  platform: string
  session_id?: string | null
  job_id?: string | null
  created_at: string
  updated_at: string
}

export interface JobItem {
  id: string
  title: string
  source: string
  content: string
  fit_score?: number | null
  fit_notes: string
  status: string
  session_id?: string | null
  created_at: string
  updated_at: string
}

export interface CrmClient {
  id: string
  name: string
  notes: string
  rate: string
  last_contact?: string | null
  created_at: string
  updated_at: string
}

export interface AuditEntry {
  id: string
  kind: string
  action: string
  detail: string
  session_id?: string | null
  created_at: string
}

export interface Artifact {
  id: string
  session_id: string
  kind: string
  title: string
  content: string
  meta: string
  created_at: string
}

export interface ResearchSchedule {
  id: string
  topic: string
  cadence: string
  next_run_at?: string | null
  last_run_at?: string | null
  last_result_session_id?: string | null
  enabled: number
  reminder_note: string
  created_at: string
  updated_at: string
}

export interface UsageInfo {
  session_id: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
}

export interface FreelanceCockpit {
  connected_platforms: string[]
  job_count: number
  open_jobs: number
  proposal_count: number
  recent_jobs: { id: string; title: string; fit_score?: number | null; status: string }[]
  recent_proposals: { id: string; title: string; platform: string }[]
}

export async function fetchProjects(): Promise<WorkspaceProject[]> {
  return json(await apiFetch(`${API}/projects`))
}

export async function createProject(name: string, description = '', clientId?: string) {
  return json<WorkspaceProject>(
    await apiFetch(`${API}/projects`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description, clientId }),
    }),
  )
}

export async function deleteProject(id: string) {
  await json(await apiFetch(`${API}/projects/${id}`, { method: 'DELETE' }))
}

export async function fetchProposals(): Promise<Proposal[]> {
  return json(await apiFetch(`${API}/proposals`))
}

export async function createProposal(payload: {
  title: string
  content: string
  platform?: string
  sessionId?: string
  jobId?: string
}) {
  return json<Proposal>(
    await apiFetch(`${API}/proposals`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  )
}

export async function deleteProposal(id: string) {
  await json(await apiFetch(`${API}/proposals/${id}`, { method: 'DELETE' }))
}

export async function fetchJobs(): Promise<JobItem[]> {
  return json(await apiFetch(`${API}/jobs`))
}

export async function createJob(content: string, title = '') {
  return json<JobItem>(
    await apiFetch(`${API}/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, title, source: 'paste' }),
    }),
  )
}

export async function deleteJob(id: string) {
  await json(await apiFetch(`${API}/jobs/${id}`, { method: 'DELETE' }))
}

export async function fetchClients(): Promise<CrmClient[]> {
  return json(await apiFetch(`${API}/clients`))
}

export async function createClient(name: string, notes = '', rate = '') {
  return json<CrmClient>(
    await apiFetch(`${API}/clients`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, notes, rate }),
    }),
  )
}

export async function deleteClient(id: string) {
  await json(await apiFetch(`${API}/clients/${id}`, { method: 'DELETE' }))
}

export async function fetchAudit(limit = 50): Promise<AuditEntry[]> {
  return json(await apiFetch(`${API}/audit?limit=${limit}`))
}

export async function syncArtifacts(sessionId: string): Promise<Artifact[]> {
  return json(await apiFetch(`${API}/sessions/${sessionId}/artifacts/sync`, { method: 'POST' }))
}

export async function fetchArtifacts(sessionId: string): Promise<Artifact[]> {
  return json(await apiFetch(`${API}/sessions/${sessionId}/artifacts`))
}

export async function fetchSchedules(): Promise<ResearchSchedule[]> {
  return json(await apiFetch(`${API}/schedules`))
}

export async function fetchDueSchedules(): Promise<ResearchSchedule[]> {
  return json(await apiFetch(`${API}/schedules/due`))
}

export async function createSchedule(topic: string, cadence = 'weekly') {
  return json<ResearchSchedule>(
    await apiFetch(`${API}/schedules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic, cadence }),
    }),
  )
}

export async function deleteSchedule(id: string) {
  await json(await apiFetch(`${API}/schedules/${id}`, { method: 'DELETE' }))
}

export async function markScheduleRun(id: string, sessionId?: string) {
  return json<ResearchSchedule>(
    await apiFetch(`${API}/schedules/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ markRun: true, sessionId }),
    }),
  )
}

export async function fetchUsage(sessionId: string): Promise<UsageInfo> {
  return json(await apiFetch(`${API}/sessions/${sessionId}/usage`))
}

export async function fetchCockpit(): Promise<FreelanceCockpit> {
  return json(await apiFetch(`${API}/freelance/cockpit`))
}

export async function exportChat(sessionId: string, format: 'markdown' | 'html' = 'markdown') {
  const res = await apiFetch(`${API}/sessions/${sessionId}/export?format=${format}`)
  if (!res.ok) throw new Error('Export failed')
  const blob = await res.blob()
  const cd = res.headers.get('Content-Disposition') || ''
  const match = /filename="([^"]+)"/.exec(cd)
  const filename = match?.[1] || `chat.${format === 'html' ? 'html' : 'md'}`
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
