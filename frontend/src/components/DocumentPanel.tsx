import { useEffect, useRef } from 'react'
import { FileText, PanelRightClose, PanelRight, X } from 'lucide-react'
import type { DocumentCitation } from '../api'
import type { UploadedDocument } from '../documents'
import { formatFileSize, getDocumentFileUrl } from '../documents'
import { highlightSnippet } from '../utils/docCitations'

interface Props {
  documents: UploadedDocument[]
  open: boolean
  onToggle: () => void
  onRemove?: (id: string) => void
  activeCitation?: DocumentCitation | null
  onSelectDocument?: (docId: string) => void
}

function statusLabel(doc: UploadedDocument) {
  if (doc.status === 'ready') return `${formatFileSize(doc.file_size)} · ${doc.page_count} pg`
  if (doc.status === 'failed') return doc.error_message || 'Failed'
  if (doc.status === 'processing') return 'Processing…'
  return 'Queued…'
}

function DocumentViewer({
  citation,
  documents,
}: {
  citation: DocumentCitation
  documents: UploadedDocument[]
}) {
  const excerptRef = useRef<HTMLDivElement>(null)
  const doc = documents.find((d) => d.id === citation.document_id)
  const pageLabel =
    citation.page_end && citation.page_end !== citation.page
      ? `Pages ${citation.page}–${citation.page_end}`
      : `Page ${citation.page}`
  const highlight = highlightSnippet(citation.content || '', citation.snippet || '')

  useEffect(() => {
    excerptRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [citation.id])

  if (!doc || doc.status !== 'ready') {
    return (
      <div className="doc-viewer-empty">
        <p>Document not available for preview.</p>
      </div>
    )
  }

  return (
    <div className="doc-viewer">
      <div className="doc-viewer-meta">
        <span className="doc-viewer-filename" title={citation.filename}>
          {citation.filename}
        </span>
        <span className="doc-viewer-page">{pageLabel}</span>
      </div>

      <div className="doc-viewer-pdf">
        <iframe
          key={`${citation.document_id}-${citation.page}`}
          title={`${citation.filename} page ${citation.page}`}
          src={`${getDocumentFileUrl(citation.document_id)}#page=${citation.page}`}
          className="doc-viewer-iframe"
        />
      </div>

      <div className="doc-viewer-excerpt" ref={excerptRef}>
        <div className="doc-viewer-excerpt-label">Referenced passage</div>
        <p className="doc-viewer-excerpt-text">
          {highlight.before}
          {highlight.match ? <mark className="doc-highlight">{highlight.match}</mark> : null}
          {highlight.after}
        </p>
      </div>
    </div>
  )
}

export default function DocumentPanel({
  documents,
  open,
  onToggle,
  onRemove,
  activeCitation,
  onSelectDocument,
}: Props) {
  if (!documents.length) return null

  const readyCount = documents.filter((d) => d.status === 'ready').length

  if (!open) {
    return (
      <aside className="doc-panel doc-panel-collapsed" aria-label="Documents">
        <button
          type="button"
          className="doc-panel-expand"
          onClick={onToggle}
          title="Show documents"
          aria-expanded={false}
        >
          <PanelRight size={18} />
          {readyCount > 0 && <span className="doc-panel-badge">{readyCount}</span>}
        </button>
      </aside>
    )
  }

  return (
    <aside className="doc-panel" aria-label="Documents">
      <header className="doc-panel-header">
        <div className="doc-panel-title">
          <FileText size={16} />
          <span>Documents</span>
          <span className="doc-panel-count">{documents.length}</span>
        </div>
        <button
          type="button"
          className="doc-panel-close"
          onClick={onToggle}
          title="Collapse panel"
          aria-expanded
        >
          <PanelRightClose size={18} />
        </button>
      </header>

      <div className="doc-panel-body">
        {activeCitation ? (
          <DocumentViewer citation={activeCitation} documents={documents} />
        ) : (
          <>
            <ul className="doc-panel-list">
              {documents.map((doc) => (
                <li key={doc.id} className={`doc-panel-item doc-panel-item-${doc.status}`}>
                  <button
                    type="button"
                    className="doc-panel-item-main"
                    onClick={() => doc.status === 'ready' && onSelectDocument?.(doc.id)}
                    disabled={doc.status !== 'ready'}
                  >
                    <FileText size={14} className="doc-panel-item-icon" />
                    <div className="doc-panel-item-text">
                      <span className="doc-panel-item-name" title={doc.filename}>
                        {doc.filename}
                      </span>
                      <span className="doc-panel-item-meta">{statusLabel(doc)}</span>
                    </div>
                  </button>
                  {onRemove && (
                    <button
                      type="button"
                      className="doc-panel-item-remove"
                      onClick={() => onRemove(doc.id)}
                      aria-label={`Remove ${doc.filename}`}
                    >
                      <X size={14} />
                    </button>
                  )}
                </li>
              ))}
            </ul>
            <p className="doc-panel-hint">
              Click a citation in the answer to jump to the matching passage here.
            </p>
          </>
        )}
      </div>
    </aside>
  )
}
