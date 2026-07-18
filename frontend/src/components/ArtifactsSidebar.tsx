import { useEffect, useState } from 'react'
import { Layers, X, RefreshCw } from 'lucide-react'
import { syncArtifacts, type Artifact } from '../workspace'
import EmptyState from './EmptyState'
import LoadingSkeleton from './LoadingSkeleton'

interface Props {
  sessionId: string | null
  open: boolean
  onToggle: () => void
  onInsert?: (content: string) => void
}

export default function ArtifactsSidebar({ sessionId, open, onToggle, onInsert }: Props) {
  const [items, setItems] = useState<Artifact[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    if (!sessionId) {
      setItems([])
      return
    }
    setLoading(true)
    setError(null)
    try {
      setItems(await syncArtifacts(sessionId))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load artifacts')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open && sessionId) void load()
  }, [open, sessionId])

  if (!open) {
    return (
      <button type="button" className="artifacts-rail-toggle" onClick={onToggle} title="Saved outputs">
        <Layers size={16} />
      </button>
    )
  }

  return (
    <aside className="artifacts-sidebar">
      <div className="artifacts-sidebar-head">
        <strong>Saved outputs</strong>
        <div>
          <button type="button" onClick={() => void load()} disabled={loading || !sessionId} title="Refresh">
            <RefreshCw size={14} />
          </button>
          <button type="button" onClick={onToggle} aria-label="Close saved outputs">
            <X size={14} />
          </button>
        </div>
      </div>
      {!sessionId ? (
        <EmptyState
          compact
          title="Pick a chat first"
          body="Diagrams, code, and proposals from the conversation will show up here."
        />
      ) : error ? (
        <p className="workspace-empty error">{error}</p>
      ) : loading && items.length === 0 ? (
        <LoadingSkeleton rows={3} />
      ) : items.length === 0 ? (
        <EmptyState
          compact
          title="Nothing captured yet"
          body="When Atlas draws diagrams or ships multi-file code, they’ll land here."
          actionLabel="Refresh"
          onAction={() => void load()}
        />
      ) : (
        <ul className="artifacts-list">
          {items.map((a) => (
            <li key={a.id}>
              <span className="artifact-kind">{a.kind}</span>
              <strong>{a.title}</strong>
              <pre>{a.content.slice(0, 280)}{a.content.length > 280 ? '…' : ''}</pre>
              {onInsert && (
                <button type="button" onClick={() => onInsert(a.content)}>Reuse</button>
              )}
            </li>
          ))}
        </ul>
      )}
    </aside>
  )
}
