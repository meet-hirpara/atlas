import { useState } from 'react'
import { Check, Copy, RotateCcw, Download, BookmarkPlus } from 'lucide-react'

interface Props {
  content: string
  onRetry?: () => void
  onExportMd?: () => void
  onSaveProposal?: () => void
  status?: 'ok' | 'stopped' | 'failed'
}

export default function MessageActions({
  content,
  onRetry,
  onExportMd,
  onSaveProposal,
  status = 'ok',
}: Props) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // ignore
    }
  }

  return (
    <div className="message-actions">
      {status === 'stopped' && (
        <span className="message-status-chip stopped">Stopped</span>
      )}
      {status === 'failed' && (
        <span className="message-status-chip failed">Failed</span>
      )}
      {onRetry && (status === 'stopped' || status === 'failed') && (
        <button
          type="button"
          className="message-action-btn"
          onClick={onRetry}
          aria-label="Retry"
          title="Retry"
        >
          <RotateCcw size={15} />
        </button>
      )}
      {onSaveProposal && (
        <button
          type="button"
          className="message-action-btn"
          onClick={onSaveProposal}
          aria-label="Save as proposal"
          title="Save as proposal"
        >
          <BookmarkPlus size={15} />
        </button>
      )}
      {onExportMd && (
        <button
          type="button"
          className="message-action-btn"
          onClick={onExportMd}
          aria-label="Export chat"
          title="Export chat"
        >
          <Download size={15} />
        </button>
      )}
      <button
        type="button"
        className="message-action-btn"
        onClick={handleCopy}
        aria-label={copied ? 'Copied' : 'Copy message'}
        title={copied ? 'Copied!' : 'Copy'}
      >
        {copied ? <Check size={15} /> : <Copy size={15} />}
      </button>
    </div>
  )
}
