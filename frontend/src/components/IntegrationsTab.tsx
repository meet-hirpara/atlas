import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, Check, ChevronDown, ChevronUp, ExternalLink, Info, Search, Unlink } from 'lucide-react'
import type { ConnectionStatus, ProviderCatalogItem } from '../connections'
import { fetchProviders } from '../connections'

interface Props {
  connections: ConnectionStatus[]
  loading: boolean
  error: string | null
  onConnect: (provider: string, data: Record<string, string>) => Promise<void>
  onDisconnect: (provider: string) => Promise<void>
  /** Jump to Apps & tools → live Upwork API setup */
  onOpenLiveUpwork?: () => void
}

function statusLabel(status: ProviderCatalogItem['status']): string | null {
  switch (status) {
    case 'coming_soon':
      return 'Coming soon'
    case 'oauth_required':
      return 'OAuth required'
    case 'manual_token':
      return 'Manual setup'
    default:
      return null
  }
}

function StatusBadge({ status }: { status: ProviderCatalogItem['status'] }) {
  const label = statusLabel(status)
  if (!label) return null
  return (
    <span className={`integration-badge integration-status-${status}`}>
      {label}
    </span>
  )
}

function ConnectForm({
  provider,
  onSubmit,
  onCancel,
  busy,
  formError,
  mode = 'connect',
}: {
  provider: ProviderCatalogItem
  onSubmit: (data: Record<string, string>) => Promise<void>
  onCancel: () => void
  busy: boolean
  formError: string | null
  mode?: 'connect' | 'update'
}) {
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {}
    for (const f of provider.fields) {
      init[f.key] = f.default || ''
    }
    return init
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await onSubmit(values)
  }

  return (
    <form className="connect-form" onSubmit={handleSubmit}>
      <p className="connect-form-title">
        {mode === 'update' ? `Update ${provider.name} credentials` : `Enter your ${provider.name} credentials`}
      </p>
      {provider.id === 'upwork' && (
        <div className="connect-form-notice">
          <Info size={14} />
          <div>
            <span>
              You chose <strong>Profile &amp; drafts</strong> — saves your profile for proposal help and public job search in chat.
              Need live jobs and proposals from your Upwork account? Use the chooser above to switch to Live API.
            </span>
          </div>
        </div>
      )}
      {provider.setup_help && (
        <div className="connect-form-notice">
          <Info size={14} />
          <div>
            <span>{provider.setup_help}</span>
            {provider.docs_url && (
              <a href={provider.docs_url} target="_blank" rel="noopener noreferrer" className="connect-docs-link">
                Platform docs <ExternalLink size={12} />
              </a>
            )}
          </div>
        </div>
      )}
      {formError && (
        <div className="connect-form-error">
          <AlertCircle size={14} />
          <span>{formError}</span>
        </div>
      )}
      {provider.fields.map((field) => (
        <label key={field.key} className="connect-field">
          <span className="connect-field-label">
            {field.label}
            {!field.required ? <span className="connect-field-optional">Optional</span> : null}
          </span>
          <input
            type={field.type === 'password' ? 'password' : field.type === 'email' ? 'email' : 'text'}
            className={field.type === 'password' ? 'connect-input-secret' : undefined}
            value={values[field.key] ?? ''}
            onChange={(e) => setValues((v) => ({ ...v, [field.key]: e.target.value }))}
            placeholder={field.type === 'password' ? '••••••••' : field.placeholder}
            required={field.required && mode === 'connect'}
            disabled={busy}
            autoComplete="off"
            spellCheck={false}
          />
          {field.hint && <span className="connect-field-hint">{field.hint}</span>}
        </label>
      ))}
      <div className="connect-form-actions">
        <button type="button" className="connect-cancel" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button type="submit" className="connect-submit" disabled={busy}>
          {busy
            ? mode === 'update'
              ? 'Updating…'
              : 'Connecting…'
            : mode === 'update'
              ? 'Update credentials'
              : provider.category === 'freelance'
                ? 'Save profile & enable assistant'
                : provider.status === 'coming_soon'
                  ? 'Save profile'
                  : 'Connect'}
        </button>
      </div>
    </form>
  )
}

