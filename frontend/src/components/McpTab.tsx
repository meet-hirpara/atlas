import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Box,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  CheckCircle2,
  Link2,
  RefreshCw,
  Trash2,
  Unlink,
  AlertCircle,
  Zap,
  Info,
  Wrench,
} from 'lucide-react'
import type { McpPreset, McpServer } from '../mcp'
import { fetchMcpServerTools, type McpTool } from '../mcp'

interface Props {
  presets: McpPreset[]
  servers: McpServer[]
  loading: boolean
  error: string | null
  focusPreset?: string | null
  onConnect: (payload: {
    name: string
    preset: string
    transport: string
    command: string
    args: string[]
    url: string
    env?: Record<string, string>
  }) => Promise<McpServer | void>
  onRemove: (id: string) => Promise<void>
  onTest: (id: string) => Promise<void>
  onToggle: (id: string, enabled: boolean) => Promise<void>
}

const BLENDER_PRESET_IDS = ['blender', 'blender_sse']
const UPWORK_PRESET_IDS = ['upwork']
const OTHER_PRESET_GROUPS: { title: string; ids: string[] }[] = [
  { title: 'Unity', ids: ['unity', 'unity_stdio'] },
  { title: 'Other', ids: ['custom'] },
]

function CopyButton({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* ignore */
    }
  }

  return (
    <button type="button" className="mcp-copy-btn" onClick={copy} title={`Copy ${label || text}`}>
      {copied ? <Check size={14} /> : <Copy size={14} />}
      {copied ? 'Copied' : label || 'Copy'}
    </button>
  )
}

function StatusDot({ connected }: { connected: boolean }) {
  return (
    <span className={`mcp-status-dot ${connected ? 'mcp-status-on' : 'mcp-status-off'}`} title={connected ? 'Connected' : 'Disconnected'} />
  )
}

function ConnectForm({
  preset,
  onSubmit,
  onCancel,
  busy,
}: {
  preset: McpPreset
  onSubmit: (data: Record<string, string>) => void
  onCancel: () => void
  busy: boolean
}) {
  const [transport, setTransport] = useState(preset.transport)
  const [command, setCommand] = useState(preset.command)
  const [args, setArgs] = useState(preset.args.join(' '))
  const [url, setUrl] = useState(preset.url)
  const [name, setName] = useState(preset.name)
  const [envValues, setEnvValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {}
    for (const field of preset.env_fields || []) {
      initial[field.key] = ''
    }
    return initial
  })

  const missingRequiredEnv = (preset.env_fields || []).some(
    (f) => f.required && !envValues[f.key]?.trim(),
  )

  const needsCredentials = (preset.env_fields?.length ?? 0) > 0

  return (
    <form
      className="mcp-connect-form"
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit({
          name,
          preset: preset.id,
          transport,
          command,
          args,
          url,
          ...Object.fromEntries(
            Object.entries(envValues).map(([k, v]) => [`env:${k}`, v]),
          ),
        })
      }}
    >
      <header className="mcp-connect-form-header">
        <p className="connect-form-title">
          {needsCredentials ? `Connect ${preset.name}` : 'Connection settings'}
        </p>
        <p className="connect-form-subtitle">
          {needsCredentials
            ? 'Enter credentials below, then connect to discover tools for chat.'
            : 'Review or customize how Atlas reaches this MCP server.'}
        </p>
      </header>

      <div className="mcp-connect-fields">
        <label className="connect-field">
          <span className="connect-field-label">Display name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label className="connect-field">
          <span className="connect-field-label">Connection type</span>
          <select value={transport} onChange={(e) => setTransport(e.target.value as 'stdio' | 'sse')}>
            <option value="stdio">stdio — local command (uvx)</option>
            <option value="sse">SSE — HTTP URL</option>
          </select>
        </label>
        {transport === 'stdio' ? (
          <>
            <label className="connect-field">
              <span className="connect-field-label">Command</span>
              <input value={command} onChange={(e) => setCommand(e.target.value)} placeholder="uvx" required />
            </label>
            <label className="connect-field">
              <span className="connect-field-label">Arguments</span>
              <input value={args} onChange={(e) => setArgs(e.target.value)} placeholder="blender-mcp" />
              <span className="connect-field-hint">Space-separated, e.g. <code>blender-mcp</code></span>
            </label>
          </>
        ) : (
          <label className="connect-field">
            <span className="connect-field-label">Server URL</span>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="http://127.0.0.1:8765/sse"
              required
            />
            <span className="connect-field-hint">Copy the URL from the Blender MCP panel sidebar</span>
          </label>
        )}
      </div>

      {needsCredentials && (
        <div className="mcp-env-fields">
          <div className="mcp-env-fields-head">
            <span className="mcp-env-fields-title">Credentials</span>
            <span className="mcp-env-fields-hint">Stored with this connection on the Atlas backend</span>
          </div>
          {preset.env_fields!.map((field) => (
            <label key={field.key} className="connect-field">
              <span className="connect-field-label">
                {field.label}
                {field.required ? <span className="connect-field-required">Required</span> : null}
              </span>
              <input
                type={field.secret ? 'password' : 'text'}
                className={field.secret ? 'connect-input-secret' : undefined}
                value={envValues[field.key] || ''}
                onChange={(e) => setEnvValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                placeholder={field.secret ? '••••••••' : field.key}
                required={field.required}
                autoComplete="off"
                spellCheck={false}
              />
              {field.hint && <span className="connect-field-hint">{field.hint}</span>}
            </label>
          ))}
        </div>
      )}

      <div className="connect-form-actions">
        <button type="button" className="connect-cancel" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button type="submit" className="connect-submit" disabled={busy || missingRequiredEnv}>
          {busy ? 'Connecting…' : 'Connect & discover tools'}
        </button>
      </div>
    </form>
  )
}

