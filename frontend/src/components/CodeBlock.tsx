import { useState } from 'react'
import { Check, Copy, Play, Loader2 } from 'lucide-react'
import { canRunLanguage } from '../utils/codeRunner'
import { useTerminal } from '../context/TerminalContext'

interface Props {
  code: string
  language?: string
  className?: string
  filePath?: string
}

export default function CodeBlock({ code, language, className, filePath }: Props) {
  const [copied, setCopied] = useState(false)
  const { run, running, code: runningCode, open } = useTerminal()
  const runnable = canRunLanguage(language)
  const isRunningThis = running && runningCode === code && open

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // fallback ignored
    }
  }

  const handleRun = () => {
    if (!language || !runnable) return
    void run(language, code)
  }

  return (
    <div className="code-block">
      <div className="code-block-header">
        <span className="code-lang" title={filePath || language}>
          {filePath || language || 'code'}
        </span>
        <div className="code-block-actions">
          {runnable && (
            <button
              type="button"
              className="code-run-btn"
              onClick={handleRun}
              disabled={isRunningThis}
              aria-label="Run code"
            >
              {isRunningThis ? (
                <>
                  <Loader2 size={14} className="code-run-spin" />
                  <span>Running</span>
                </>
              ) : (
                <>
                  <Play size={14} />
                  <span>Run</span>
                </>
              )}
            </button>
          )}
          <button
            type="button"
            className="code-copy-btn"
            onClick={handleCopy}
            aria-label={copied ? 'Copied' : 'Copy code'}
          >
            {copied ? (
              <>
                <Check size={14} />
                <span>Copied</span>
              </>
            ) : (
              <>
                <Copy size={14} />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>
      <pre>
        <code className={className}>{code}</code>
      </pre>
    </div>
  )
}
