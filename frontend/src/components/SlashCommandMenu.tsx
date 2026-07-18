import { useEffect, useRef } from 'react'
import type { SlashCommand } from '../utils/slashCommands'
import { groupSlashCommands } from '../utils/slashCommands'

interface Props {
  commands: SlashCommand[]
  selectedIndex: number
  query: string
  onSelect: (command: SlashCommand) => void
  onHover: (index: number) => void
}

export default function SlashCommandMenu({
  commands,
  selectedIndex,
  query,
  onSelect,
  onHover,
}: Props) {
  const listRef = useRef<HTMLDivElement>(null)
  const grouped = !query.trim() ? groupSlashCommands(commands) : null

  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-index="${selectedIndex}"]`)
    el?.scrollIntoView({ block: 'nearest' })
  }, [selectedIndex])

  if (commands.length === 0) {
    return (
      <div className="slash-menu" role="listbox" aria-label="Slash commands">
        <p className="slash-menu-empty">No matching commands</p>
      </div>
    )
  }

  const renderItem = (cmd: SlashCommand, i: number) => {
    const Icon = cmd.icon
    return (
      <button
        key={cmd.name}
        type="button"
        role="option"
        aria-selected={i === selectedIndex}
        data-index={i}
        className={`slash-menu-item${i === selectedIndex ? ' selected' : ''}`}
        onMouseEnter={() => onHover(i)}
        onClick={() => onSelect(cmd)}
      >
        <span className="slash-menu-icon">
          <Icon size={16} />
        </span>
        <span className="slash-menu-text">
          <strong>{cmd.label}</strong>
          <small>
            {cmd.description}
            {cmd.acceptsArgs && cmd.argPrompt ? ` — ${cmd.argPrompt}` : ''}
          </small>
        </span>
      </button>
    )
  }

  return (
    <div className="slash-menu" role="listbox" aria-label="Slash commands" ref={listRef}>
      {!query.trim() && (
        <p className="slash-menu-hint">Pick a command — ones with a prompt will ask for details next.</p>
      )}
      {grouped ? (
        grouped.map((group) => (
          <div key={group.category} className="slash-menu-section">
            <p className="slash-menu-section-label">{group.label}</p>
            {group.commands.map((cmd) => {
              const i = commands.indexOf(cmd)
              return renderItem(cmd, i)
            })}
          </div>
        ))
      ) : (
        commands.map((cmd, i) => renderItem(cmd, i))
      )}
    </div>
  )
}
