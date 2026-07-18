import { useState, useEffect, useMemo, type ReactNode } from 'react'
import {
  X,
  RotateCcw,
  Sparkles,
  MessageSquare,
  Plug,
  Box,
  Brain,
  FileText,
  Sliders,
  Wand2,
  GitFork,
} from 'lucide-react'
import type { BotSettings } from '../settings'
import {
  PERSONALITY_OPTIONS,
  RESPONSE_LENGTH_OPTIONS,
  CREATIVITY_OPTIONS,
  DIAGRAM_OPTIONS,
  CODE_STYLE_OPTIONS,
} from '../settings'
import { fetchModelCatalog, type MistralModel } from '../api'
import IntegrationsTab from './IntegrationsTab'
import McpTab from './McpTab'
import GithubTab from './GithubTab'
import type { ConnectionStatus } from '../connections'
import type { McpPreset, McpServer } from '../mcp'
import type { GithubRepo } from '../github'
import type { SettingsTabId } from '../utils/connectIntent'

type Tab = SettingsTabId

interface Props {
  settings: BotSettings
  onChange: (patch: Partial<BotSettings>) => void
  onReset: () => void
  onClose: () => void
  initialTab?: Tab | null
  mcpFocus?: string | null
  connections: ConnectionStatus[]
  connectionsLoading: boolean
  connectionsError: string | null
  onConnect: (provider: string, data: Record<string, string>) => Promise<void>
  onDisconnect: (provider: string) => Promise<void>
  mcpPresets: McpPreset[]
  mcpServers: McpServer[]
  mcpLoading: boolean
  mcpError: string | null
  onMcpConnect: (payload: {
    name: string
    preset: string
    transport: string
    command: string
    args: string[]
    url: string
    env?: Record<string, string>
  }) => Promise<McpServer | void>
  onMcpRemove: (id: string) => Promise<void>
  onMcpTest: (id: string) => Promise<void>
  onMcpToggle: (id: string, enabled: boolean) => Promise<void>
  githubRepos: GithubRepo[]
  githubLoading: boolean
  githubError: string | null
  onGithubAdd: (url: string, token: string, branch: string) => Promise<GithubRepo | void>
  onGithubRemove: (id: string) => Promise<void>
  onGithubToggleActive: (id: string) => void
}

const MAIN_TABS: { id: Tab; label: string; hint: string; icon: typeof MessageSquare }[] = [
  { id: 'behavior', label: 'Chat', hint: 'Model, tone & style', icon: MessageSquare },
  { id: 'connections', label: 'Integrations', hint: 'Upwork, Telegram…', icon: Plug },
  { id: 'mcp', label: 'Apps & tools', hint: 'Blender, live Upwork…', icon: Box },
  { id: 'github', label: 'GitHub', hint: 'Repos for code Q&A', icon: GitFork },
]
const CATEGORY_LABELS: Record<string, string> = {
  general: 'General purpose',
  code: 'Code & dev',
  vision: 'Design & vision',
  fast: 'Fast & light',
}

function SettingCard({
  icon,
  title,
  description,
  children,
}: {
  icon?: ReactNode
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <section className="settings-card">
      <div className="settings-card-head">
        {icon && <div className="settings-card-icon">{icon}</div>}
        <div className="settings-card-titles">
          <h3 className="settings-card-title">{title}</h3>
          {description && <p className="settings-card-desc">{description}</p>}
        </div>
      </div>
      <div className="settings-card-body">{children}</div>
    </section>
  )
}

function SettingField({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="settings-field">
      <div className="settings-field-label">
        <span>{label}</span>
        {hint && <span className="settings-field-hint">{hint}</span>}
      </div>
      {children}
    </div>
  )
}

function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  columns = 3,
}: {
  options: { value: T; label: string; desc?: string }[]
  value: T
  onChange: (v: T) => void
  columns?: 2 | 3 | 4
}) {
  return (
    <div className={`settings-segmented settings-segmented-cols-${columns}`} role="radiogroup">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          role="radio"
          aria-checked={value === opt.value}
          className={`settings-segment${value === opt.value ? ' settings-segment-active' : ''}`}
          onClick={() => onChange(opt.value)}
          title={opt.desc}
        >
          <span className="settings-segment-label">{opt.label}</span>
          {opt.desc && <span className="settings-segment-desc">{opt.desc}</span>}
        </button>
      ))}
    </div>
  )
}

function ModelSelect({
  value,
  models,
  loading,
  onChange,
  autoDescription,
}: {
  value: string
  models: MistralModel[]
  loading: boolean
  onChange: (id: string) => void
  autoDescription: string
}) {
  const grouped = useMemo(() => {
    const acc: Record<string, MistralModel[]> = {}
    for (const m of models) {
      const cat = m.category || 'general'
      if (!acc[cat]) acc[cat] = []
      acc[cat].push(m)
    }
    return acc
  }, [models])

  const order = ['general', 'code', 'vision', 'fast']
  const selectedHint = useMemo(() => {
    if (value === 'auto') return autoDescription
    const m = models.find((x) => x.id === value)
    return m?.description || m?.id || ''
  }, [value, models, autoDescription])

  return (
    <div className="settings-model-picker">
      <select
        className="settings-select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={loading}
      >
        <option value="auto">Auto — recommended</option>
        {order.map((cat) => {
          const items = grouped[cat]
          if (!items?.length) return null
          return (
            <optgroup key={cat} label={CATEGORY_LABELS[cat] || cat}>
              {items.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name || m.id}
                </option>
              ))}
            </optgroup>
          )
        })}
      </select>
      {loading ? (
        <p className="settings-inline-hint">Loading models from Mistral…</p>
      ) : selectedHint ? (
        <p className="settings-inline-hint">{selectedHint}</p>
      ) : null}
    </div>
  )
}

