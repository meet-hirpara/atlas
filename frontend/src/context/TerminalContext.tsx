import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { runCode, type CodeRunResult } from '../utils/codeRunner'

interface TerminalState {
  open: boolean
  running: boolean
  language: string
  code: string
  result: CodeRunResult | null
  history: { language: string; code: string; result: CodeRunResult }[]
}

interface TerminalContextValue extends TerminalState {
  run: (language: string, code: string) => Promise<void>
  close: () => void
  openPanel: () => void
  clear: () => void
}

const TerminalContext = createContext<TerminalContextValue | null>(null)

export function TerminalProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<TerminalState>({
    open: false,
    running: false,
    language: '',
    code: '',
    result: null,
    history: [],
  })

  const run = useCallback(async (language: string, code: string) => {
    setState((s) => ({
      ...s,
      open: true,
      running: true,
      language,
      code,
      result: null,
    }))
    try {
      const result = await runCode(language, code)
      setState((s) => ({
        ...s,
        running: false,
        result,
        history: [{ language, code, result }, ...s.history].slice(0, 20),
      }))
    } catch (e) {
      setState((s) => ({
        ...s,
        running: false,
        result: {
          stdout: '',
          stderr: e instanceof Error ? e.message : 'Run failed',
          exit_code: 1,
          language,
        },
      }))
    }
  }, [])

  const close = useCallback(() => setState((s) => ({ ...s, open: false })), [])
  const openPanel = useCallback(() => setState((s) => ({ ...s, open: true })), [])
  const clear = useCallback(
    () => setState((s) => ({ ...s, result: null, code: '', history: [] })),
    [],
  )

  return (
    <TerminalContext.Provider value={{ ...state, run, close, openPanel, clear }}>
      {children}
    </TerminalContext.Provider>
  )
}

export function useTerminal() {
  const ctx = useContext(TerminalContext)
  if (!ctx) throw new Error('useTerminal must be used within TerminalProvider')
  return ctx
}
