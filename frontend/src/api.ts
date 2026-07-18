export interface ChatSession {
  id: string
  title: string
  pinned?: boolean
  project_id?: string | null
  prompt_tokens?: number
  completion_tokens?: number
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  sources?: string
  created_at: string
}

import type { BotSettings } from './settings'
import { apiFetch } from './utils/apiFetch'

const API_BASE = '/api'

export interface MistralModel {
  id: string
  name: string
  category: string
  model_type?: string
  description?: string
}

export interface ModelCatalog {
  models: MistralModel[]
  ocrModels: MistralModel[]
}

export async function fetchModelCatalog(): Promise<ModelCatalog> {
  const res = await apiFetch(`${API_BASE}/models`)
  if (!res.ok) throw new Error('Failed to fetch models')
  const data = await res.json()
  return {
    models: data.models as MistralModel[],
    ocrModels: (data.ocr_models || []) as MistralModel[],
  }
}

/** @deprecated use fetchModelCatalog */
export async function fetchModels(): Promise<MistralModel[]> {
  const { models } = await fetchModelCatalog()
  return models
}

export async function fetchSessions(): Promise<ChatSession[]> {
  const res = await apiFetch(`${API_BASE}/sessions`)
  if (!res.ok) throw new Error('Failed to fetch sessions')
  return res.json()
}

