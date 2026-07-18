import { useEffect, useState } from 'react'
import { AlertTriangle, Database, HardDrive, RefreshCw, Shield, X } from 'lucide-react'
import {
  applyStorageConfig,
  fetchAdminHealth,
  fetchAdminUsers,
  fetchStorageStatus,
  testStorageConnection,
  updateUserRole,
  type AdminHealth,
  type AdminUser,
  type StorageCredentials,
  type StorageEngine,
  type StorageStatus,
} from '../authApi'
import LoadingSkeleton from './LoadingSkeleton'

interface Props {
  open: boolean
  onClose: () => void
}

type Tab = 'users' | 'storage'
type StorageStep = 1 | 2 | 3

const PRIMARY_ENGINES: StorageEngine[] = ['sqlite', 'postgresql', 'mongodb']
const CACHE_ENGINES: StorageEngine[] = ['redis']
const CONFIRM_PHRASE = 'START FRESH'

const emptyCreds = (): StorageCredentials => ({
  path: './data/chatbot.db',
  host: '127.0.0.1',
  port: 0,
  database: 'atlas',
  username: '',
  password: '',
  url: '',
})

export default function AdminPanel({ open, onClose }: Props) {
  const [tab, setTab] = useState<Tab>('users')
  const [users, setUsers] = useState<AdminUser[]>([])
  const [health, setHealth] = useState<AdminHealth | null>(null)
  const [storage, setStorage] = useState<StorageStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [testMsg, setTestMsg] = useState<string | null>(null)

  const [primaryEngine, setPrimaryEngine] = useState<StorageEngine>('sqlite')
  const [primaryCreds, setPrimaryCreds] = useState<StorageCredentials>(emptyCreds())
  const [useRedis, setUseRedis] = useState(false)
  const [redisCreds, setRedisCreds] = useState<StorageCredentials>({
    ...emptyCreds(),
    host: '127.0.0.1',
    port: 6379,
    database: '0',
  })
  const [ackLoss, setAckLoss] = useState(false)
  const [confirmText, setConfirmText] = useState('')
  const [storageStep, setStorageStep] = useState<StorageStep>(1)
  const [primaryTestedOk, setPrimaryTestedOk] = useState(false)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [u, h, s] = await Promise.all([
        fetchAdminUsers(),
        fetchAdminHealth(),
        fetchStorageStatus(),
      ])
      setUsers(u)
      setHealth(h)
      setStorage(s)
      setPrimaryEngine(s.primary.engine)
      setPrimaryCreds({ ...emptyCreds(), ...s.primary.credentials, password: '' })
      if (s.chat_cache?.engine === 'redis') {
        setUseRedis(true)
        setRedisCreds({ ...emptyCreds(), ...s.chat_cache.credentials, password: '', port: s.chat_cache.credentials.port || 6379 })
      } else {
        setUseRedis(false)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load admin data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open) void load()
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const setRole = async (id: string, role: 'user' | 'admin') => {
    try {
      const updated = await updateUserRole(id, role)
      setUsers((prev) => prev.map((u) => (u.id === id ? updated : u)))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update role')
    }
  }

  const onTest = async (target: 'primary' | 'chat_cache') => {
    setBusy(true)
    setTestMsg(null)
    setError(null)
    try {
      const engine = target === 'primary' ? primaryEngine : 'redis'
      const credentials = target === 'primary' ? primaryCreds : redisCreds
      const res = await testStorageConnection({ engine, credentials, purpose: target })
      setTestMsg(
        res.ok
          ? `Connection works — ${res.message}${res.latency_ms != null ? ` (${res.latency_ms} ms)` : ''}`
          : `Could not connect — ${res.message}`,
      )
      if (target === 'primary') setPrimaryTestedOk(Boolean(res.ok))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Connection test failed')
      if (target === 'primary') setPrimaryTestedOk(false)
    } finally {
      setBusy(false)
    }
  }

  const onApply = async () => {
    if (!ackLoss || confirmText.trim().toUpperCase() !== CONFIRM_PHRASE) {
      setError(`Check the box and type ${CONFIRM_PHRASE} to continue.`)
      return
    }
    setBusy(true)
    setError(null)
    setTestMsg(null)
    try {
      const next = await applyStorageConfig({
        primary: { engine: primaryEngine, credentials: primaryCreds, enabled: true },
        chat_cache: useRedis
          ? { engine: 'redis', credentials: redisCreds, enabled: true }
          : null,
        confirm_destructive: true,
        acknowledge_data_loss: true,
      })
      setStorage(next)
      setAckLoss(false)
      setConfirmText('')
      setStorageStep(1)
      setPrimaryTestedOk(false)
      setTestMsg('Storage updated. Sign out and create a new admin — previous data was not moved.')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to apply storage')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="admin-overlay" role="dialog" aria-modal="true" aria-label="Admin">
      <div className="admin-panel admin-panel-wide">
        <header className="admin-panel-head">
          <div className="admin-panel-title">
            <Shield size={18} />
            <strong>Admin</strong>
          </div>
          <div className="admin-panel-actions">
            <button type="button" onClick={() => void load()} disabled={loading} title="Refresh" aria-label="Refresh">
              <RefreshCw size={16} className={loading ? 'spin' : undefined} />
            </button>
            <button type="button" onClick={onClose} aria-label="Close">
              <X size={16} />
            </button>
          </div>
        </header>

        <nav className="admin-tabs" aria-label="Admin sections">
          <button
            type="button"
            className={tab === 'users' ? 'active' : undefined}
            onClick={() => setTab('users')}
          >
            Users
          </button>
          <button
            type="button"
            className={tab === 'storage' ? 'active' : undefined}
            onClick={() => setTab('storage')}
          >
            <HardDrive size={14} /> Storage
          </button>
        </nav>

        {error && <p className="admin-error">{error}</p>}
        {testMsg && <p className="admin-ok">{testMsg}</p>}

        {loading && !health && !storage ? (
          <div style={{ padding: '1rem' }}>
            <LoadingSkeleton rows={5} />
          </div>
        ) : tab === 'users' ? (
          <>
            {health && (
              <section className="admin-health">
                <h3>Usage</h3>
                <ul>
                  <li>Users: {health.users}</li>
                  <li>Sessions: {health.sessions}</li>
                  <li>Messages: {health.messages}</li>
                  <li>Connections: {health.connections}</li>
                  <li>Connected apps: {health.mcp_servers}</li>
                </ul>
              </section>
            )}

            <section className="admin-users">
              <h3>Users</h3>
              {loading && users.length === 0 ? (
                <LoadingSkeleton rows={4} />
              ) : users.length === 0 ? (
                <p className="admin-muted">No users yet.</p>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>Email</th>
                      <th>Role</th>
                      <th>Sessions</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id}>
                        <td>{u.email}</td>
                        <td>{u.role}</td>
                        <td>{u.session_count}</td>
                        <td>
                          {u.role === 'admin' ? (
                            <button type="button" onClick={() => void setRole(u.id, 'user')}>
                              Make user
                            </button>
                          ) : (
                            <button type="button" onClick={() => void setRole(u.id, 'admin')}>
                              Make admin
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
          </>
        ) : (
          <section className="admin-storage">
            <div className="admin-storage-warn" role="alert">
              <AlertTriangle size={18} />
              <div>
                <strong>This replaces your database</strong>
                <p>
                  {storage?.warning ||
                    'Switching the primary store starts empty. Existing users, chats, and settings stay on the old database and are not migrated.'}
                </p>
              </div>
            </div>

            <ol className="admin-storage-steps" aria-label="Storage setup steps">
              <li className={storageStep === 1 ? 'active' : storageStep > 1 ? 'done' : undefined}>
                <span>1</span> Test connection
              </li>
              <li className={storageStep === 2 ? 'active' : storageStep > 2 ? 'done' : undefined}>
                <span>2</span> Confirm
              </li>
              <li className={storageStep === 3 ? 'active' : undefined}>
                <span>3</span> Apply
              </li>
            </ol>

            {storage && storageStep === 1 && (
              <div className="admin-storage-current">
                <h3>
                  <Database size={16} /> Current setup
                </h3>
                <ul>
                  {storage.placement.map((p) => (
                    <li key={p.purpose}>
                      <span>{p.description}</span>
                      <code>
                        {p.engine} · {p.location_hint}
                      </code>
                    </li>
                  ))}
                </ul>
                <p className="admin-muted">
                  Drivers:{' '}
                  {storage.engines_available
                    .map((e) => `${e.engine}${e.driver_installed ? '' : ' (missing)'}`)
                    .join(' · ')}
                </p>
              </div>
            )}

            {storageStep === 1 && (
              <div className="admin-storage-form">
                <h3>Choose primary database</h3>
                <label className="admin-field">
                  Engine
                  <select
                    value={primaryEngine}
                    onChange={(e) => {
                      setPrimaryEngine(e.target.value as StorageEngine)
                      setPrimaryTestedOk(false)
                    }}
                  >
                    {PRIMARY_ENGINES.map((eng) => (
                      <option key={eng} value={eng}>
                        {eng === 'sqlite'
                          ? 'SQLite (local file)'
                          : eng === 'postgresql'
                            ? 'PostgreSQL'
                            : 'MongoDB'}
                      </option>
                    ))}
                  </select>
                </label>

                {primaryEngine === 'sqlite' ? (
                  <label className="admin-field">
                    Database file path
                    <input
                      value={primaryCreds.path || ''}
                      onChange={(e) => {
                        setPrimaryCreds((c) => ({ ...c, path: e.target.value }))
                        setPrimaryTestedOk(false)
                      }}
                      placeholder="./data/chatbot.db"
                    />
                  </label>
                ) : (
                  <>
                    <label className="admin-field">
                      Connection URL (optional override)
                      <input
                        value={primaryCreds.url || ''}
                        onChange={(e) => {
                          setPrimaryCreds((c) => ({ ...c, url: e.target.value }))
                          setPrimaryTestedOk(false)
                        }}
                        placeholder={
                          primaryEngine === 'mongodb'
                            ? 'mongodb://user:pass@host:27017/atlas'
                            : 'postgresql://user:pass@host:5432/atlas'
                        }
                      />
                    </label>
                    <div className="admin-field-row">
                      <label className="admin-field">
                        Host
                        <input
                          value={primaryCreds.host || ''}
                          onChange={(e) => {
                            setPrimaryCreds((c) => ({ ...c, host: e.target.value }))
                            setPrimaryTestedOk(false)
                          }}
                        />
                      </label>
                      <label className="admin-field">
                        Port
                        <input
                          type="number"
                          value={primaryCreds.port || (primaryEngine === 'mongodb' ? 27017 : 5432)}
                          onChange={(e) => {
                            setPrimaryCreds((c) => ({ ...c, port: Number(e.target.value) || 0 }))
                            setPrimaryTestedOk(false)
                          }}
                        />
                      </label>
                    </div>
                    <div className="admin-field-row">
                      <label className="admin-field">
                        Database
                        <input
                          value={primaryCreds.database || ''}
                          onChange={(e) => {
                            setPrimaryCreds((c) => ({ ...c, database: e.target.value }))
                            setPrimaryTestedOk(false)
                          }}
                        />
                      </label>
                      <label className="admin-field">
                        Username
                        <input
                          value={primaryCreds.username || ''}
                          onChange={(e) => {
                            setPrimaryCreds((c) => ({ ...c, username: e.target.value }))
                            setPrimaryTestedOk(false)
                          }}
                          autoComplete="off"
                        />
                      </label>
                      <label className="admin-field">
                        Password
                        <input
                          type="password"
                          value={primaryCreds.password || ''}
                          onChange={(e) => {
                            setPrimaryCreds((c) => ({ ...c, password: e.target.value }))
                            setPrimaryTestedOk(false)
                          }}
                          autoComplete="new-password"
                        />
                      </label>
                    </div>
                  </>
                )}

                <div className="admin-storage-actions">
                  <button type="button" disabled={busy} onClick={() => void onTest('primary')}>
                    {busy ? 'Testing…' : 'Test connection'}
                  </button>
                </div>

                <h3>Optional: chat history cache</h3>
                <label className="admin-check">
                  <input
                    type="checkbox"
                    checked={useRedis}
                    onChange={(e) => setUseRedis(e.target.checked)}
                  />
                  Use Redis for chat message history
                </label>
                {useRedis && (
                  <>
                    <div className="admin-field-row">
                      <label className="admin-field">
                        Host
                        <input
                          value={redisCreds.host || ''}
                          onChange={(e) => setRedisCreds((c) => ({ ...c, host: e.target.value }))}
                        />
                      </label>
                      <label className="admin-field">
                        Port
                        <input
                          type="number"
                          value={redisCreds.port || 6379}
                          onChange={(e) =>
                            setRedisCreds((c) => ({ ...c, port: Number(e.target.value) || 6379 }))
                          }
                        />
                      </label>
                      <label className="admin-field">
                        DB index
                        <input
                          value={redisCreds.database || '0'}
                          onChange={(e) => setRedisCreds((c) => ({ ...c, database: e.target.value }))}
                        />
                      </label>
                    </div>
                    <label className="admin-field">
                      Password
                      <input
                        type="password"
                        value={redisCreds.password || ''}
                        onChange={(e) => setRedisCreds((c) => ({ ...c, password: e.target.value }))}
                        autoComplete="new-password"
                      />
                    </label>
                    <label className="admin-field">
                      URL override
                      <input
                        value={redisCreds.url || ''}
                        onChange={(e) => setRedisCreds((c) => ({ ...c, url: e.target.value }))}
                        placeholder="redis://:pass@127.0.0.1:6379/0"
                      />
                    </label>
                    <div className="admin-storage-actions">
                      <button type="button" disabled={busy} onClick={() => void onTest('chat_cache')}>
                        Test Redis
                      </button>
                    </div>
                    <p className="admin-muted">
                      Supported cache engines: {CACHE_ENGINES.join(', ')}. Messages are dual-written to
                      primary and Redis when enabled.
                    </p>
                  </>
                )}

                <div className="admin-storage-nav">
                  <button
                    type="button"
                    className="admin-primary-btn"
                    disabled={!primaryTestedOk}
                    onClick={() => setStorageStep(2)}
                    title={primaryTestedOk ? undefined : 'Test the primary connection first'}
                  >
                    Continue to confirm →
                  </button>
                  {!primaryTestedOk && (
                    <p className="admin-muted">Test the primary connection successfully before continuing.</p>
                  )}
                </div>
              </div>
            )}

            {storageStep === 2 && (
              <div className="admin-storage-confirm">
                <h3>Confirm you understand</h3>
                <p className="admin-storage-confirm-lead">
                  You are about to switch to <strong>{primaryEngine}</strong>
                  {useRedis ? ' with Redis chat cache' : ''}. Atlas will start with an empty store —
                  you will need to create a new admin account after applying.
                </p>
                <label className="admin-check">
                  <input
                    type="checkbox"
                    checked={ackLoss}
                    onChange={(e) => setAckLoss(e.target.checked)}
                  />
                  I understand previous admins and data will not be moved over
                </label>
                <label className="admin-field">
                  Type <strong>{CONFIRM_PHRASE}</strong> to unlock the final step
                  <input
                    value={confirmText}
                    onChange={(e) => setConfirmText(e.target.value)}
                    placeholder={CONFIRM_PHRASE}
                    autoComplete="off"
                  />
                </label>
                <div className="admin-storage-nav">
                  <button type="button" onClick={() => setStorageStep(1)}>
                    ← Back
                  </button>
                  <button
                    type="button"
                    className="admin-primary-btn"
                    disabled={!ackLoss || confirmText.trim().toUpperCase() !== CONFIRM_PHRASE}
                    onClick={() => setStorageStep(3)}
                  >
                    Continue to apply →
                  </button>
                </div>
              </div>
            )}

            {storageStep === 3 && (
              <div className="admin-storage-confirm admin-storage-apply">
                <h3>Apply new storage</h3>
                <p className="admin-storage-confirm-lead">
                  Last chance — this cannot be undone from the app. Have your new database ready.
                </p>
                <div className="admin-storage-nav">
                  <button type="button" onClick={() => setStorageStep(2)}>
                    ← Back
                  </button>
                  <button
                    type="button"
                    className="admin-danger-btn"
                    disabled={busy}
                    onClick={() => void onApply()}
                  >
                    {busy ? 'Applying…' : 'Apply & start fresh'}
                  </button>
                </div>
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  )
}
