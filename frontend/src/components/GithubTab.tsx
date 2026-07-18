import { useState } from 'react'
import {
  AlertCircle,
  GitBranch,
  GitFork,
  Loader2,
  MessageSquare,
  Plus,
  Trash2,
  CheckCircle2,
} from 'lucide-react'
import type { GithubRepo, RepoGraph } from '../github'
import { fetchRepoGraph, queryGithubRepo, repoLabel, statusLabel } from '../github'
import RepoGraphView from './RepoGraphView'

interface Props {
  repos: GithubRepo[]
  loading: boolean
  error: string | null
  activeRepoIds: string[]
  onAdd: (url: string, token: string, branch: string) => Promise<GithubRepo | void>
  onRemove: (id: string) => Promise<void>
  onToggleActive: (id: string) => void
}

export default function GithubTab({
  repos,
  loading,
  error,
  activeRepoIds,
  onAdd,
  onRemove,
  onToggleActive,
}: Props) {
  const [url, setUrl] = useState('')
  const [token, setToken] = useState('')
  const [branch, setBranch] = useState('main')
  const [adding, setAdding] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [graph, setGraph] = useState<RepoGraph | null>(null)
  const [graphLoading, setGraphLoading] = useState(false)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [queryLoading, setQueryLoading] = useState(false)
  const [queryError, setQueryError] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<string | null>(null)

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) return
    setAdding(true)
    try {
      const repo = await onAdd(url.trim(), token.trim(), branch.trim() || 'main')
      setUrl('')
      setToken('')
      if (repo) setSelectedId(repo.id)
    } finally {
      setAdding(false)
    }
  }

  const loadGraph = async (id: string) => {
    setSelectedId(id)
    setGraph(null)
    setAnswer('')
    setGraphLoading(true)
    try {
      const g = await fetchRepoGraph(id)
      setGraph(g)
    } catch {
      setGraph({ nodes: [], edges: [] })
    } finally {
      setGraphLoading(false)
    }
  }

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedId || !question.trim()) return
    setQueryLoading(true)
    setQueryError(null)
    setAnswer('')
    try {
      const result = await queryGithubRepo(selectedId, question.trim())
      setAnswer(result.answer)
    } catch (err) {
      setQueryError(err instanceof Error ? err.message : 'Query failed')
    } finally {
      setQueryLoading(false)
    }
  }

  return (
    <div className="github-tab">
      <section className="settings-card">
        <div className="settings-card-head">
          <div className="settings-card-icon">
            <GitFork size={18} />
          </div>
          <div className="settings-card-titles">
            <h3 className="settings-card-title">Add GitHub repository</h3>
            <p className="settings-card-desc">
              Clone and index a repo for code graph, Q&amp;A, and smart build references in chat.
            </p>
          </div>
        </div>
        <div className="settings-card-body">
          <form className="github-add-form" onSubmit={handleAdd}>
            <label>
              <span>Repository URL</span>
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                required
              />
            </label>
            <div className="github-add-row">
              <label>
                <span>Branch</span>
                <input
                  value={branch}
                  onChange={(e) => setBranch(e.target.value)}
                  placeholder="main"
                />
              </label>
              <label>
                <span>Token (private repos)</span>
                <input
                  type="password"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  placeholder="ghp_… optional"
                  autoComplete="off"
                />
              </label>
            </div>
            <button type="submit" className="github-add-btn" disabled={adding || !url.trim()}>
              {adding ? <Loader2 size={14} className="spin" /> : <Plus size={14} />}
              Add repository
            </button>
          </form>
        </div>
      </section>

      {error && (
        <div className="github-error">
          <AlertCircle size={14} />
          {error}
        </div>
      )}

      <section className="settings-card">
        <div className="settings-card-head">
          <div className="settings-card-titles">
            <h3 className="settings-card-title">Indexed repositories</h3>
            <p className="settings-card-desc">
              Toggle repos to use as chat context. Python, JS, and TS call graphs are supported.
            </p>
          </div>
        </div>
        <div className="settings-card-body">
          {loading && !repos.length ? (
            <p className="settings-inline-hint">
              <Loader2 size={14} className="spin" /> Loading…
            </p>
          ) : !repos.length ? (
            <p className="settings-inline-hint">No repositories added yet.</p>
          ) : (
            <ul className="github-repo-list">
              {repos.map((repo) => {
                const active = activeRepoIds.includes(repo.id)
                return (
                  <li key={repo.id} className={`github-repo-item${selectedId === repo.id ? ' github-repo-item-selected' : ''}`}>
                    <div className="github-repo-main">
                      <button
                        type="button"
                        className={`github-repo-toggle${active ? ' github-repo-toggle-on' : ''}`}
                        onClick={() => onToggleActive(repo.id)}
                        title={active ? 'Active in chat' : 'Use in chat'}
                        disabled={repo.status !== 'ready'}
                      >
                        {active ? <CheckCircle2 size={16} /> : <GitBranch size={16} />}
                      </button>
                      <button type="button" className="github-repo-info" onClick={() => loadGraph(repo.id)}>
                        <span className="github-repo-name">{repoLabel(repo)}</span>
                        <span className={`github-repo-status github-repo-status-${repo.status}`}>
                          {statusLabel(repo.status)}
                          {repo.status === 'ready' && ` · ${repo.file_count} files · ${repo.chunk_count} chunks`}
                        </span>
                        {repo.error_message && (
                          <span className="github-repo-err">{repo.error_message}</span>
                        )}
                      </button>
                      <button
                        type="button"
                        className="github-repo-delete"
                        onClick={() => onRemove(repo.id)}
                        aria-label="Remove"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </section>

      {selectedId && (
        <>
          <section className="settings-card">
            <div className="settings-card-head">
              <div className="settings-card-titles">
                <h3 className="settings-card-title">Code graph</h3>
                <p className="settings-card-desc">Functions, classes, imports, and call relationships.</p>
              </div>
            </div>
            <div className="settings-card-body github-graph-body">
              {graphLoading ? (
                <p className="settings-inline-hint">
                  <Loader2 size={14} className="spin" /> Building graph…
                </p>
              ) : graph ? (
                <RepoGraphView
                  graph={graph}
                  selectedNodeId={selectedNode}
                  onSelectNode={setSelectedNode}
                />
              ) : null}
            </div>
          </section>

          <section className="settings-card">
            <div className="settings-card-head">
              <div className="settings-card-icon">
                <MessageSquare size={18} />
              </div>
              <div className="settings-card-titles">
                <h3 className="settings-card-title">Ask about this repo</h3>
                <p className="settings-card-desc">Q&amp;A over indexed code chunks.</p>
              </div>
            </div>
            <div className="settings-card-body">
              <form className="github-query-form" onSubmit={handleQuery}>
                <input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="How does authentication work in this repo?"
                  disabled={queryLoading}
                />
                <button type="submit" disabled={queryLoading || !question.trim()}>
                  {queryLoading ? <Loader2 size={14} className="spin" /> : 'Ask'}
                </button>
              </form>
              {queryError && <p className="github-repo-err">{queryError}</p>}
              {answer && <div className="github-query-answer">{answer}</div>}
            </div>
          </section>
        </>
      )}
    </div>
  )
}
