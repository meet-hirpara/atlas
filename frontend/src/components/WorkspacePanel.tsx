import { useCallback, useEffect, useState } from 'react'
import {
  Briefcase,
  X,
  FolderKanban,
  FileText,
  Inbox,
  Users,
  ScrollText,
  CalendarClock,
  Gauge,
  Trash2,
  Plus,
} from 'lucide-react'
import {
  createClient,
  createJob,
  createProject,
  createProposal,
  createSchedule,
  deleteClient,
  deleteJob,
  deleteProject,
  deleteProposal,
  deleteSchedule,
  fetchAudit,
  fetchClients,
  fetchCockpit,
  fetchDueSchedules,
  fetchJobs,
  fetchProjects,
  fetchProposals,
  fetchSchedules,
  fetchUsage,
  type AuditEntry,
  type CrmClient,
  type FreelanceCockpit,
  type JobItem,
  type Proposal,
  type ResearchSchedule,
  type UsageInfo,
  type WorkspaceProject,
} from '../workspace'
import EmptyState from './EmptyState'
import LoadingSkeleton from './LoadingSkeleton'

export type WorkspaceSection =
  | 'cockpit'
  | 'projects'
  | 'proposals'
  | 'jobs'
  | 'clients'
  | 'audit'
  | 'schedules'
  | 'usage'

interface Props {
  open: boolean
  section: WorkspaceSection
  onSection: (s: WorkspaceSection) => void
  onClose: () => void
  activeSessionId: string | null
  onDraftProposal?: (job: JobItem) => void
  onRunSchedule?: (topic: string) => void
  onAssignProject?: (projectId: string | null) => void
}

const PRIMARY_NAV: { id: WorkspaceSection; label: string; icon: typeof Briefcase }[] = [
  { id: 'cockpit', label: 'Overview', icon: Briefcase },
  { id: 'projects', label: 'Projects', icon: FolderKanban },
  { id: 'proposals', label: 'Proposals', icon: FileText },
  { id: 'jobs', label: 'Job inbox', icon: Inbox },
  { id: 'clients', label: 'Clients', icon: Users },
  { id: 'schedules', label: 'Research', icon: CalendarClock },
]

const ADVANCED_NAV: { id: WorkspaceSection; label: string; icon: typeof Briefcase }[] = [
  { id: 'audit', label: 'Activity log', icon: ScrollText },
  { id: 'usage', label: 'Usage', icon: Gauge },
]