function ConnectedServerCard({
  srv,
  busy,
  onTest,
  onToggle,
  onRemove,
  onError,
  onSuccess,
}: {
  srv: McpServer
  busy: boolean
  onTest: (id: string) => Promise<void>
  onToggle: (id: string, enabled: boolean) => Promise<void>
  onRemove: (id: string) => Promise<void>
  onError: (msg: string) => void
  onSuccess: (msg: string) => void
}) {
  const [showTools, setShowTools] = useState(false)
  const [tools, setTools] = useState<McpTool[] | null>(null)
  const [toolsLoading, setToolsLoading] = useState(false)
  const [toolsError, setToolsError] = useState<string | null>(null)
  const isBlender = srv.preset.startsWith('blender')

  const loadTools = useCallback(async () => {
    if (!srv.enabled) return
    setToolsLoading(true)
    setToolsError(null)
    try {
      const list = await fetchMcpServerTools(srv.id)
      setTools(list)
    } catch (e) {
      setToolsError(e instanceof Error ? e.message : 'Could not load tools')
      setTools(null)
    } finally {
      setToolsLoading(false)
    }
  }, [srv.id, srv.enabled])

  useEffect(() => {
    if (showTools && srv.enabled) void loadTools()
  }, [showTools, srv.enabled, loadTools])

  return (
    <div className={`mcp-connection-card ${srv.enabled ? 'mcp-connection-live' : ''}`}>
      <div className="mcp-connection-head">
        <div
          className="mcp-connection-icon"
          style={isBlender ? { background: 'rgba(232, 125, 13, 0.15)', color: '#E87D0D' } : undefined}
        >
          <Box size={18} />
        </div>
        <div className="mcp-connection-info">
          <div className="mcp-connection-title-row">
            <StatusDot connected={srv.enabled} />
            <span className="mcp-connection-name">{srv.name}</span>
            <span className={`mcp-connection-status ${srv.enabled ? 'mcp-status-label-on' : 'mcp-status-label-off'}`}>
              {srv.enabled ? 'Connected' : 'Disabled'}
            </span>
          </div>
          <p className="mcp-connection-detail">
            {srv.transport === 'sse' ? srv.url : `${srv.command} ${srv.args.join(' ')}`.trim()}
          </p>
          {srv.enabled && (
            <p className="mcp-connection-tools-count">
              <Wrench size={12} />
              {srv.tool_count} tool{srv.tool_count !== 1 ? 's' : ''} available in chat
            </p>
          )}
        </div>
      </div>

      {srv.enabled && (
        <div className="mcp-tools-section">
          <button
            type="button"
            className="mcp-tools-toggle"
            onClick={() => setShowTools((v) => !v)}
          >
            {showTools ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {showTools ? 'Hide tools' : 'Show available tools'}
          </button>
          {showTools && (
            <div className="mcp-tools-list">
              {toolsLoading && <p className="mcp-tools-loading">Loading tools…</p>}
              {toolsError && <p className="mcp-tools-error">{toolsError}</p>}
              {!toolsLoading && tools && tools.length > 0 && (
                <ul>
                  {tools.map((t) => (
                    <li key={t.name}>
                      <code>{t.name}</code>
                      <span>{t.description}</span>
                    </li>
                  ))}
                </ul>
              )}
              {!toolsLoading && tools && tools.length === 0 && (
                <p className="mcp-tools-empty">No tools discovered</p>
              )}
            </div>
          )}
        </div>
      )}

      <div className="mcp-connection-actions">
        <button
          type="button"
          className="integration-btn"
          disabled={busy}
          onClick={async () => {
            try {
              await onTest(srv.id)
              onSuccess(`Connection test passed for ${srv.name}`)
              if (showTools) await loadTools()
            } catch (e) {
              onError(e instanceof Error ? e.message : 'Test failed')
            }
          }}
        >
          <RefreshCw size={14} /> Test
        </button>
        <button type="button" className="integration-btn" onClick={() => onToggle(srv.id, !srv.enabled)}>
          {srv.enabled ? <Unlink size={14} /> : <Link2 size={14} />}
          {srv.enabled ? 'Disable' : 'Enable'}
        </button>
        <button
          type="button"
          className="integration-btn integration-btn-disconnect"
          disabled={busy}
          onClick={async () => {
            try {
              await onRemove(srv.id)
              onSuccess(`Removed ${srv.name}`)
            } catch (e) {
              onError(e instanceof Error ? e.message : 'Remove failed')
            }
          }}
        >
          <Trash2 size={14} /> Remove
        </button>
      </div>
    </div>
  )
}

function BlenderConnectCard({
  presets,
  servers,
  loading,
  busy,
  expanded,
  setExpanded,
  onConnect,
  setLocalError,
}: {
  presets: McpPreset[]
  servers: McpServer[]
  loading: boolean
  busy: string | null
  expanded: string | null
  setExpanded: (id: string | null) => void
  onConnect: (preset: McpPreset, data: Record<string, string>) => Promise<void>
  setLocalError: (msg: string | null) => void
}) {
  const blenderStdio = presets.find((p) => p.id === 'blender')
  const blenderSse = presets.find((p) => p.id === 'blender_sse')
  const blenderServer = servers.find((s) => s.preset.startsWith('blender') && s.enabled)
  const [method, setMethod] = useState<'stdio' | 'sse'>('stdio')
  const activePreset = method === 'stdio' ? blenderStdio : blenderSse

  const connectCmd = blenderStdio ? `${blenderStdio.command} ${blenderStdio.args.join(' ')}`.trim() : 'uvx blender-mcp'

  if (!blenderStdio && !blenderSse) return null

  return (
    <section className="settings-card mcp-blender-card">
      <div className="settings-card-head">
        <div className="settings-card-icon" style={{ background: 'rgba(232, 125, 13, 0.15)', color: '#E87D0D' }}>
          <Box size={18} />
        </div>
        <div className="settings-card-titles">
          <h3 className="settings-card-title">Connect Blender</h3>
          <p className="settings-card-desc">
            Control Blender scenes, objects, and materials directly from chat
          </p>
        </div>
        {blenderServer && (
          <div className="mcp-blender-live-badge">
            <StatusDot connected />
            <span>Live</span>
          </div>
        )}
      </div>

      <div className="settings-card-body">
        <div className="mcp-flow-diagram">
          <div className="mcp-flow-step">
            <span className="mcp-flow-num">1</span>
            <div>
              <strong>Blender addon</strong>
              <span>Starts a local MCP server inside Blender</span>
            </div>
          </div>
          <div className="mcp-flow-arrow">→</div>
          <div className="mcp-flow-step">
            <span className="mcp-flow-num">2</span>
            <div>
              <strong>Atlas bridge</strong>
              <span>Runs <code>uvx blender-mcp</code> to talk MCP</span>
            </div>
          </div>
          <div className="mcp-flow-arrow">→</div>
          <div className="mcp-flow-step">
            <span className="mcp-flow-num">3</span>
            <div>
              <strong>Chat</strong>
              <span>AI uses Blender tools in your messages</span>
            </div>
          </div>
        </div>

        <div className="mcp-checklist">
          <p className="mcp-checklist-title">Prerequisites</p>
          <ul>
            <li>
              <CheckCircle2 size={15} />
              <span><strong>Blender</strong> installed and running</span>
            </li>
            <li>
              <CheckCircle2 size={15} />
              <span><strong>Blender MCP addon</strong> installed (from the addon&apos;s GitHub releases)</span>
            </li>
            <li>
              <CheckCircle2 size={15} />
              <span>In Blender: press <kbd>N</kbd> → <strong>MCP</strong> tab → click <strong>Start Server</strong></span>
            </li>
            <li>
              <CheckCircle2 size={15} />
              <span><strong>uv</strong> installed for the bridge command: <code>pip install uv</code></span>
            </li>
          </ul>
        </div>

        <div className="mcp-method-tabs">
          <button
            type="button"
            className={`mcp-method-tab ${method === 'stdio' ? 'mcp-method-active' : ''}`}
            onClick={() => setMethod('stdio')}
          >
            Recommended · stdio
          </button>
          <button
            type="button"
            className={`mcp-method-tab ${method === 'sse' ? 'mcp-method-active' : ''}`}
            onClick={() => setMethod('sse')}
          >
            Direct HTTP · SSE
          </button>
        </div>

        {method === 'stdio' && blenderStdio && (
          <div className="mcp-command-block">
            <div className="mcp-command-label">
              <span>Bridge command Atlas runs on connect</span>
              <CopyButton text={connectCmd} label="Copy command" />
            </div>
            <code className="mcp-command-code">{connectCmd}</code>
            <p className="mcp-command-hint">
              You don&apos;t need to run this manually — click Connect below. Atlas spawns this process and discovers Blender tools automatically.
            </p>
          </div>
        )}

        {method === 'sse' && blenderSse && (
          <div className="mcp-command-block">
            <div className="mcp-command-label">
              <span>Blender HTTP endpoint</span>
              <CopyButton text={blenderSse.url} label="Copy URL" />
            </div>
            <code className="mcp-command-code">{blenderSse.url}</code>
            <p className="mcp-command-hint">
              Enable HTTP/SSE in the Blender MCP addon panel, then copy the URL shown there (default port 8765).
            </p>
          </div>
        )}

        {activePreset && (
          <>
            {expanded === activePreset.id ? (
              <ConnectForm
                preset={activePreset}
                busy={busy === activePreset.id}
                onSubmit={(data) => onConnect(activePreset, data)}
                onCancel={() => setExpanded(null)}
              />
            ) : (
              <div className="mcp-blender-actions">
                <button
                  type="button"
                  className="integration-btn integration-btn-connect mcp-connect-primary"
                  disabled={busy === activePreset.id || loading}
                  onClick={() => onConnect(activePreset, {
                    name: activePreset.name,
                    preset: activePreset.id,
                    transport: activePreset.transport,
                    command: activePreset.command,
                    args: activePreset.args.join(' '),
                    url: activePreset.url,
                  })}
                >
                  <Zap size={15} />
                  {busy === activePreset.id ? 'Connecting…' : blenderServer ? 'Reconnect Blender' : 'Connect Blender'}
                </button>
                <button
                  type="button"
                  className="integration-btn mcp-config-btn"
                  disabled={!!busy}
                  onClick={() => {
                    setExpanded(activePreset.id)
                    setLocalError(null)
                  }}
                >
                  <Link2 size={14} />
                  Custom settings
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  )
}

function UpworkConnectCard({
  presets,
  servers,
  loading,
  busy,
  expanded,
  setExpanded,
  onConnect,
  setLocalError,
}: {
  presets: McpPreset[]
  servers: McpServer[]
  loading: boolean
  busy: string | null
  expanded: string | null
  setExpanded: (id: string | null) => void
  onConnect: (preset: McpPreset, data: Record<string, string>) => Promise<void>
  setLocalError: (msg: string | null) => void
}) {
  const upworkPreset = presets.find((p) => p.id === 'upwork')
  const upworkServer = servers.find((s) => s.preset === 'upwork' && s.enabled)

  if (!upworkPreset) return null

  const connectCmd = `${upworkPreset.command} ${upworkPreset.args.join(' ')}`.trim()

  return (
    <section className="settings-card mcp-upwork-card">
      <div className="settings-card-head">
        <div className="settings-card-icon" style={{ background: 'rgba(20, 168, 0, 0.15)', color: '#14A800' }}>
          <Link2 size={18} />
        </div>
        <div className="settings-card-titles">
          <h3 className="settings-card-title">Upwork — live account</h3>
          <p className="settings-card-desc">
            Connect your Upwork API so Atlas can search jobs, draft proposals, and check contracts in chat.
            Prefer a lighter profile-only setup? Use Integrations → Upwork → Profile &amp; drafts.
          </p>
        </div>
        {upworkServer && (
          <div className="mcp-blender-live-badge">
            <StatusDot connected />
            <span>Live</span>
          </div>
        )}
      </div>

      <div className="settings-card-body">
        {upworkPreset.notes && (
          <p className="mcp-upwork-note">{upworkPreset.notes}</p>
        )}

        <div className="mcp-checklist">
          <p className="mcp-checklist-title">Setup</p>
          <ul>
            {upworkPreset.setup_steps.map((step) => (
              <li key={step}>
                <CheckCircle2 size={15} />
                <span>{step}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="mcp-command-block">
          <div className="mcp-command-label">
            <span>MCP server command</span>
            <CopyButton text={connectCmd} label="Copy command" />
          </div>
          <code className="mcp-command-code">{connectCmd}</code>
          <p className="mcp-command-hint">
            Requires Node.js/npx. After saving credentials below, run{' '}
            <code>npx -y @furkankoykiran/upwork-mcp auth</code> once to complete OAuth in your browser.
          </p>
        </div>

        {expanded === upworkPreset.id ? (
          <ConnectForm
            preset={upworkPreset}
            busy={busy === upworkPreset.id}
            onSubmit={(data) => onConnect(upworkPreset, data)}
            onCancel={() => setExpanded(null)}
          />
        ) : (
          <div className="mcp-blender-actions">
            <button
              type="button"
              className="integration-btn integration-btn-connect mcp-connect-primary"
              disabled={!!busy || loading}
              onClick={() => {
                setExpanded(upworkPreset.id)
                setLocalError(null)
              }}
            >
              <Zap size={15} />
              {upworkServer ? 'Update Upwork credentials' : 'Connect Upwork'}
            </button>
          </div>
        )}
      </div>
    </section>
  )
}

function PresetCard({
  preset,
  expanded,
  busy,
  onConnect,
  setExpanded,
  setLocalError,
}: {
  preset: McpPreset
  expanded: boolean
  busy: boolean
  onConnect: (preset: McpPreset, data: Record<string, string>) => Promise<void>
  setExpanded: (id: string | null) => void
  setLocalError: (msg: string | null) => void
}) {
  const transportLabel =
    preset.transport === 'sse'
      ? `HTTP · ${preset.url || 'URL required'}`
      : `stdio · ${preset.command || 'command'} ${preset.args.join(' ')}`.trim()
  const needsEnv = (preset.env_fields?.length ?? 0) > 0

  return (
    <div className="integration-card mcp-preset-card">
      <div className="integration-card-head">
        <div className="integration-icon" style={{ background: `${preset.color}22`, color: preset.color }}>
          {preset.name[0]}
        </div>
        <div className="integration-info">
          <div className="integration-name-row">
            <span className="integration-name">{preset.name}</span>
            <span className="mcp-transport-tag">{preset.transport.toUpperCase()}</span>
          </div>
          <p className="integration-desc">{preset.description}</p>
          <p className="integration-tools-hint">Default: {transportLabel}</p>
        </div>
      </div>

      <div className="mcp-prereq">
        <span className="mcp-prereq-title">Setup steps</span>
        <ol className="mcp-setup-steps">
          {preset.setup_steps.map((step, i) => (
            <li key={step}>
              <span className="mcp-step-num">{i + 1}</span>
              {step}
            </li>
          ))}
        </ol>
      </div>

      {!expanded ? (
        <div className="mcp-preset-actions">
          {!needsEnv && (
            <button
              type="button"
              className="integration-btn integration-btn-connect"
              disabled={busy}
              onClick={() => onConnect(preset, {
                name: preset.name,
                preset: preset.id,
                transport: preset.transport,
                command: preset.command,
                args: preset.args.join(' '),
                url: preset.url,
              })}
            >
              <Zap size={14} />
              {busy ? 'Connecting…' : 'Quick connect'}
            </button>
          )}
          <button
            type="button"
            className={`integration-btn ${needsEnv ? 'integration-btn-connect' : 'mcp-config-btn'}`}
            disabled={busy}
            onClick={() => {
              setExpanded(preset.id)
              setLocalError(null)
            }}
          >
            <Link2 size={14} />
            {needsEnv ? 'Connect' : 'Configure'}
          </button>
        </div>
      ) : (
        <ConnectForm
          preset={preset}
          busy={busy}
          onSubmit={(data) => onConnect(preset, data)}
          onCancel={() => setExpanded(null)}
        />
      )}
    </div>
  )
}

export default function McpTab({
  presets,
  servers,
  loading,
  error,
  focusPreset = null,
  onConnect,
  onRemove,
  onTest,
  onToggle,
}: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [showOther, setShowOther] = useState(focusPreset === 'unity')
  const [showIntro, setShowIntro] = useState(false)

  useEffect(() => {
    if (focusPreset === 'unity') setShowOther(true)
  }, [focusPreset])

  useEffect(() => {
    if (!focusPreset) return
    const timer = window.setTimeout(() => {
      const el = document.querySelector(`[data-mcp-focus="${focusPreset}"]`)
      el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }, 80)
    return () => window.clearTimeout(timer)
  }, [focusPreset])

  const presetMap = useMemo(() => {
    const map = new Map<string, McpPreset>()
    for (const p of presets) map.set(p.id, p)
    return map
  }, [presets])

  const otherGroups = useMemo(() => {
    const allGrouped = [
      ...BLENDER_PRESET_IDS,
      ...UPWORK_PRESET_IDS,
      ...OTHER_PRESET_GROUPS.flatMap((g) => g.ids),
    ]
    return OTHER_PRESET_GROUPS.map((g) => ({
      title: g.title,
      items: g.ids.map((id) => presetMap.get(id)).filter(Boolean) as McpPreset[],
    })).filter((g) => g.items.length > 0).concat(
      presets
        .filter((p) => !allGrouped.includes(p.id))
        .length
        ? [{ title: 'Other', items: presets.filter((p) => !allGrouped.includes(p.id)) }]
        : [],
    )
  }, [presets, presetMap])

  const handleConnect = async (preset: McpPreset, data: Record<string, string>) => {
    setBusy(preset.id)
    setLocalError(null)
    setSuccess(null)
    const env: Record<string, string> = {}
    for (const [key, value] of Object.entries(data)) {
      if (key.startsWith('env:')) {
        env[key.slice(4)] = value
      }
    }
    try {
      const result = await onConnect({
        name: data.name || preset.name,
        preset: data.preset || preset.id,
        transport: data.transport,
        command: data.command,
        args: data.args ? data.args.split(/\s+/).filter(Boolean) : [],
        url: data.url,
        env: Object.keys(env).length > 0 ? env : undefined,
      })
      setExpanded(null)
      const tools = result?.tool_count ?? 0
      const updated = Boolean((result as McpServer & { updated?: boolean })?.updated)
      setSuccess(
        updated
          ? `Updated ${data.name || preset.name} — ${tools} tool${tools !== 1 ? 's' : ''} ready in chat.`
          : `Connected to ${data.name || preset.name} — ${tools} tool${tools !== 1 ? 's' : ''} ready in chat.`,
      )
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : 'Connection failed')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="integrations-tab mcp-tab">
      <section className="settings-card mcp-intro-card">
        <button
          type="button"
          className="mcp-intro-toggle"
          onClick={() => setShowIntro((v) => !v)}
          aria-expanded={showIntro}
        >
          <div className="settings-card-head mcp-intro-head">
            <div className="settings-card-icon">
              <Info size={18} />
            </div>
            <div className="settings-card-titles">
              <h3 className="settings-card-title">What are Apps &amp; tools?</h3>
              <p className="settings-card-desc">
                Optional bridges so Atlas can control Blender, live Upwork, and similar apps from chat.
              </p>
            </div>
            {showIntro ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </div>
        </button>
        {showIntro && (
          <div className="settings-card-body">
            <p className="mcp-intro-detail">
              Under the hood this uses MCP (Model Context Protocol). Most people only need Blender or live Upwork —
              expand &quot;Other apps&quot; below for Unity or a custom server.
            </p>
          </div>
        )}
      </section>

      {(error || localError) && (
        <div className="integrations-error mcp-error-banner">
          <AlertCircle size={16} />
          <div>
            <strong>{localError ? 'Connection failed' : 'Could not load apps'}</strong>
            <span>{localError || error}</span>
          </div>
        </div>
      )}

      {success && (
        <div className="mcp-success-banner">
          <Check size={16} />
          <span>{success}</span>
        </div>
      )}

      {loading && presets.length === 0 && (
        <p className="integrations-loading">Loading app options…</p>
      )}

      {!loading && presets.length === 0 && !error && (
        <div className="mcp-empty">
          <p>No apps available. Start the backend on port 8000 and reopen Settings.</p>
        </div>
      )}

      {servers.length > 0 && (
        <section className="mcp-connected-section">
          <h4 className="mcp-section-title">Your connections</h4>
          <div className="mcp-connections-list">
            {servers.map((srv) => (
              <ConnectedServerCard
                key={srv.id}
                srv={srv}
                busy={busy === srv.id}
                onTest={onTest}
                onToggle={onToggle}
                onRemove={onRemove}
                onError={setLocalError}
                onSuccess={setSuccess}
              />
            ))}
          </div>
        </section>
      )}

      <div
        data-mcp-focus="blender"
        className={focusPreset === 'blender' ? 'mcp-focus-target' : undefined}
      >
        <BlenderConnectCard
          presets={presets}
          servers={servers}
          loading={loading}
          busy={busy}
          expanded={expanded}
          setExpanded={setExpanded}
          onConnect={handleConnect}
          setLocalError={setLocalError}
        />
      </div>

      <div
        data-mcp-focus="upwork"
        className={focusPreset === 'upwork' ? 'mcp-focus-target' : undefined}
      >
        <UpworkConnectCard
          presets={presets}
          servers={servers}
          loading={loading}
          busy={busy}
          expanded={expanded}
          setExpanded={setExpanded}
          onConnect={handleConnect}
          setLocalError={setLocalError}
        />
      </div>

      {otherGroups.length > 0 && (
        <section
          className={`mcp-other-section${focusPreset === 'unity' ? ' mcp-focus-target' : ''}`}
          data-mcp-focus={focusPreset === 'unity' ? 'unity' : undefined}
        >
          <button
            type="button"
            className="mcp-other-toggle"
            onClick={() => setShowOther((v) => !v)}
          >
            <div>
              <strong>Other apps & custom servers</strong>
              <span>Unity, custom MCP endpoints</span>
            </div>
            {showOther ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </button>
          {showOther && (
            <div className="mcp-other-content">
              {otherGroups.map((group) => (
                <div key={group.title} className="mcp-preset-group">
                  <h4 className="mcp-section-title">{group.title}</h4>
                  <div className="integration-cards">
                    {group.items.map((preset) => (
                      <PresetCard
                        key={preset.id}
                        preset={preset}
                        expanded={expanded === preset.id}
                        busy={busy === preset.id}
                        onConnect={handleConnect}
                        setExpanded={setExpanded}
                        setLocalError={setLocalError}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <div className="mcp-hint">
        <strong>Try after connecting</strong>
        <ul>
          <li>&quot;Create a red cube in Blender at the origin&quot;</li>
          <li>&quot;Search Upwork for TypeScript jobs between $50–$100/hr&quot;</li>
          <li>&quot;List my pending Upwork proposals&quot;</li>
        </ul>
      </div>
    </div>
  )
}
