import { useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, ExternalLink, Telescope } from 'lucide-react'
import type { ActivityItem, ResearchSource, ResearchStatus } from '../api'

interface Props {
  status: ResearchStatus | null
  steps: ActivityItem[]
  sources: ResearchSource[]
  reportStarted: boolean
  collapsed?: boolean
}

function phaseTitle(phase: ResearchStatus['phase'] | undefined): string {
  const map: Record<ResearchStatus['phase'], string> = {
    planning: 'Planning research',
    searching: 'Searching the web',
    analyzing: 'Analyzing sources',
    writing: 'Writing report',
    complete: 'Research complete',
  }
  return phase ? map[phase] : 'Researching'
}

function faviconUrl(domain: string): string {
  if (!domain) return ''
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=32`
}

export default function DeepResearchPanel({
  status,
  steps,
  sources,
  reportStarted,
  collapsed: collapsedProp,
}: Props) {
  const [manualOpen, setManualOpen] = useState(true)

  const progress = useMemo(() => {
    if (!status?.total) return status?.phase === 'complete' ? 100 : 8
    return Math.min(100, Math.round((status.step / status.total) * 100))
  }, [status])

  const uniqueSources = useMemo(() => {
    const seen = new Set<string>()
    return sources.filter((s) => {
      const key = s.url || s.title
      if (!key || seen.has(key)) return false
      seen.add(key)
      return true
    })
  }, [sources])

  const timeline = useMemo(() => {
    const grouped: { phase: string; items: ActivityItem[] }[] = []
    for (const item of steps) {
      const last = grouped[grouped.length - 1]
      if (last && last.phase === item.phase) {
        last.items.push(item)
      } else {
        grouped.push({ phase: item.phase, items: [item] })
      }
    }
    return grouped
  }, [steps])

  const isComplete = status?.phase === 'complete'
  const showCollapsed = collapsedProp ?? (reportStarted && !manualOpen)
  const panelOpen = !showCollapsed && manualOpen

  return (
    <div className={`deep-research-panel${reportStarted ? ' deep-research-panel-reporting' : ''}`}>
      <div className="deep-research-header">
        <div className="deep-research-header-main">
          <span className="deep-research-icon" aria-hidden>
            <Telescope size={16} />
          </span>
          <div className="deep-research-header-text">
            <span className="deep-research-title">
              {isComplete ? 'Research complete' : 'Researching…'}
            </span>
            <span className="deep-research-subtitle">
              {status?.message || phaseTitle(status?.phase)}
              {uniqueSources.length > 0 && (
                <span className="deep-research-source-count">
                  {' · '}
                  {uniqueSources.length} source{uniqueSources.length === 1 ? '' : 's'}
                </span>
              )}
            </span>
          </div>
        </div>
        <button
          type="button"
          className="deep-research-toggle"
          onClick={() => setManualOpen((v) => !v)}
          aria-expanded={panelOpen}
        >
          {panelOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          <span>Research process</span>
        </button>
      </div>

      <div className="deep-research-progress" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
        <div className="deep-research-progress-track">
          <div className="deep-research-progress-fill" style={{ width: `${progress}%` }} />
        </div>
        {status?.total ? (
          <span className="deep-research-progress-label">
            Step {Math.min(status.step, status.total)} of {status.total}
          </span>
        ) : null}
      </div>

      {status?.query && status.phase === 'searching' && (
        <div className="deep-research-query">
          <span className="deep-research-query-label">Current query</span>
          <span className="deep-research-query-text">{status.query}</span>
        </div>
      )}

      {panelOpen && (
        <div className="deep-research-body">
          {timeline.length > 0 && (
            <ol className="deep-research-steps">
              {timeline.map((group) => (
                <li key={group.phase} className={`deep-research-step deep-research-step-${group.phase}`}>
                  <span className="deep-research-step-phase">
                    {phaseTitle(group.phase as ResearchStatus['phase'])}
                  </span>
                  <ul className="deep-research-step-events">
                    {group.items.slice(-3).map((item) => (
                      <li
                        key={item.id}
                        className={item.state === 'active' ? 'is-active' : 'is-done'}
                      >
                        {item.detail || item.label}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          )}

          {uniqueSources.length > 0 && (
            <div className="deep-research-sources">
              <span className="deep-research-sources-heading">Sources found</span>
              <ul className="deep-research-source-list">
                {uniqueSources.slice(0, 12).map((source) => (
                  <li key={source.url || source.title} className="deep-research-source-card">
                    {source.domain ? (
                      <img
                        className="deep-research-source-favicon"
                        src={faviconUrl(source.domain)}
                        alt=""
                        width={16}
                        height={16}
                        loading="lazy"
                      />
                    ) : (
                      <span className="deep-research-source-favicon-placeholder" aria-hidden />
                    )}
                    <div className="deep-research-source-meta">
                      <span className="deep-research-source-title">{source.title}</span>
                      {source.domain && (
                        <span className="deep-research-source-domain">{source.domain}</span>
                      )}
                    </div>
                    {source.url && (
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="deep-research-source-link"
                        aria-label={`Open ${source.title}`}
                      >
                        <ExternalLink size={12} />
                      </a>
                    )}
                  </li>
                ))}
              </ul>
              {uniqueSources.length > 12 && (
                <span className="deep-research-sources-more">
                  +{uniqueSources.length - 12} more sources
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
