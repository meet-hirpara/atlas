interface Props {
  rows?: number
  className?: string
}

/** Theme-aware shimmer bars for panel / admin loading. */
export default function LoadingSkeleton({ rows = 4, className = '' }: Props) {
  return (
    <div className={`atlas-skeleton${className ? ` ${className}` : ''}`} aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          className="atlas-skeleton-bar"
          style={{ width: `${88 - (i % 3) * 12}%` }}
        />
      ))}
    </div>
  )
}
