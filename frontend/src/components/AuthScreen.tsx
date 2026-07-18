import { useState } from 'react'
import { Eye, EyeOff } from 'lucide-react'
import { APP_NAME } from '../brand'
import LampLogo from './LampLogo'

interface Props {
  hasUsers: boolean
  onLogin: (email: string, password: string) => Promise<void>
  onRegister: (email: string, password: string) => Promise<void>
}

export default function AuthScreen({ hasUsers, onLogin, onRegister }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>(hasUsers ? 'login' : 'register')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === 'register') {
        if (password !== confirm) {
          setError('Passwords do not match')
          return
        }
        await onRegister(email.trim(), password)
      } else {
        await onLogin(email.trim(), password)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong — try again')
    } finally {
      setBusy(false)
    }
  }

  const switchMode = (next: 'login' | 'register') => {
    setMode(next)
    setError(null)
    setConfirm('')
  }

  return (
    <div className="auth-screen">
      <div className="auth-shell">
        <aside className="auth-hero" aria-hidden="true">
          <div className="auth-hero-glow" />
          <div className="auth-hero-content">
            <LampLogo size={56} />
            <h1 className="auth-hero-brand">{APP_NAME}</h1>
            <p className="auth-hero-tagline">
              Research, integrations, and focused chat — your workspace, signed in and private.
            </p>
          </div>
        </aside>

        <div className="auth-card">
          <div className="auth-brand auth-brand-mobile">
            <LampLogo size={36} />
            <h1>{APP_NAME}</h1>
          </div>

          <div className="auth-card-head">
            <h2>
              {mode === 'register'
                ? hasUsers
                  ? 'Join Atlas'
                  : 'Set up Atlas'
                : 'Welcome back'}
            </h2>
            <p>
              {mode === 'register'
                ? hasUsers
                  ? 'Create your space — chats, settings, and workspace stay yours.'
                  : 'Create the first admin account. Takes under a minute.'
                : 'Pick up where you left off.'}
            </p>
          </div>

          <form className="auth-form" onSubmit={(e) => void submit(e)}>
            <label>
              Email
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
              />
            </label>
            <label>
              Password
              <div className="auth-password-field">
                <input
                  type={showPassword ? 'text' : 'password'}
                  autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
                  required
                  minLength={mode === 'register' ? 8 : 1}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === 'register' ? 'At least 8 characters' : 'Your password'}
                />
                <button
                  type="button"
                  className="auth-password-toggle"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </label>
            {mode === 'register' && (
              <label>
                Confirm password
                <input
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  required
                  minLength={8}
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Repeat password"
                />
              </label>
            )}

            {error && <p className="auth-error" role="alert">{error}</p>}

            <button type="submit" className="auth-submit" disabled={busy}>
              {busy
                ? mode === 'register'
                  ? 'Creating…'
                  : 'Signing in…'
                : mode === 'register'
                  ? 'Create account'
                  : 'Sign in'}
            </button>
          </form>

          <p className="auth-switch">
            {mode === 'login' ? (
              <>
                New here?{' '}
                <button type="button" onClick={() => switchMode('register')}>
                  Create an account
                </button>
              </>
            ) : (
              <>
                Already have an account?{' '}
                <button type="button" onClick={() => switchMode('login')}>
                  Sign in
                </button>
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  )
}
