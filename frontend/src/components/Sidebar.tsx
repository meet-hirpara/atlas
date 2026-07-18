import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import {
  Plus, Trash2, PanelLeftClose, PanelLeft, Settings, Pencil, Pin, Download,
  Briefcase, ChevronDown, Layers, Shield, LogOut,
} from 'lucide-react'
import type { ChatSession } from '../api'
import { APP_DISPLAY_NAME, APP_NAME } from '../brand'
import LampLogo from './LampLogo'
import EmptyState from './EmptyState'
import type { WorkspaceSection } from './WorkspacePanel'

interface Props {
  sessions: ChatSession[]
  activeSessionId: string | null
  collapsed: boolean
  onToggle: () => void
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  onRename: (id: string, title: string) => void
  onPin?: (id: string, pinned: boolean) => void
  onExport?: (id: string) => void
  onOpenSettings: () => void
  onOpenAdmin?: () => void
  onLogout?: () => void
  userEmail?: string | null
  onOpenWorkspace?: (section?: WorkspaceSection) => void
  onToggleArtifacts?: () => void
  projectFilter?: string | null
  projects?: { id: string; name: string }[]
  onProjectFilter?: (id: string | null) => void
}

function greetName(email: string | null | undefined): string | null {
  if (!email) return null
  const local = email.split('@')[0]?.trim()
  if (!local) return null
  const part = local.split(/[._-]/)[0] || local
  return part.charAt(0).toUpperCase() + part.slice(1)
}

