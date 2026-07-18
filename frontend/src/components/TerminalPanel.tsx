import { useCallback, useRef, useState } from 'react'
import { Terminal, Loader2, Trash2, X } from 'lucide-react'
import { useTerminal } from '../context/TerminalContext'

const MIN_HEIGHT = 120
const DEFAULT_HEIGHT = 200
const MAX_HEIGHT_RATIO = 0.45

export default function TerminalPanel() {
  const { open, running, language, code, result, run, close, clear } = useTerminal()
  const [height, setHeight] = useState(DEFAULT_HEIGHT)
  const dragRef = useRef<{ startY: number; startH: number } | null>(null)

  const onResizeStart = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault()
      dragRef.current = { startY: e.clientY, startH: height }
      const onMove = (ev: PointerEvent) => {
        if (!dragRef.current) return
        const maxH = Math.min(window.innerHeight * MAX_HEIGHT_RATIO, 420)
        const delta = dragRef.current.startY - ev.clientY
        const next = Math.min(maxH, Math.max(MIN_HEIGHT, dragRef.current.startH + delta))
        setHeight(next)
      }
      const onUp = () => {
        dragRef.current = null
        window.removeEventListener('pointermove', onMove)
        window.removeEventListener('pointerup', onUp)
      }
      window.addEventListener('pointermove', onMove)
      window.addEventListener('pointerup', onUp)
    },
    [height],
  )

  if (!open) return null

  const output = result
    ? [result.stdout, result.stderr].filter(Boolean).join(result.stdout && result.stderr ? '\n' : '')
    : ''

  return (
    <div className="terminal-drawer" style={{ height }}>
      <div
        className="terminal-resize-handle"
        onPointerDown={onResizeStart}
        role="separator"
        aria-orientation="horizontal"
        aria-label="Resize terminal"
      />
      <div className="terminal-panel">
        <div className="terminal-panel-header">
          <div className="terminal-panel-title">
            <Terminal size={16} />
            <span>Terminal</span>
            {language && <span className="terminal-lang-badge">{language}</span>}
            {running && <Loader2 size={14} className="terminal-spin" />}
            {result && !running && (
              <span className={`terminal-exit terminal-exit-${result.exit_code === 0 ? 'ok' : 'err'}`}>
                exit {result.exit_code}
              </span>
            )}
          </div>
          <div className="terminal-panel-actions">
            {code && !running && (
              <button type="button" className="terminal-action-btn" onClick={() => run(language, code)} title="Re-run">
                Re-run
              </button>
            )}
            <button type="button" className="terminal-action-btn" onClick={clear} title="Clear">
              <Trash2 size={14} />
            </button>
            <button type="button" className="terminal-action-btn" onClick={close} title="Close">
              <X size={16} />
            </button>
          </div>
        </div>

        {code && (
          <div className="terminal-code-preview">
            <span className="terminal-prompt">$</span>
            <code>{code.split('\n')[0]}{code.includes('\n') ? ' …' : ''}</code>
          </div>
        )}

        <div className="terminal-output" role="log" aria-live="polite">
          {running ? (
            <span className="terminal-muted">Running…</span>
          ) : output ? (
            <pre>{output}</pre>
          ) : (
            <span className="terminal-muted">Run code from a message to see output here.</span>
          )}
        </div>
      </div>
    </div>
  )
}
