import type { SlashCommand } from '../utils/slashCommands'

interface Props {
  command: SlashCommand
  suggestions?: string[]
  onSuggestionClick: (suggestion: string) => void
  disabled?: boolean
}

export default function SlashCommandHints({
  command,
  suggestions: suggestionsOverride,
  onSuggestionClick,
  disabled,
}: Props) {
  const suggestions = suggestionsOverride ?? command.suggestions ?? []

  return (
    <div className="slash-hints" role="region" aria-label={`${command.label} suggestions`}>
      <p className="slash-hints-prompt">{command.argPrompt}</p>
      {suggestions.length > 0 && (
        <div className="slash-hints-chips">
          {suggestions.map((suggestion, index) => (
            <button
              key={`${index}-${suggestion}`}
              type="button"
              className="slash-hints-chip"
              disabled={disabled}
              title={`Send: ${suggestion}`}
              onClick={() => onSuggestionClick(suggestion)}
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}
      <p className="slash-hints-note">Click a suggestion to send, or type your own request above.</p>
    </div>
  )
}