export async function createSession(title = 'New Chat'): Promise<ChatSession> {
  const res = await apiFetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
  if (!res.ok) throw new Error('Failed to create session')
  return res.json()
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await apiFetch(`${API_BASE}/sessions/${sessionId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete session')
}

export async function renameSession(sessionId: string, title: string): Promise<ChatSession> {
  const res = await apiFetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
  if (!res.ok) throw new Error('Failed to rename session')
  return res.json()
}

export async function updateSession(
  sessionId: string,
  patch: { title?: string; pinned?: boolean; project_id?: string | null; clear_project?: boolean },
): Promise<ChatSession> {
  const res = await apiFetch(`${API_BASE}/sessions/${sessionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new Error('Failed to update session')
  return res.json()
}

export async function pinSession(sessionId: string, pinned: boolean): Promise<ChatSession> {
  return updateSession(sessionId, { pinned })
}

export interface SessionSearchHit {
  session_id: string
  session_title: string
  snippet: string
  score: number
  message_role: string
}

export async function searchSessions(
  query: string,
  excludeSessionId?: string,
  limit = 10,
): Promise<SessionSearchHit[]> {
  const params = new URLSearchParams({ q: query, limit: String(limit) })
  if (excludeSessionId) params.set('exclude', excludeSessionId)
  const res = await apiFetch(`${API_BASE}/sessions/search?${params}`)
  if (!res.ok) throw new Error('Failed to search sessions')
  return res.json()
}

export async function fetchMessages(sessionId: string): Promise<ChatMessage[]> {
  const res = await apiFetch(`${API_BASE}/sessions/${sessionId}/messages`)
  if (!res.ok) throw new Error('Failed to fetch messages')
  return res.json()
}

export async function persistMessages(
  sessionId: string,
  messages: { role: 'user' | 'assistant' | 'system'; content: string; sources?: string }[],
): Promise<ChatMessage[]> {
  const res = await apiFetch(`${API_BASE}/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages }),
  })
  if (!res.ok) throw new Error('Failed to persist messages')
  return res.json()
}

export async function fetchSessionAgent(sessionId: string): Promise<EphemeralAgent | null> {
  const res = await apiFetch(`${API_BASE}/sessions/${sessionId}/agents`)
  if (!res.ok) throw new Error('Failed to fetch session agent')
  const data = await res.json()
  return data ?? null
}

export async function dismissSessionAgent(sessionId: string, agentId: string): Promise<void> {
  const res = await apiFetch(`${API_BASE}/sessions/${sessionId}/agents/${agentId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to dismiss agent')
}

export interface ResearchSource {
  id?: number
  title: string
  url: string
  domain?: string
  snippet?: string
}

export type WebSearchSource = ResearchSource

export interface DocumentCitation {
  id: number
  document_id: string
  filename: string
  chunk_index: number
  page: number
  page_end?: number
  snippet: string
  content: string
}

export interface ResearchStatus {
  phase: 'planning' | 'searching' | 'analyzing' | 'writing' | 'complete'
  message: string
  step: number
  total: number
  query?: string
  label?: string
  sources_found?: number
  new_sources?: ResearchSource[]
}

export interface ResearchMeta {
  provider?: string
  sources?: number
  queries?: number
  source_list?: ResearchSource[]
  web_forced?: boolean
}

export type ActivityPhase =
  | 'thinking'
  | 'reasoning'
  | 'planning'
  | 'searching'
  | 'analyzing'
  | 'writing'
  | 'tools'
  | 'calculating'
  | 'complete'

export interface ActivityItem {
  id: string
  label: string
  detail: string
  phase: ActivityPhase
  state: 'active' | 'done'
}

export interface ChatActivityStatus {
  phase: ActivityPhase
  label?: string
  detail?: string
}

export interface ClarificationRequest {
  question: string
  options: string[]
  allowCustom: boolean
}

export interface YouTubeVideo {
  videoId: string
  title: string
  channel: string
  thumbnail: string
  url: string
  description: string
}

export interface EphemeralAgent {
  id: string
  session_id: string
  name: string
  role_prompt: string
  model_preference: string
  allowed_tools: string[]
  created_at: string
}

function phaseLabel(phase: ResearchStatus['phase'], label?: string): string {
  if (label) return label
  const map: Record<ResearchStatus['phase'], string> = {
    planning: 'Planning',
    searching: 'Searching the web',
    analyzing: 'Analyzing sources',
    writing: 'Writing',
    complete: 'Done',
  }
  return map[phase] ?? 'Working'
}

const ACTIVITY_LABELS: Record<ActivityPhase, string> = {
  thinking: 'Thinking',
  reasoning: 'Reasoning',
  planning: 'Planning',
  searching: 'Searching the web',
  analyzing: 'Analyzing sources',
  writing: 'Writing',
  tools: 'Using tools',
  calculating: 'Calculating',
  complete: 'Done',
}

export function activityLabel(phase: ActivityPhase, label?: string): string {
  if (label) return label
  return ACTIVITY_LABELS[phase] ?? 'Working'
}

export function researchToActivity(status: ResearchStatus): Pick<ActivityItem, 'label' | 'detail' | 'phase'> {
  const label = phaseLabel(status.phase, status.label)
  let detail = status.message
  if (status.query && status.phase === 'searching') {
    const q = status.query.length > 72 ? `${status.query.slice(0, 72)}…` : status.query
    detail = `"${q}"`
  }
  return { label, detail, phase: status.phase }
}

export function chatActivityToItem(status: ChatActivityStatus): Pick<ActivityItem, 'label' | 'detail' | 'phase'> {
  return {
    label: activityLabel(status.phase, status.label),
    detail: status.detail ?? '',
    phase: status.phase,
  }
}

export async function streamChat(
  sessionId: string,
  message: string,
  botSettings: BotSettings,
  onToken: (token: string) => void,
  onDone: (wasClarification?: boolean) => void,
  onError: (error: string) => void,
  onMeta?: (meta: string) => void,
  onModelDisplay?: (name: string) => void,
  deepResearch = false,
  onResearchStatus?: (status: ResearchStatus) => void,
  onActivity?: (status: ChatActivityStatus) => void,
  onResearchMeta?: (meta: ResearchMeta) => void,
  onBuildMode?: (active: boolean) => void,
  onEphemeralAgent?: (payload: { action: 'created' | 'dismissed'; agent?: EphemeralAgent; name?: string }) => void,
  onClarification?: (clarification: ClarificationRequest) => void,
  onSources?: (sources: WebSearchSource[]) => void,
  onDocCitations?: (citations: DocumentCitation[]) => void,
  onYoutubeVideos?: (videos: YouTubeVideo[]) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response
  try {
    res = await apiFetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        message,
        settings: botSettings,
        deepResearch,
      }),
      signal,
    })
  } catch (err) {
    if (signal?.aborted || (err instanceof DOMException && err.name === 'AbortError')) {
      onDone(false)
      return
    }
    onError('Failed to connect to chat service')
    return
  }

  if (!res.ok) {
    onError('Failed to connect to chat service')
    return
  }

  const reader = res.body?.getReader()
  if (!reader) {
    onError('No response stream')
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel().catch(() => undefined)
        onDone(false)
        return
      }
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const jsonStr = line.slice(6).trim()
        if (!jsonStr) continue

        try {
          const data = JSON.parse(jsonStr)
          if (data.error) {
            onError(data.error)
            return
          }
          if (data.meta && onMeta) {
            onMeta(data.meta)
          }
          if (data.model_display && onModelDisplay) {
            onModelDisplay(data.model_display as string)
          }
          if (data.build_mode && onBuildMode) {
            onBuildMode(true)
          }
          if (data.ephemeral_agent && onEphemeralAgent) {
            onEphemeralAgent(data.ephemeral_agent)
          }
          if (data.research && onResearchStatus) {
            onResearchStatus(data.research as ResearchStatus)
          }
          if (data.research_meta && onResearchMeta) {
            onResearchMeta(data.research_meta as ResearchMeta)
          }
          if (data.activity && onActivity) {
            onActivity(data.activity as ChatActivityStatus)
          }
          if (data.clarification && onClarification) {
            onClarification(data.clarification as ClarificationRequest)
          }
          if (data.sources && onSources) {
            onSources(data.sources as WebSearchSource[])
          }
          if (data.doc_citations && onDocCitations) {
            onDocCitations(data.doc_citations as DocumentCitation[])
          }
          if (data.youtube_videos && onYoutubeVideos) {
            onYoutubeVideos(data.youtube_videos as YouTubeVideo[])
          }
          if (data.token) {
            onToken(data.token)
          }
          if (data.done) {
            onDone(Boolean(data.clarification))
            return
          }
        } catch {
          // skip malformed lines
        }
      }
    }
    onDone()
  } catch (err) {
    if (signal?.aborted || (err instanceof DOMException && err.name === 'AbortError')) {
      onDone(false)
      return
    }
    onError(err instanceof Error ? err.message : 'Stream interrupted')
  }
}
