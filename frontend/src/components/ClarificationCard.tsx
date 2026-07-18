import { useState } from 'react'
import { Send } from 'lucide-react'
import type { ClarificationRequest } from '../utils/clarification'

interface Props {
  data: ClarificationRequest
  onSubmit: (answer: string) => void
  disabled?: boolean
  answered?: string
}

export default function ClarificationCard({ data, onSubmit, disabled, answered }: Props) {
  const [custom, setCustom] = useState('')
  const [selected, setSelected] = useState<string | null>(answered ?? null)

  const handleOption = (option: string) => {
    if (disabled || answered) return
    setSelected(option)
    onSubmit(option)
  }

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const text = custom.trim()
    if (!text || disabled || answered) return
    setSelected(text)
    onSubmit(text)
  }

  const isAnswered = Boolean(answered || selected)

  return (
    <div className={`clarification-card${isAnswered ? ' clarification-card-answered' : ''}`}>
      <p className="clarification-question">{data.question}</p>
      <div className="clarification-options">
        {data.options.map((option) => (
          <button
            key={option}
            type="button"
            className={`clarification-option${
              (answered ?? selected) === option ? ' clarification-option-selected' : ''
            }`}
            onClick={() => handleOption(option)}
            disabled={disabled || isAnswered}
          >
            {option}
          </button>
        ))}
      </div>
      {data.allowCustom && !isAnswered && (
        <form className="clarification-custom" onSubmit={handleCustomSubmit}>
          <input
            type="text"
            className="clarification-custom-input"
            placeholder="Or describe your own…"
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            disabled={disabled}
          />
          <button
            type="submit"
            className="clarification-custom-submit"
            disabled={disabled || !custom.trim()}
            aria-label="Submit custom answer"
          >
            <Send size={14} />
          </button>
        </form>
      )}
      {isAnswered && (
        <p className="clarification-answered-note">
          You chose: <strong>{answered ?? selected}</strong>
        </p>
      )}
    </div>
  )
}
