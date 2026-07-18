import { DEFAULT_COMPOSER_MODEL_ID } from './models'
import { formatMemoryForPrompt, loadMemoryItems } from './utils/userMemory'
import { getActiveUserId } from './utils/userScope'

export type Personality = 'professional' | 'friendly' | 'concise' | 'teacher'
export type ResponseLength = 'brief' | 'balanced' | 'detailed'
export type Creativity = 'precise' | 'balanced' | 'creative'
export type DiagramMode = 'auto' | 'on_request' | 'off'
export type CodeStyle = 'minimal' | 'commented' | 'production'

export interface BotSettings {
  personality: Personality
  responseLength: ResponseLength
  creativity: Creativity
  clarifyQuestions: boolean
  diagramMode: DiagramMode
  codeStyle: CodeStyle
  customInstructions: string
  modelSelection: string
  ocrModelSelection: string
  webSearchMode: 'auto' | 'on' | 'off'
  activeGithubRepoIds: string[]
}

export const DEFAULT_SETTINGS: BotSettings = {
  personality: 'teacher',
  responseLength: 'detailed',
  creativity: 'balanced',
  clarifyQuestions: true,
  diagramMode: 'auto',
  codeStyle: 'commented',
  customInstructions: '',
  modelSelection: DEFAULT_COMPOSER_MODEL_ID,
  ocrModelSelection: 'auto',
  webSearchMode: 'auto',
  activeGithubRepoIds: [],
}

const STORAGE_KEY = 'nexus-bot-settings'
const SETTINGS_VERSION = 3

function settingsKey(userId?: string | null): string {
  const id = userId ?? getActiveUserId()
  return id ? `${STORAGE_KEY}:${id}` : STORAGE_KEY
}

type StoredSettings = BotSettings & { settingsVersion?: number }

const PERSONALITIES = new Set<Personality>(['professional', 'friendly', 'concise', 'teacher'])
const LENGTHS = new Set<ResponseLength>(['brief', 'balanced', 'detailed'])
const CREATIVITIES = new Set<Creativity>(['precise', 'balanced', 'creative'])
const DIAGRAMS = new Set<DiagramMode>(['auto', 'on_request', 'off'])
const CODE_STYLES = new Set<CodeStyle>(['minimal', 'commented', 'production'])
const WEB_MODES = new Set(['auto', 'on', 'off'])

function coerceSettings(raw: unknown): BotSettings {
  const base = { ...DEFAULT_SETTINGS }
  if (!raw || typeof raw !== 'object') return base
  const parsed = raw as Record<string, unknown>

  if (typeof parsed.personality === 'string' && PERSONALITIES.has(parsed.personality as Personality)) {
    base.personality = parsed.personality as Personality
  }
  if (typeof parsed.responseLength === 'string' && LENGTHS.has(parsed.responseLength as ResponseLength)) {
    base.responseLength = parsed.responseLength as ResponseLength
  }
  if (typeof parsed.creativity === 'string' && CREATIVITIES.has(parsed.creativity as Creativity)) {
    base.creativity = parsed.creativity as Creativity
  }
  if (typeof parsed.clarifyQuestions === 'boolean') {
    base.clarifyQuestions = parsed.clarifyQuestions
  }
  if (typeof parsed.diagramMode === 'string' && DIAGRAMS.has(parsed.diagramMode as DiagramMode)) {
    base.diagramMode = parsed.diagramMode as DiagramMode
  }
  if (typeof parsed.codeStyle === 'string' && CODE_STYLES.has(parsed.codeStyle as CodeStyle)) {
    base.codeStyle = parsed.codeStyle as CodeStyle
  }
  if (typeof parsed.customInstructions === 'string') {
    base.customInstructions = parsed.customInstructions.slice(0, 8000)
  }
  if (typeof parsed.modelSelection === 'string' && parsed.modelSelection.trim()) {
    base.modelSelection = parsed.modelSelection.trim()
  }
  if (typeof parsed.ocrModelSelection === 'string' && parsed.ocrModelSelection.trim()) {
    base.ocrModelSelection = parsed.ocrModelSelection.trim()
  }
  if (typeof parsed.webSearchMode === 'string' && WEB_MODES.has(parsed.webSearchMode)) {
    base.webSearchMode = parsed.webSearchMode as BotSettings['webSearchMode']
  }
  if (Array.isArray(parsed.activeGithubRepoIds)) {
    base.activeGithubRepoIds = parsed.activeGithubRepoIds
      .filter((id): id is string => typeof id === 'string' && id.trim().length > 0)
      .slice(0, 50)
  }
  return base
}