export default function WorkspacePanel({
  open,
  section,
  onSection,
  onClose,
  activeSessionId,
  onDraftProposal,
  onRunSchedule,
  onAssignProject,
}: Props) {
  const [projects, setProjects] = useState<WorkspaceProject[]>([])
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [jobs, setJobs] = useState<JobItem[]>([])
  const [clients, setClients] = useState<CrmClient[]>([])
  const [audit, setAudit] = useState<AuditEntry[]>([])
  const [schedules, setSchedules] = useState<ResearchSchedule[]>([])
  const [due, setDue] = useState<ResearchSchedule[]>([])
  const [cockpit, setCockpit] = useState<FreelanceCockpit | null>(null)
  const [usage, setUsage] = useState<UsageInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [projectName, setProjectName] = useState('')
  const [jobPaste, setJobPaste] = useState('')
  const [clientName, setClientName] = useState('')
  const [clientRate, setClientRate] = useState('')
  const [scheduleTopic, setScheduleTopic] = useState('')
  const [proposalTitle, setProposalTitle] = useState('')
  const [proposalBody, setProposalBody] = useState('')
  const [loading, setLoading] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(
    () => section === 'audit' || section === 'usage',
  )

  useEffect(() => {
    if (section === 'audit' || section === 'usage') setShowAdvanced(true)
  }, [section])

  const reload = useCallback(async () => {
    setError(null)
    setLoading(true)
    try {
      const [p, pr, j, c, a, s, d, ck] = await Promise.all([
        fetchProjects(),
        fetchProposals(),
        fetchJobs(),
        fetchClients(),
        fetchAudit(40),
        fetchSchedules(),
        fetchDueSchedules(),
        fetchCockpit(),
      ])
      setProjects(p)
      setProposals(pr)
      setJobs(j)
      setClients(c)
      setAudit(a)
      setSchedules(s)
      setDue(d)
      setCockpit(ck)
      if (activeSessionId) {
        setUsage(await fetchUsage(activeSessionId))
      } else {
        setUsage(null)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load workspace')
    } finally {
      setLoading(false)
    }
  }, [activeSessionId])

  useEffect(() => {
    if (open) void reload()
  }, [open, reload, section])

  if (!open) return null

  return (
    <div className="workspace-panel-overlay" role="dialog" aria-modal="true">
      <div className="workspace-panel">
        <header className="workspace-panel-head">
          <h2>Workspace</h2>
          <button type="button" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </header>
        <div className="workspace-panel-body">
          <nav className="workspace-panel-nav">
            {PRIMARY_NAV.map((item) => (
              <button
                key={item.id}
                type="button"
                className={section === item.id ? 'active' : ''}
                onClick={() => onSection(item.id)}
              >
                <item.icon size={15} />
                {item.label}
              </button>
            ))}
            <button
              type="button"
              className="workspace-nav-more"
              aria-expanded={showAdvanced}
              onClick={() => setShowAdvanced((v) => !v)}
            >
              {showAdvanced ? 'Hide advanced' : 'More'}
            </button>
            {showAdvanced &&
              ADVANCED_NAV.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={section === item.id ? 'active' : ''}
                  onClick={() => onSection(item.id)}
                >
                  <item.icon size={15} />
                  {item.label}
                </button>
              ))}
          </nav>
          <div className="workspace-panel-content">
            {error && <p className="workspace-empty error">{error}</p>}

            {section === 'cockpit' && (
              <div className="workspace-section">
                <h3>Overview</h3>
                {loading && !cockpit ? (
                  <LoadingSkeleton rows={4} />
                ) : !cockpit ? (
                  <EmptyState
                    title="Nothing here yet"
                    body="Paste a job in Job inbox, or start drafting a proposal — Atlas keeps your freelance work in one place."
                    actionLabel="Open job inbox"
                    onAction={() => onSection('jobs')}
                  />
                ) : (
                  <>
                    <p className="workspace-muted">
                      Connected platforms:{' '}
                      {cockpit.connected_platforms.length
                        ? cockpit.connected_platforms.join(', ')
                        : 'None yet — connect Upwork from Settings'}
                    </p>
                    <div className="workspace-stats">
                      <span>{cockpit.open_jobs} open jobs</span>
                      <span>{cockpit.proposal_count} proposals</span>
                    </div>
                    <div className="workspace-actions-row">
                      <button type="button" onClick={() => onSection('jobs')}>
                        Find / paste jobs
                      </button>
                      <button type="button" onClick={() => onSection('proposals')}>
                        Draft proposal
                      </button>
                    </div>
                    {cockpit.recent_jobs.length === 0 && (
                      <EmptyState
                        compact
                        title="Inbox is clear"
                        body="Paste a job posting and Atlas will help you draft a sharp proposal."
                        actionLabel="Add a job"
                        onAction={() => onSection('jobs')}
                      />
                    )}
                  </>
                )}
              </div>
            )}

            {section === 'projects' && (
              <div className="workspace-section">
                <h3>Projects</h3>
                <form
                  className="workspace-inline-form"
                  onSubmit={async (e) => {
                    e.preventDefault()
                    if (!projectName.trim()) return
                    await createProject(projectName.trim())
                    setProjectName('')
                    await reload()
                  }}
                >
                  <input
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value)}
                    placeholder="New project name"
                  />
                  <button type="submit"><Plus size={14} /> Add</button>
                </form>
                {projects.length === 0 ? (
                  <EmptyState
                    compact
                    title="No projects yet"
                    body="Name a client or engagement above — then assign chats so everything stays grouped."
                  />
                ) : (
                  <ul className="workspace-list">
                    {projects.map((p) => (
                      <li key={p.id}>
                        <div>
                          <strong>{p.name}</strong>
                          {p.description && <span className="workspace-muted">{p.description}</span>}
                        </div>
                        <div className="workspace-row-actions">
                          {onAssignProject && activeSessionId && (
                            <button type="button" onClick={() => onAssignProject(p.id)}>
                              Assign chat
                            </button>
                          )}
                          <button type="button" aria-label="Delete" onClick={async () => { await deleteProject(p.id); await reload() }}>
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {section === 'proposals' && (
              <div className="workspace-section">
                <h3>Proposal library</h3>
                <form
                  className="workspace-stack-form"
                  onSubmit={async (e) => {
                    e.preventDefault()
                    if (!proposalTitle.trim() || !proposalBody.trim()) return
                    await createProposal({
                      title: proposalTitle.trim(),
                      content: proposalBody.trim(),
                      sessionId: activeSessionId || undefined,
                    })
                    setProposalTitle('')
                    setProposalBody('')
                    await reload()
                  }}
                >
                  <input value={proposalTitle} onChange={(e) => setProposalTitle(e.target.value)} placeholder="Title" />
                  <textarea value={proposalBody} onChange={(e) => setProposalBody(e.target.value)} placeholder="Proposal draft…" rows={4} />
                  <button type="submit">Save proposal</button>
                </form>
                {proposals.length === 0 ? (
                  <EmptyState
                    compact
                    title="Proposal shelf is empty"
                    body="Save a draft from chat, or paste one here — Atlas keeps them for reuse."
                  />
                ) : (
                  <ul className="workspace-list">
                    {proposals.map((p) => (
                      <li key={p.id}>
                        <div>
                          <strong>{p.title}</strong>
                          <span className="workspace-muted">{p.content.slice(0, 120)}…</span>
                        </div>
                        <button type="button" onClick={async () => { await deleteProposal(p.id); await reload() }}>
                          <Trash2 size={14} />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {section === 'jobs' && (
              <div className="workspace-section">
                <h3>Job inbox</h3>
                <form
                  className="workspace-stack-form"
                  onSubmit={async (e) => {
                    e.preventDefault()
                    if (!jobPaste.trim()) return
                    await createJob(jobPaste.trim())
                    setJobPaste('')
                    await reload()
                  }}
                >
                  <textarea value={jobPaste} onChange={(e) => setJobPaste(e.target.value)} placeholder="Paste a job post…" rows={5} />
                  <button type="submit">Score &amp; save</button>
                </form>
                {jobs.length === 0 ? (
                  <EmptyState
                    compact
                    title="Inbox is waiting"
                    body="Paste an Upwork or freelance post above — Atlas scores fit and keeps it handy."
                  />
                ) : (
                  <ul className="workspace-list">
                    {jobs.map((j) => (
                      <li key={j.id}>
                        <div>
                          <strong>{j.title}</strong>
                          <span className="workspace-muted">
                            Fit {j.fit_score ?? '—'} · {j.fit_notes}
                          </span>
                        </div>
                        <div className="workspace-row-actions">
                          {onDraftProposal && (
                            <button type="button" onClick={() => onDraftProposal(j)}>Draft proposal</button>
                          )}
                          <button type="button" onClick={async () => { await deleteJob(j.id); await reload() }}>
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {section === 'clients' && (
              <div className="workspace-section">
                <h3>Clients</h3>
                <form
                  className="workspace-inline-form"
                  onSubmit={async (e) => {
                    e.preventDefault()
                    if (!clientName.trim()) return
                    await createClient(clientName.trim(), '', clientRate.trim())
                    setClientName('')
                    setClientRate('')
                    await reload()
                  }}
                >
                  <input value={clientName} onChange={(e) => setClientName(e.target.value)} placeholder="Client name" />
                  <input value={clientRate} onChange={(e) => setClientRate(e.target.value)} placeholder="Rate" />
                  <button type="submit"><Plus size={14} /> Add</button>
                </form>
                {clients.length === 0 ? (
                  <EmptyState
                    compact
                    title="Build your client list"
                    body="Add a name and rate — light CRM for the people you work with."
                  />
                ) : (
                  <ul className="workspace-list">
                    {clients.map((c) => (
                      <li key={c.id}>
                        <div>
                          <strong>{c.name}</strong>
                          <span className="workspace-muted">{c.rate || 'No rate'} · {c.notes || 'No notes'}</span>
                        </div>
                        <button type="button" onClick={async () => { await deleteClient(c.id); await reload() }}>
                          <Trash2 size={14} />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {section === 'schedules' && (
              <div className="workspace-section">
                <h3>Scheduled research</h3>
                {due.length > 0 && (
                  <div className="workspace-due">
                    <strong>Due now</strong>
                    {due.map((d) => (
                      <div key={d.id} className="workspace-due-row">
                        <span>{d.topic}</span>
                        {onRunSchedule && (
                          <button type="button" onClick={() => onRunSchedule(d.topic)}>Run</button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                <form
                  className="workspace-inline-form"
                  onSubmit={async (e) => {
                    e.preventDefault()
                    if (!scheduleTopic.trim()) return
                    await createSchedule(scheduleTopic.trim(), 'weekly')
                    setScheduleTopic('')
                    await reload()
                  }}
                >
                  <input value={scheduleTopic} onChange={(e) => setScheduleTopic(e.target.value)} placeholder="Weekly research topic" />
                  <button type="submit"><Plus size={14} /> Add</button>
                </form>
                {schedules.length === 0 ? (
                  <EmptyState
                    compact
                    title="No research cadence yet"
                    body="Add a weekly topic — Atlas reminds you when you’re back."
                  />
                ) : (
                  <ul className="workspace-list">
                    {schedules.map((s) => (
                      <li key={s.id}>
                        <div>
                          <strong>{s.topic}</strong>
                          <span className="workspace-muted">{s.cadence} · next {s.next_run_at ? new Date(s.next_run_at).toLocaleString() : '—'}</span>
                        </div>
                        <button type="button" onClick={async () => { await deleteSchedule(s.id); await reload() }}>
                          <Trash2 size={14} />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {section === 'audit' && (
              <div className="workspace-section">
                <h3>Audit log</h3>
                {audit.length === 0 ? (
                  <EmptyState
                    compact
                    title="Quiet so far"
                    body="Tool calls and system events from chat will show up here."
                  />
                ) : (
                  <ul className="workspace-list compact">
                    {audit.map((a) => (
                      <li key={a.id}>
                        <div>
                          <strong>{a.kind}: {a.action}</strong>
                          <span className="workspace-muted">{a.detail || new Date(a.created_at).toLocaleString()}</span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {section === 'usage' && (
              <div className="workspace-section">
                <h3>Usage meter</h3>
                {!activeSessionId ? (
                  <EmptyState compact title="Select a chat" body="Token usage appears for the conversation you have open." />
                ) : !usage ? (
                  <LoadingSkeleton rows={3} />
                ) : (
                  <div className="workspace-stats">
                    <span>Prompt ≈ {usage.prompt_tokens}</span>
                    <span>Completion ≈ {usage.completion_tokens}</span>
                    <span>Total ≈ {usage.total_tokens}</span>
                  </div>
                )}
                <p className="workspace-muted">Estimates from message length (~4 chars/token), not billing APIs.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