function OcrModelSelect({
  value,
  models,
  loading,
  onChange,
}: {
  value: string
  models: MistralModel[]
  loading: boolean
  onChange: (id: string) => void
}) {
  const selected = value === 'auto'
    ? null
    : models.find((m) => m.id === value)

  return (
    <div className="settings-model-picker">
      <select
        className="settings-select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={loading}
      >
        <option value="auto">Auto — smart PDF handling</option>
        {models.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name || m.id}
          </option>
        ))}
      </select>
      <p className="settings-inline-hint">
        {value === 'auto'
          ? 'Uses OCR for scanned PDFs; fast text extraction for digital PDFs.'
          : selected?.description || selected?.id || ''}
      </p>
    </div>
  )
}

export default function SettingsPanel({
  settings,
  onChange,
  onReset,
  onClose,
  initialTab = null,
  mcpFocus = null,
  connections,
  connectionsLoading,
  connectionsError,
  onConnect,
  onDisconnect,
  mcpPresets,
  mcpServers,
  mcpLoading,
  mcpError,
  onMcpConnect,
  onMcpRemove,
  onMcpTest,
  onMcpToggle,
  githubRepos,
  githubLoading,
  githubError,
  onGithubAdd,
  onGithubRemove,
  onGithubToggleActive,
}: Props) {
  const [tab, setTab] = useState<Tab>(initialTab ?? 'behavior')
  const [models, setModels] = useState<MistralModel[]>([])
  const [ocrModels, setOcrModels] = useState<MistralModel[]>([])
  const [modelsLoading, setModelsLoading] = useState(false)
  const [localMcpFocus, setLocalMcpFocus] = useState<string | null>(null)

  const connectedCount = connections.filter((c) => c.connected).length
  const mcpActiveCount = mcpServers.filter((s) => s.enabled).length
  const githubReadyCount = githubRepos.filter((r) => r.status === 'ready').length
  const effectiveMcpFocus = localMcpFocus ?? mcpFocus

  useEffect(() => {
    if (initialTab && MAIN_TABS.some((t) => t.id === initialTab)) setTab(initialTab)
  }, [initialTab])

  useEffect(() => {
    let cancelled = false
    setModelsLoading(true)
    fetchModelCatalog()
      .then((data) => {
        if (!cancelled) {
          setModels(data.models)
          setOcrModels(data.ocrModels)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setModels([])
          setOcrModels([])
        }
      })
      .finally(() => {
        if (!cancelled) setModelsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const activeTabMeta = MAIN_TABS.find((t) => t.id === tab) ?? MAIN_TABS[0]

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-panel settings-panel-layout" onClick={(e) => e.stopPropagation()}>
        <aside className="settings-sidebar">
          <div className="settings-sidebar-brand">
            <h2>Settings</h2>
            <p>Changes save automatically</p>
          </div>
          <nav className="settings-nav">
            {MAIN_TABS.map(({ id, label, hint, icon: Icon }) => (
              <button
                key={id}
                type="button"
                className={`settings-nav-item${tab === id ? ' settings-nav-item-active' : ''}`}
                onClick={() => setTab(id)}
              >
                <Icon size={18} className="settings-nav-icon" />
                <span className="settings-nav-text">
                  <span className="settings-nav-label">{label}</span>
                  <span className="settings-nav-hint">{hint}</span>
                </span>
                {id === 'connections' && connectedCount > 0 && (
                  <span className="settings-nav-badge">{connectedCount}</span>
                )}
                {id === 'mcp' && mcpActiveCount > 0 && (
                  <span className="settings-nav-badge">{mcpActiveCount}</span>
                )}
                {id === 'github' && githubReadyCount > 0 && (
                  <span className="settings-nav-badge">{githubReadyCount}</span>
                )}
              </button>
            ))}
          </nav>
          <button type="button" className="settings-close settings-close-sidebar" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </aside>

        <div className="settings-main">
          <header className="settings-main-header">
            <div>
              <h2 className="settings-main-title">{activeTabMeta.label}</h2>
              <p className="settings-main-subtitle">{activeTabMeta.hint}</p>
            </div>
            <button type="button" className="settings-close settings-close-mobile" onClick={onClose} aria-label="Close">
              <X size={20} />
            </button>
          </header>

          <div className="settings-body">
            {tab === 'behavior' ? (
              <div className="settings-cards">
                <SettingCard
                  icon={<Brain size={18} />}
                  title="AI model"
                  description="Choose which Mistral model answers your messages."
                >
                  <SettingField label="Chat model" hint="Auto picks the best model per task.">
                    <ModelSelect
                      value={settings.modelSelection}
                      models={models}
                      loading={modelsLoading}
                      onChange={(id) => onChange({ modelSelection: id })}
                      autoDescription="Routes Q&A, code, and design tasks automatically with multi-model orchestration when needed."
                    />
                  </SettingField>
                </SettingCard>

                <SettingCard
                  icon={<FileText size={18} />}
                  title="PDF & documents"
                  description="How uploaded PDFs are read and indexed."
                >
                  <SettingField label="OCR model">
                    <OcrModelSelect
                      value={settings.ocrModelSelection}
                      models={ocrModels}
                      loading={modelsLoading}
                      onChange={(id) => onChange({ ocrModelSelection: id })}
                    />
                  </SettingField>
                </SettingCard>

                <SettingCard
                  icon={<Wand2 size={18} />}
                  title="Personality & tone"
                  description="How the assistant sounds when it replies."
                >
                  <SettingField label="Personality">
                    <SegmentedControl
                      options={PERSONALITY_OPTIONS}
                      value={settings.personality}
                      onChange={(v) => onChange({ personality: v })}
                      columns={2}
                    />
                  </SettingField>
                </SettingCard>

                <SettingCard
                  icon={<Sliders size={18} />}
                  title="Response style"
                  description="Length and creativity of answers."
                >
                  <SettingField label="Length">
                    <SegmentedControl
                      options={RESPONSE_LENGTH_OPTIONS}
                      value={settings.responseLength}
                      onChange={(v) => onChange({ responseLength: v })}
                      columns={3}
                    />
                  </SettingField>
                  <SettingField label="Creativity">
                    <SegmentedControl
                      options={CREATIVITY_OPTIONS}
                      value={settings.creativity}
                      onChange={(v) => onChange({ creativity: v })}
                      columns={3}
                    />
                  </SettingField>
                </SettingCard>

                <SettingCard
                  icon={<Sparkles size={18} />}
                  title="Extras"
                  description="Diagrams, code formatting, and custom rules."
                >
                  <SettingField label="Diagrams" hint="Mermaid charts in answers">
                    <SegmentedControl
                      options={DIAGRAM_OPTIONS}
                      value={settings.diagramMode}
                      onChange={(v) => onChange({ diagramMode: v })}
                      columns={3}
                    />
                  </SettingField>
                  <SettingField label="Code style">
                    <SegmentedControl
                      options={CODE_STYLE_OPTIONS}
                      value={settings.codeStyle}
                      onChange={(v) => onChange({ codeStyle: v })}
                      columns={3}
                    />
                  </SettingField>
                  <div className="settings-row">
                    <div className="settings-row-text">
                      <span className="settings-row-label">Ask clarifying questions</span>
                      <span className="settings-row-desc">When your message is vague or missing context</span>
                    </div>
                    <label className="settings-toggle">
                      <input
                        type="checkbox"
                        checked={settings.clarifyQuestions}
                        onChange={(e) => onChange({ clarifyQuestions: e.target.checked })}
                      />
                      <span className="settings-toggle-track" />
                    </label>
                  </div>
                  <SettingField label="Custom instructions" hint="Always applied to every chat">
                    <textarea
                      className="settings-textarea"
                      placeholder="e.g. Always use Python. Prefer step-by-step answers. Keep responses under 200 words."
                      value={settings.customInstructions}
                      onChange={(e) => onChange({ customInstructions: e.target.value })}
                      rows={3}
                    />
                  </SettingField>
                </SettingCard>
              </div>
            ) : tab === 'connections' ? (
              <IntegrationsTab
                connections={connections}
                loading={connectionsLoading}
                error={connectionsError}
                onConnect={onConnect}
                onDisconnect={onDisconnect}
                onOpenLiveUpwork={() => {
                  setLocalMcpFocus('upwork')
                  setTab('mcp')
                }}
              />
            ) : tab === 'github' ? (
              <GithubTab
                repos={githubRepos}
                loading={githubLoading}
                error={githubError}
                activeRepoIds={settings.activeGithubRepoIds}
                onAdd={onGithubAdd}
                onRemove={onGithubRemove}
                onToggleActive={onGithubToggleActive}
              />
            ) : (
              <McpTab
                presets={mcpPresets}
                servers={mcpServers}
                loading={mcpLoading}
                error={mcpError}
                focusPreset={effectiveMcpFocus}
                onConnect={onMcpConnect}
                onRemove={onMcpRemove}
                onTest={onMcpTest}
                onToggle={onMcpToggle}
              />            )}
          </div>

          <footer className="settings-footer">
            {tab === 'behavior' ? (
              <button type="button" className="settings-reset" onClick={onReset}>
                <RotateCcw size={14} />
                Reset defaults
              </button>
            ) : (
              <span />
            )}
            <button type="button" className="settings-save" onClick={onClose}>
              Done
            </button>
          </footer>
        </div>
      </div>
    </div>
  )
}
