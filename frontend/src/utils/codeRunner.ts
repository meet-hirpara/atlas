export interface CodeRunResult {
  stdout: string
  stderr: string
  exit_code: number
  language: string
}

const BROWSER_JS = new Set(['javascript', 'js', 'typescript', 'ts'])
/** Languages the UI offers a Run button for (shell is server-gated / not advertised). */
const RUNNABLE_UI = new Set(['python', 'py', 'javascript', 'js', 'typescript', 'ts'])

export function canRunLanguage(language?: string): boolean {
  if (!language) return false
  return RUNNABLE_UI.has(language.toLowerCase())
}

/**
 * Run JS/TS in a dedicated Worker so snippets cannot touch page localStorage/DOM.
 * Falls back to a rejected result if Workers are unavailable.
 */
export function runJavaScriptLocal(code: string): Promise<CodeRunResult> {
  return new Promise((resolve) => {
    if (typeof Worker === 'undefined') {
      resolve({
        stdout: '',
        stderr: 'JavaScript sandbox unavailable in this browser.',
        exit_code: 1,
        language: 'javascript',
      })
      return
    }

    const workerSource = `
      self.onmessage = (event) => {
        const code = String(event.data || '');
        const logs = [];
        const errors = [];
        const format = (v) => {
          if (typeof v === 'string') return v;
          try { return JSON.stringify(v, null, 2) ?? String(v); }
          catch { return String(v); }
        };
        const consoleProxy = {
          log: (...args) => logs.push(args.map(format).join(' ')),
          info: (...args) => logs.push(args.map(format).join(' ')),
          warn: (...args) => logs.push('[warn] ' + args.map(format).join(' ')),
          error: (...args) => errors.push(args.map(format).join(' ')),
        };
        try {
          const fn = new Function('console', '"use strict";\\n' + code);
          const ret = fn(consoleProxy);
          if (ret !== undefined) logs.push(String(ret));
          self.postMessage({
            stdout: logs.join('\\n') || '(no output)',
            stderr: errors.join('\\n'),
            exit_code: errors.length ? 1 : 0,
            language: 'javascript',
          });
        } catch (err) {
          self.postMessage({
            stdout: logs.join('\\n'),
            stderr: err && err.message ? err.message : String(err),
            exit_code: 1,
            language: 'javascript',
          });
        }
      };
    `

    const blob = new Blob([workerSource], { type: 'application/javascript' })
    const url = URL.createObjectURL(blob)
    let settled = false
    const worker = new Worker(url)

    const finish = (result: CodeRunResult) => {
      if (settled) return
      settled = true
      worker.terminate()
      URL.revokeObjectURL(url)
      resolve(result)
    }

    worker.onmessage = (event) => {
      finish(event.data as CodeRunResult)
    }
    worker.onerror = (event) => {
      finish({
        stdout: '',
        stderr: event.message || 'Worker execution failed',
        exit_code: 1,
        language: 'javascript',
      })
    }

    worker.postMessage(code)
    setTimeout(() => {
      finish({
        stdout: '',
        stderr: 'JavaScript execution timed out',
        exit_code: 124,
        language: 'javascript',
      })
    }, 8000)
  })
}

export async function runCode(language: string, code: string): Promise<CodeRunResult> {
  const lang = language.toLowerCase()
  if (BROWSER_JS.has(lang)) {
    return runJavaScriptLocal(code)
  }

  // Shell languages are not offered in the UI; backend also rejects without allow_shell.
  const { authHeaders } = await import('./localAuth')
  const res = await fetch('/api/code/run', {
    method: 'POST',
    headers: await authHeaders(),
    body: JSON.stringify({ language: lang, code, allowShell: false }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    return {
      stdout: '',
      stderr: (err as { detail?: string }).detail || 'Failed to run code',
      exit_code: 1,
      language: lang,
    }
  }

  return res.json()
}
