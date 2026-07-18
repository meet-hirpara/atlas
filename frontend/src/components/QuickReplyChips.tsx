import { useMemo } from 'react'
import { getContextualQuickReplies } from '../utils/quickReplies'

interface Props {
  assistantContent: string
  onSelect: (message: string) => void
  disabled?: boolean
}

export default function QuickReplyChips({ assistantContent, onSelect, disabled }: Props) {
  const chips = useMemo(
    () => getContextualQuickReplies(assistantContent),
    [assistantContent],
  )

  if (chips.length === 0) return null

  return (
    <div className="quick-reply-row" role="group" aria-label="Follow-up suggestions">
      {chips.map((chip) => (
        <button
          key={chip.id}
          type="button"
          className="quick-reply-chip"
          disabled={disabled}
          onClick={() => onSelect(chip.buildMessage(assistantContent))}
        >
          {chip.label}
        </button>
      ))}
    </div>
  )
}