export function loadSettings(userId?: string | null): BotSettings {
  try {
    const id = userId ?? getActiveUserId()
    const raw =
      localStorage.getItem(settingsKey(id)) ??
      (id ? localStorage.getItem(STORAGE_KEY) : null)
    if (!raw) return { ...DEFAULT_SETTINGS }
    const json = JSON.parse(raw)
    const parsed = coerceSettings(json) as StoredSettings
    parsed.settingsVersion = typeof json?.settingsVersion === 'number' ? json.settingsVersion : 1
    let migrated = false
    const version = parsed.settingsVersion ?? 1

    // v3: restore streaming-friendly web search default (auto, not always-on tools)
    if (version < 3 && parsed.webSearchMode === 'on') {
      parsed.webSearchMode = 'auto'
      migrated = true
    }
    if (!parsed.modelSelection || parsed.modelSelection === 'auto') {
      parsed.modelSelection = DEFAULT_COMPOSER_MODEL_ID
      migrated = true
    }

    if (version < SETTINGS_VERSION) {
      if (parsed.responseLength === 'balanced' && parsed.personality === 'friendly') {
        parsed.responseLength = 'detailed'
        parsed.personality = 'teacher'
        migrated = true
      }
      parsed.settingsVersion = SETTINGS_VERSION
      migrated = true
    }

    if (migrated) {
      saveSettings(parsed, id)
    }
    return parsed
  } catch {
    return { ...DEFAULT_SETTINGS }
  }
}

export function saveSettings(settings: BotSettings, userId?: string | null): void {
  localStorage.setItem(settingsKey(userId), JSON.stringify(settings))
}

/** Merge saved memory facts into settings sent to the API (fenced, not elevated). */
export function settingsWithMemory(settings: BotSettings): BotSettings {
  const memoryBlock = formatMemoryForPrompt(loadMemoryItems())
  if (!memoryBlock) return settings
  const custom = settings.customInstructions.trim()
  return {
    ...settings,
    customInstructions: custom ? `${custom}\n\n${memoryBlock}` : memoryBlock,
  }
}

export const PERSONALITY_OPTIONS: { value: Personality; label: string; desc: string }[] = [
  { value: 'professional', label: 'Professional', desc: 'Formal, business-like tone' },
  { value: 'friendly', label: 'Friendly', desc: 'Warm and conversational' },
  { value: 'concise', label: 'Concise', desc: 'Direct, no fluff' },
  { value: 'teacher', label: 'Teacher', desc: 'Patient, educational explanations' },
]

export const RESPONSE_LENGTH_OPTIONS: { value: ResponseLength; label: string }[] = [
  { value: 'brief', label: 'Brief' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'detailed', label: 'Detailed' },
]

export const CREATIVITY_OPTIONS: { value: Creativity; label: string; desc: string }[] = [
  { value: 'precise', label: 'Precise', desc: 'Factual, focused answers' },
  { value: 'balanced', label: 'Balanced', desc: 'Mix of accuracy and flexibility' },
  { value: 'creative', label: 'Creative', desc: 'More imaginative responses' },
]

export const DIAGRAM_OPTIONS: { value: DiagramMode; label: string; desc: string }[] = [
  { value: 'auto', label: 'Auto', desc: 'Generate diagrams when helpful' },
  { value: 'on_request', label: 'On request', desc: 'Only when you ask' },
  { value: 'off', label: 'Off', desc: 'Text explanations only' },
]

export const CODE_STYLE_OPTIONS: { value: CodeStyle; label: string; desc: string }[] = [
  { value: 'minimal', label: 'Minimal', desc: 'Short code snippets' },
  { value: 'commented', label: 'Commented', desc: 'Code with explanations' },
  { value: 'production', label: 'Production', desc: 'Complete, robust examples' },
]