export default function Sidebar({
  sessions,
  activeSessionId,
  collapsed,
  onToggle,
  onSelect,
  onNew,
  onDelete,
  onRename,
  onPin,
  onExport,
  onOpenSettings,
  onOpenAdmin,
  onLogout,
  userEmail,
  onOpenWorkspace,
  onToggleArtifacts,
  projectFilter = null,
  projects = [],
  onProjectFilter,
}: Props) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [toolsOpen, setToolsOpen] = useState(false)
  const editInputRef = useRef<HTMLInputElement>(null)
  const name = greetName(userEmail)

  useEffect(() => {
    if (editingId && editInputRef.current) {
      editInputRef.current.focus()
      editInputRef.current.select()
    }
  }, [editingId])

  const startRename = (session: ChatSession) => {
    setEditingId(session.id)
    setEditTitle(session.title)
  }

  const commitRename = (id: string) => {
    const trimmed = editTitle.trim()
    setEditingId(null)
    if (!trimmed) return
    const session = sessions.find((s) => s.id === id)
    if (session && trimmed !== session.title) {
      onRename(id, trimmed)
    }
  }

  const cancelRename = () => {
    setEditingId(null)
    setEditTitle('')
  }

  const handleEditKeyDown = (e: KeyboardEvent<HTMLInputElement>, id: string) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      commitRename(id)
    } else if (e.key === 'Escape') {
      e.preventDefault()
      cancelRename()
    }
  }

  const visible = projectFilter
    ? sessions.filter((s) => s.project_id === projectFilter)
    : sessions
  const pinned = visible.filter((s) => s.pinned)
  const rest = visible.filter((s) => !s.pinned)

  if (collapsed) {
    return (
      <aside className="sidebar sidebar-collapsed">
        <button type="button" onClick={onToggle} className="sidebar-ghost-btn" title="Open sidebar">
          <PanelLeft size={18} />
        </button>
        <button type="button" onClick={onNew} className="sidebar-ghost-btn" title="New chat">
          <Plus size={18} />
        </button>
        {onOpenWorkspace && (
          <button type="button" onClick={() => onOpenWorkspace('cockpit')} className="sidebar-ghost-btn" title="Workspace">
            <Briefcase size={18} />
          </button>
        )}
        <button type="button" onClick={() => onOpenSettings()} className="sidebar-ghost-btn" title="Settings">
          <Settings size={18} />
        </button>
        {onOpenAdmin && (
          <button type="button" onClick={onOpenAdmin} className="sidebar-ghost-btn" title="Admin">
            <Shield size={18} />
          </button>
        )}
        {onLogout && (
          <button type="button" onClick={onLogout} className="sidebar-ghost-btn" title="Sign out">
            <LogOut size={18} />
          </button>
        )}
      </aside>
    )
  }

  const renderSession = (session: ChatSession) => (
    <div
      key={session.id}
      role="button"
      tabIndex={0}
      className={`sidebar-chat ${activeSessionId === session.id ? 'sidebar-chat-active' : ''}${session.pinned ? ' sidebar-chat-pinned' : ''}`}
      onClick={() => editingId !== session.id && onSelect(session.id)}
      onKeyDown={(e) => e.key === 'Enter' && editingId !== session.id && onSelect(session.id)}
      onDoubleClick={(e) => {
        e.stopPropagation()
        startRename(session)
      }}
    >
      {editingId === session.id ? (
        <input
          ref={editInputRef}
          className="sidebar-chat-edit"
          value={editTitle}
          onChange={(e) => setEditTitle(e.target.value)}
          onBlur={() => commitRename(session.id)}
          onKeyDown={(e) => handleEditKeyDown(e, session.id)}
          onClick={(e) => e.stopPropagation()}
          aria-label="Rename chat"
        />
      ) : (
        <span className="sidebar-chat-title">
          {session.pinned ? <Pin size={12} className="sidebar-pin-icon" /> : null}
          {session.title}
        </span>
      )}
      {editingId !== session.id && (
        <div className="sidebar-chat-actions">
          {onPin && (
            <button
              type="button"
              className="sidebar-chat-rename"
              onClick={(e) => { e.stopPropagation(); onPin(session.id, !session.pinned) }}
              aria-label={session.pinned ? 'Unpin chat' : 'Pin chat'}
              title={session.pinned ? 'Unpin' : 'Pin'}
            >
              <Pin size={14} />
            </button>
          )}
          {onExport && activeSessionId === session.id && (
            <button
              type="button"
              className="sidebar-chat-rename"
              onClick={(e) => { e.stopPropagation(); onExport(session.id) }}
              aria-label="Export chat"
              title="Export"
            >
              <Download size={14} />
            </button>
          )}
          <button
            type="button"
            className="sidebar-chat-rename"
            onClick={(e) => { e.stopPropagation(); startRename(session) }}
            aria-label="Rename chat"
          >
            <Pencil size={14} />
          </button>
          <button
            type="button"
            className="sidebar-chat-delete"
            onClick={(e) => { e.stopPropagation(); onDelete(session.id) }}
            aria-label="Delete chat"
          >
            <Trash2 size={14} />
          </button>
        </div>
      )}
    </div>
  )

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <span className="sidebar-brand">
          <LampLogo size={20} className="sidebar-brand-logo" label={APP_DISPLAY_NAME} />
          <span className="sidebar-brand-name">{APP_NAME}</span>
        </span>
        <button type="button" onClick={onToggle} className="sidebar-ghost-btn" title="Close sidebar">
          <PanelLeftClose size={17} />
        </button>
      </div>

      <div className="sidebar-actions">
        <button type="button" onClick={onNew} className="sidebar-new-chat">
          <Plus size={16} strokeWidth={2} />
          New chat
        </button>
      </div>

      {onOpenWorkspace && (
        <div className="sidebar-tools">
          <button
            type="button"
            className="sidebar-workspace-btn"
            onClick={() => onOpenWorkspace('cockpit')}
          >
            <Briefcase size={15} />
            <span>Workspace</span>
          </button>
          {onToggleArtifacts && (
            <div className="sidebar-tools-more">
              <button
                type="button"
                className="sidebar-tools-toggle"
                aria-expanded={toolsOpen}
                onClick={() => setToolsOpen((v) => !v)}
              >
                <span>More tools</span>
                <ChevronDown size={14} className={toolsOpen ? 'sidebar-chevron-open' : undefined} />
              </button>
              {toolsOpen && (
                <div className="sidebar-tools-menu">
                  <button type="button" onClick={() => onOpenWorkspace('projects')}>
                    Projects
                  </button>
                  <button type="button" onClick={onToggleArtifacts}>
                    <Layers size={13} /> Saved outputs
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {projects.length > 0 && onProjectFilter && (
        <div className="sidebar-project-filter">
          <select
            value={projectFilter || ''}
            onChange={(e) => onProjectFilter(e.target.value || null)}
            aria-label="Filter by project"
          >
            <option value="">All chats</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
      )}

      <nav className="sidebar-nav" aria-label="Chat history">
        {visible.length === 0 ? (
          <div className="sidebar-empty">
            {projectFilter ? (
              <EmptyState
                compact
                title="Nothing in this project yet"
                body="Open Workspace → Projects to assign a chat, or start a new one."
                actionLabel="New chat"
                onAction={onNew}
              />
            ) : (
              <EmptyState
                compact
                title="No chats yet"
                body="Tap New chat above — your conversations will show up here."
                actionLabel="New chat"
                onAction={onNew}
              />
            )}
          </div>
        ) : (
          <>
            {pinned.length > 0 && (
              <div className="sidebar-section-label">Pinned</div>
            )}
            {pinned.map(renderSession)}
            {pinned.length > 0 && rest.length > 0 && (
              <div className="sidebar-section-label">Recent</div>
            )}
            {rest.map(renderSession)}
          </>
        )}
      </nav>

      <div className="sidebar-footer">
        {userEmail && (
          <div className="sidebar-user">
            <p className="sidebar-user-greet">{name ? `Hey, ${name}` : 'Signed in'}</p>
            <p className="sidebar-user-email" title={userEmail}>{userEmail}</p>
          </div>
        )}
        {onOpenAdmin && (
          <button type="button" className="sidebar-settings-btn" onClick={onOpenAdmin}>
            <Shield size={16} />
            Admin
          </button>
        )}
        <button type="button" className="sidebar-settings-btn" onClick={() => onOpenSettings()}>
          <Settings size={16} />
          Settings
        </button>
        {onLogout && (
          <button type="button" className="sidebar-settings-btn" onClick={onLogout}>
            <LogOut size={16} />
            Sign out
          </button>
        )}
      </div>
    </aside>
  )
}
