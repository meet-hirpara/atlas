interface Props {
  title: string
  body: string
  actionLabel?: string
  onAction?: () => void
  compact?: boolean
}

/** Warm empty surface with one clear CTA — Atlas voice, not “No data”. */
export default function EmptyState({ title, body, actionLabel, onAction, compact }: Props) {
  return (
    <div className={`atlas-empty${compact ? ' atlas-empty-compact' : ''}`}>
      <p className="atlas-empty-title">{title}</p>
      <p className="atlas-empty-body">{body}</p>
      {actionLabel && onAction && (
        <button type="button" className="atlas-empty-cta" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  )
}