export default function IntegrationsTab({
  connections,
  loading,
  error,
  onConnect,
  onDisconnect,
  onOpenLiveUpwork,
}: Props) {
  const [providers, setProviders] = useState<ProviderCatalogItem[]>([])
  const [catalogLoading, setCatalogLoading] = useState(true)
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [activeCategory, setActiveCategory] = useState<string>('all')
  /** null = chooser, profile = connect form, live = handoff */
  const [upworkPath, setUpworkPath] = useState<'chooser' | 'profile' | null>('chooser')

  useEffect(() => {
    let cancelled = false
    const load = () => {
      setCatalogLoading(true)
      setCatalogError(null)
      fetchProviders()
        .then((items) => {
          if (cancelled) return
          setProviders(items)
          if (items.length === 0) {
            setCatalogError('No integrations available. Start the backend (port 8000) and click Retry.')
          }
        })
        .catch((e) => {
          if (cancelled) return
          setProviders([])
          setCatalogError(e instanceof Error ? e.message : 'Failed to load integrations')
        })
        .finally(() => {
          if (!cancelled) setCatalogLoading(false)
        })
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const retryCatalog = () => {
    setCatalogLoading(true)
    setCatalogError(null)
    fetchProviders()
      .then((items) => {
        setProviders(items)
        if (items.length === 0) {
          setCatalogError('No integrations available. Start the backend (port 8000) and click Retry.')
        }
      })
      .catch((e) => {
        setProviders([])
        setCatalogError(e instanceof Error ? e.message : 'Failed to load integrations')
      })
      .finally(() => setCatalogLoading(false))
  }

  const categories = useMemo(() => {
    const cats = new Map<string, string>()
    for (const p of providers) {
      cats.set(p.category, p.category_label)
    }
    return Array.from(cats.entries())
  }, [providers])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return providers.filter((p) => {
      if (activeCategory !== 'all' && p.category !== activeCategory) return false
      if (!q) return true
      return (
        p.name.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q) ||
        p.tool_summary.toLowerCase().includes(q) ||
        p.id.includes(q)
      )
    })
  }, [providers, search, activeCategory])

  const grouped = useMemo(() => {
    const map = new Map<string, ProviderCatalogItem[]>()
    for (const p of filtered) {
      const list = map.get(p.category) || []
      list.push(p)
      map.set(p.category, list)
    }
    return map
  }, [filtered])

  const getStatus = (id: string) =>
    connections.find((c) => c.provider === id) ?? { provider: id, connected: false, label: '', connected_at: null }

  const connectedCount = connections.filter((c) => c.connected).length

  const handleConnect = async (provider: ProviderCatalogItem, data: Record<string, string>) => {
    setBusy(provider.id)
    setFormError(null)
    setSuccess(null)
    try {
      await onConnect(provider.id, data)
      setExpanded(null)
      setSuccess(`${provider.name} connected successfully.`)
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Connection failed')
    } finally {
      setBusy(null)
    }
  }

  const handleDisconnect = async (id: string, name: string) => {
    setBusy(id)
    setFormError(null)
    setSuccess(null)
    try {
      await onDisconnect(id)
      setSuccess(`${name} disconnected.`)
    } catch (e) {
      setFormError(e instanceof Error ? e.message : 'Disconnect failed')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="integrations-tab">
      <p className="integrations-intro">
        Connect a service, then use it in chat — Atlas picks it up automatically.
        {connectedCount > 0 && <span className="integrations-count"> {connectedCount} connected</span>}
      </p>

      <div className="integrations-toolbar">
        <div className="integrations-search">
          <Search size={14} />
          <input
            type="search"
            placeholder="Search integrations…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="integrations-categories">
          <button
            type="button"
            className={`integrations-cat ${activeCategory === 'all' ? 'integrations-cat-active' : ''}`}
            onClick={() => setActiveCategory('all')}
          >
            All
          </button>
          {categories.map(([cat, label]) => (
            <button
              key={cat}
              type="button"
              className={`integrations-cat ${activeCategory === cat ? 'integrations-cat-active' : ''}`}
              onClick={() => setActiveCategory(cat)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {(error || catalogError) && !expanded && (
        <div className="integrations-error">
          <AlertCircle size={16} />
          <span>{catalogError || error}</span>
          {catalogError && (
            <button type="button" className="integration-btn mcp-config-btn" onClick={retryCatalog}>
              Retry
            </button>
          )}
        </div>
      )}

      {success && (
        <div className="mcp-success-banner">
          <Check size={16} />
          <span>{success}</span>
        </div>
      )}

      {(loading || catalogLoading) && <p className="integrations-loading">Loading integrations…</p>}

      {Array.from(grouped.entries()).map(([category, items]) => (
        <div key={category} className="integration-category">
          <h4 className="integration-category-title">{items[0]?.category_label || category}</h4>
          <div className="integration-cards">
            {items.map((provider) => {
              const status = getStatus(provider.id)
              const isExpanded = expanded === provider.id
              const isBusy = busy === provider.id

              return (
                <div
                  key={provider.id}
                  className={`integration-card ${status.connected ? 'integration-connected' : ''} ${isExpanded ? 'integration-card-expanded' : ''}`}
                >
                  <button
                    type="button"
                    className="integration-card-head integration-card-toggle"
                    disabled={isBusy}
                    onClick={() => {
                      const next = isExpanded ? null : provider.id
                      setExpanded(next)
                      setFormError(null)
                      if (provider.id === 'upwork' && next) setUpworkPath('chooser')
                    }}
                    aria-expanded={isExpanded}
                  >
                    <div
                      className="integration-icon"
                      style={{ background: `${provider.color}22`, color: provider.color }}
                    >
                      {provider.name[0]}
                    </div>
                    <div className="integration-info">
                      <div className="integration-name-row">
                        <span className="integration-name">{provider.name}</span>
                        <StatusBadge status={provider.status} />
                        {status.connected && (
                          <span className="integration-badge">
                            <Check size={12} /> Connected
                          </span>
                        )}
                        {!status.connected && !isExpanded && (
                          <span className="integration-setup-hint">
                            {provider.status === 'coming_soon' ? 'Click to save profile' : 'Click to enter credentials'}
                          </span>
                        )}
                      </div>
                      <p className="integration-desc">{provider.description}</p>
                      {provider.setup_help && !isExpanded && !status.connected && (
                        <p className="integration-setup-help">{provider.setup_help}</p>
                      )}
                      <p className="integration-tools-hint">{provider.tool_summary}</p>
                      {provider.category === 'freelance' && provider.capabilities?.length > 0 && (
                        <ul className="integration-capabilities">
                          {provider.capabilities.slice(0, 3).map((cap) => (
                            <li key={cap}>{cap}</li>
                          ))}
                        </ul>
                      )}
                      {status.connected && status.label && (
                        <p className="integration-account">{status.label}</p>
                      )}
                    </div>
                    {!status.connected && (
                      <span className="integration-chevron" aria-hidden>
                        {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                      </span>
                    )}
                  </button>

                  {status.connected && (
                    <div className="integration-actions">
                      <button
                        type="button"
                        className="integration-btn mcp-config-btn"
                        disabled={isBusy}
                        onClick={() => {
                          setExpanded(isExpanded ? null : provider.id)
                          setFormError(null)
                        }}
                      >
                        {isExpanded ? 'Hide form' : 'Update credentials'}
                      </button>
                      <button
                        type="button"
                        className="integration-btn integration-btn-disconnect"
                        disabled={isBusy}
                        onClick={() => handleDisconnect(provider.id, provider.name)}
                      >
                        <Unlink size={14} />
                        {isBusy ? 'Disconnecting…' : 'Disconnect'}
                      </button>
                    </div>
                  )}

                  {isExpanded && provider.id === 'upwork' && !status.connected && upworkPath === 'chooser' && (
                    <div className="upwork-chooser">
                      <p className="upwork-chooser-title">How do you want to use Upwork?</p>
                      <button
                        type="button"
                        className="upwork-chooser-option"
                        onClick={() => setUpworkPath('profile')}
                      >
                        <strong>Profile &amp; drafts</strong>
                        <span>Save your profile for proposal help and public job search. Fastest setup.</span>
                      </button>
                      <button
                        type="button"
                        className="upwork-chooser-option"
                        onClick={() => {
                          setExpanded(null)
                          onOpenLiveUpwork?.()
                        }}
                      >
                        <strong>Live account API</strong>
                        <span>Search your real jobs, proposals, and contracts from chat. Needs API keys.</span>
                      </button>
                    </div>
                  )}

                  {isExpanded &&
                    !(provider.id === 'upwork' && !status.connected && upworkPath === 'chooser') && (
                    <ConnectForm
                      provider={provider}
                      mode={status.connected ? 'update' : 'connect'}
                      busy={isBusy}
                      formError={formError}
                      onSubmit={(data) => handleConnect(provider, data)}
                      onCancel={() => {
                        if (provider.id === 'upwork' && !status.connected) {
                          setUpworkPath('chooser')
                        } else {
                          setExpanded(null)
                        }
                        setFormError(null)
                      }}
                    />
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}

      {!catalogLoading && !catalogError && filtered.length === 0 && providers.length > 0 && (
        <p className="integrations-empty">No integrations match your search.</p>
      )}

      {!catalogLoading && catalogError && providers.length === 0 && (
        <div className="mcp-empty">
          <p>{catalogError}</p>
        </div>
      )}
    </div>
  )
}
