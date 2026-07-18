import { useMemo } from 'react'
import type { ActivityItem } from '../api'

interface Props {
  items: ActivityItem[]
  compact?: boolean
  fading?: boolean
}

export default function ActivityStatus({ items, compact, fading }: Props) {
  const activeItem = useMemo(
    () => [...items].reverse().find((i) => i.state === 'active'),
    [items],
  )

  if (items.length === 0) return null

  const visibleItems = compact
    ? activeItem
      ? [activeItem]
      : []
    : items.length > 5
      ? items.slice(-5)
      : items

  if (visibleItems.length === 0) return null

  const hasActive = visibleItems.some((item) => item.state === 'active')

  return (
    <div
      className={`activity-lines${hasActive ? ' activity-lines-working' : ''}${fading ? ' activity-lines-fading' : ''}`}
      role="status"
      aria-live="polite"
      aria-atomic="false"
    >
      {visibleItems.map((item) => {
        const isActive = item.state === 'active'

        return (
          <div
            key={item.id}
            className={`activity-line${isActive ? ' is-active' : ' is-done'}`}
          >
            <span key={isActive ? item.phase : item.id} className={isActive ? 'activity-phase-enter' : undefined}>
              <span className={`activity-line-text${isActive ? ' activity-line-shimmer' : ''}`}>
                {item.label}
                {isActive && (
                  <span className="activity-line-dots" aria-hidden>
                    <span />
                    <span />
                    <span />
                  </span>
                )}
              </span>
            </span>
            {item.detail ? (
              <span key={isActive ? `${item.phase}-detail` : item.id} className="activity-line-detail activity-phase-enter">
                {item.detail}
              </span>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
