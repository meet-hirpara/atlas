import { useCallback, useEffect, useState } from 'react'
import Sidebar from './components/Sidebar'
import ChatArea from './components/ChatArea'
import InputArea from './components/InputArea'
import TerminalPanel from './components/TerminalPanel'
import DocumentPanel from './components/DocumentPanel'
import SettingsPanel from './components/SettingsPanel'
import OnboardingModal, { isOnboardingDone, type UseCase } from './components/OnboardingModal'
import WorkspacePanel, { type WorkspaceSection } from './components/WorkspacePanel'
import ArtifactsSidebar from './components/ArtifactsSidebar'
import AuthScreen from './components/AuthScreen'
import AdminPanel from './components/AdminPanel'
import ToastStack, { nextToastId, type ToastItem } from './components/Toast'
import LoadingSkeleton from './components/LoadingSkeleton'
import { TerminalProvider } from './context/TerminalContext'
import { useChat } from './hooks/useChat'
import { useSettings } from './hooks/useSettings'
import { useConnections } from './hooks/useConnections'
import { useDocuments } from './hooks/useDocuments'
import { useMcp } from './hooks/useMcp'
import { useGithub } from './hooks/useGithub'
import { useAuth } from './hooks/useAuth'
import { repoLabel } from './github'
import { ensureLocalAuthToken } from './utils/localAuth'
import { createProposal, exportChat, fetchProjects, type JobItem } from './workspace'
import type { AuthUser } from './authApi'

export default function App() {
  const auth = useAuth()

  if (auth.loading) {
    return (
      <div className="auth-screen">
        <div className="auth-loading-card">
          <p>Loading Atlas…</p>
          <LoadingSkeleton rows={3} />
        </div>
      </div>
    )
  }

  if (!auth.isAuthenticated) {
    return (
      <AuthScreen
        hasUsers={Boolean(auth.status?.has_users)}
        onLogin={async (email, password) => {
          await auth.login(email, password)
        }}
        onRegister={async (email, password) => {
          await auth.register(email, password)
        }}
      />
    )
  }

  return (
    <AtlasApp
      user={auth.user!}
      isAdmin={auth.isAdmin}
      onLogout={() => void auth.logout()}
    />
  )
}

function AtlasApp({
  user,
  isAdmin,
  onLogout,
}: {
  user: AuthUser
  isAdmin: boolean
  onLogout: () => void
}) {
  useEffect(() => {
    void ensureLocalAuthToken()
  }, [])

  const [toasts, setToasts] = useState<ToastItem[]>([])
  const notify = useCallback((message: string) => {
    setToasts((prev) => [...prev.slice(-3), { id: nextToastId(), message }])
  }, [])
  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const [adminOpen, setAdminOpen] = useState(
    () =>
      typeof window !== 'undefined' &&
      window.location.pathname.startsWith('/admin') &&
      isAdmin,
  )

  useEffect(() => {
    if (!isAdmin && window.location.pathname.startsWith('/admin')) {
      setAdminOpen(false)
      window.history.replaceState({}, '', '/')
    }
  }, [isAdmin])

  useEffect(() => {
    if (!isAdmin && adminOpen) setAdminOpen(false)
  }, [isAdmin, adminOpen])

  useEffect(() => {
    if (!isAdmin) return
    const sync = () => {
      if (window.location.pathname.startsWith('/admin')) setAdminOpen(true)
      else setAdminOpen(false)
    }
    window.addEventListener('popstate', sync)
    return () => window.removeEventListener('popstate', sync)
  }, [isAdmin])

  const {
    settings,
    updateSettings,
    resetSettings,
    isOpen,
    initialTab,
    mcpFocus,
    openSettings,
    closeSettings,
  } = useSettings()

  const {
    connections,
    loading: connectionsLoading,
    error: connectionsError,
    connect,
    disconnect,
  } = useConnections(true)

  const {
    presets: mcpPresets,
    servers: mcpServers,
    loading: mcpLoading,
    error: mcpError,
    connect: mcpConnect,
    remove: mcpRemove,
    test: mcpTest,
    toggle: mcpToggle,
  } = useMcp(true)

  const {
    repos: githubRepos,
    loading: githubLoading,
    error: githubError,
    add: githubAdd,
    remove: githubRemove,
  } = useGithub(true)

  const activeGithubRepos = githubRepos.filter(
    (r) => settings.activeGithubRepoIds.includes(r.id) && r.status === 'ready',
  )

  const handleGithubToggleActive = (id: string) => {
    const ids = settings.activeGithubRepoIds
    const next = ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]
    updateSettings({ activeGithubRepoIds: next })
  }

  const {
    sessions,
    activeSessionId,
    messages,
    streamingContent,
    routingMeta,
    activeModelDisplay,
    researchStatus,
    researchSources,
    webSources,
    youtubeVideos,
    docCitations,
    activeDocCitation,
    handleDocCitationClick,
    activityLog,
    isDeepResearch,
    isBuildMode,
    ephemeralAgent,
    handleDismissAgent,
    isStreaming,
    sidebarCollapsed,
    setSidebarCollapsed,
    handleNewChat,
    handleSelectSession,
    handleDeleteSession,
    handleRenameSession,
    handlePinSession,
    handleAssignProject,
    handleSend,
    handleClarificationReply,
    handleStop,
    handleRetry,
    turnStatus,
    ensureSession,
    injectAssistantMessage,
    handleMemoryHelp,
    handleMemoryAdd,
    handleMemoryClear,
  } = useChat(settings)

  const { documents, uploading, upload, remove } = useDocuments(activeSessionId)

  const [docPanelOpen, setDocPanelOpen] = useState(true)
  const [showOnboarding, setShowOnboarding] = useState(() => !isOnboardingDone())
  const [workspaceOpen, setWorkspaceOpen] = useState(false)
  const [workspaceSection, setWorkspaceSection] = useState<WorkspaceSection>('cockpit')
  const [artifactsOpen, setArtifactsOpen] = useState(false)
  const [projects, setProjects] = useState<{ id: string; name: string }[]>([])
  const [projectFilter, setProjectFilter] = useState<string | null>(null)

  const showDocPanel = documents.length > 0 || docCitations.length > 0 || Boolean(activeDocCitation)

  useEffect(() => {
    if (showDocPanel) setDocPanelOpen(true)
  }, [activeSessionId, showDocPanel])

  useEffect(() => {
    if (activeDocCitation) setDocPanelOpen(true)
  }, [activeDocCitation])

  useEffect(() => {
    document.body.classList.toggle('overlay-open', isOpen || workspaceOpen || showOnboarding || adminOpen)
    return () => document.body.classList.remove('overlay-open')
  }, [isOpen, workspaceOpen, showOnboarding, adminOpen])

  useEffect(() => {
    void fetchProjects()
      .then((list) => setProjects(list.map((p) => ({ id: p.id, name: p.name }))))
      .catch(() => setProjects([]))
  }, [workspaceOpen])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      if (isOpen || workspaceOpen || showOnboarding || adminOpen) return
      if (!sidebarCollapsed && window.innerWidth <= 768) {
        setSidebarCollapsed(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [sidebarCollapsed, setSidebarCollapsed, isOpen, workspaceOpen, showOnboarding, adminOpen])

  const openWorkspace = (section: WorkspaceSection = 'cockpit') => {
    setWorkspaceSection(section)
    setWorkspaceOpen(true)
  }

  const handleExport = async (sessionId: string) => {
    try {
      await exportChat(sessionId, 'markdown')
      notify('Exported — download started')
    } catch (e) {
      console.error(e)
    }
  }

  const handleSaveProposal = async (content: string) => {
    try {
      const title = content.trim().split('\n')[0].slice(0, 80) || 'Proposal draft'
      await createProposal({
        title,
        content,
        sessionId: activeSessionId || undefined,
      })
      notify('Proposal saved to workspace')
      openWorkspace('proposals')
    } catch (e) {
      console.error(e)
    }
  }

  const handlePin = async (id: string, pinned: boolean) => {
    await handlePinSession(id, pinned)
    notify(pinned ? 'Pinned to sidebar' : 'Unpinned')
  }

  const handleConnect = async (provider: string, data: Record<string, string>) => {
    await connect(provider, data)
    notify('Connected')
  }

  const handleMcpConnect = async (payload: {
    name: string
    preset: string
    transport: string
    command: string
    args: string[]
    url: string
    env?: Record<string, string>
  }) => {
    const result = await mcpConnect(payload)
    notify(`${payload.name || 'MCP'} connected`)
    return result
  }

  const handleGithubAdd = async (url: string, token: string, branch: string) => {
    const result = await githubAdd(url, token, branch)
    notify('Repository connected')
    return result
  }

  const handleDraftFromJob = (job: JobItem) => {
    setWorkspaceOpen(false)
    void handleSend(
      `Draft a freelance proposal for this job posting:\n\n${job.content}`,
    )
  }

  const handleRunSchedule = async (topic: string) => {
    setWorkspaceOpen(false)
    await handleSend(`Deep research: ${topic}`, { deepResearch: true })
  }

  const onOnboardingDone = (_useCase: UseCase) => {
    setShowOnboarding(false)
  }

  return (
    <TerminalProvider>
      <div className={`app-shell${sidebarCollapsed ? ' sidebar-is-collapsed' : ''}`}>
        {!sidebarCollapsed && (
          <button
            type="button"
            className="sidebar-backdrop"
            aria-label="Close sidebar"
            onClick={() => setSidebarCollapsed(true)}
          />
        )}
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
          onSelect={(id) => {
            handleSelectSession(id)
            if (window.innerWidth <= 768) setSidebarCollapsed(true)
          }}
          onNew={() => {
            handleNewChat()
            if (window.innerWidth <= 768) setSidebarCollapsed(true)
          }}
          onDelete={handleDeleteSession}
          onRename={handleRenameSession}
          onPin={handlePin}
          onExport={handleExport}
          onOpenSettings={openSettings}
          onOpenAdmin={
            isAdmin
              ? () => {
                  setAdminOpen(true)
                  if (!window.location.pathname.startsWith('/admin')) {
                    window.history.pushState({}, '', '/admin')
                  }
                }
              : undefined
          }
          onLogout={onLogout}
          userEmail={user.email}
          onOpenWorkspace={(section) => {
            openWorkspace(section)
            if (window.innerWidth <= 768) setSidebarCollapsed(true)
          }}
          onToggleArtifacts={() => {
            setArtifactsOpen((v) => !v)
            if (window.innerWidth <= 768) setSidebarCollapsed(true)
          }}
          projectFilter={projectFilter}
          projects={projects}
          onProjectFilter={setProjectFilter}
        />

        <div
          className="workspace"
          onClick={() => {
            if (!sidebarCollapsed && window.innerWidth <= 768) {
              setSidebarCollapsed(true)
            }
          }}
        >
          <main className="main-panel">
            <div className="main-workspace">
              <div className="chat-column">
                <ChatArea
                  messages={messages}
                  streamingContent={streamingContent}
                  routingMeta={routingMeta}
                  activityLog={activityLog}
                  researchStatus={researchStatus}
                  researchSources={researchSources}
                  webSources={webSources}
                  youtubeVideos={youtubeVideos}
                  docCitations={docCitations}
                  activeDocCitationId={activeDocCitation?.id ?? null}
                  onDocCitationClick={handleDocCitationClick}
                  isDeepResearch={isDeepResearch}
                  isBuildMode={isBuildMode}
                  ephemeralAgent={ephemeralAgent}
                  onDismissAgent={handleDismissAgent}
                  isStreaming={isStreaming}
                  onSuggestionClick={handleSend}
                  onClarificationReply={handleClarificationReply}
                  onConnectMcp={(intent) =>
                    openSettings(intent.tab, {
                      mcpFocus: intent.preset ?? null,
                    })
                  }
                  onQuickReply={handleSend}
                  onRetry={handleRetry}
                  onExportMd={activeSessionId ? () => void handleExport(activeSessionId) : undefined}
                  onSaveProposal={(content) => void handleSaveProposal(content)}
                  turnStatus={turnStatus}
                />
                <div className="chat-column-footer">
                  <TerminalPanel />
                  <InputArea
                    onSend={handleSend}
                    disabled={isStreaming}
                    isStreaming={isStreaming}
                    selectedModelId={settings.modelSelection}
                    onModelSelect={(id) => updateSettings({ modelSelection: id })}
                    activeModelDisplay={activeModelDisplay}
                    isDeepResearchStreaming={isDeepResearch && isStreaming}
                    researchPhase={researchStatus?.phase}
                    onStop={handleStop}
                    documents={documents}
                    uploading={uploading}
                    onUpload={async (files) => {
                      const sid = await ensureSession()
                      await upload(files, sid, settings.ocrModelSelection)
                    }}
                    onRemoveDocument={remove}
                    webSearchEnabled={settings.webSearchMode !== 'off'}
                    onWebSearchToggle={() =>
                      updateSettings({
                        webSearchMode: settings.webSearchMode === 'off' ? 'on' : 'off',
                      })
                    }
                    activeGithubRepos={activeGithubRepos.map((r) => ({
                      id: r.id,
                      label: repoLabel(r),
                    }))}
                    onOpenGithubSettings={() => openSettings('github')}
                    onNewChat={handleNewChat}
                    onOpenSettings={openSettings}
                    onSlashHelp={injectAssistantMessage}
                    onMemoryHelp={handleMemoryHelp}
                    onMemoryAdd={handleMemoryAdd}
                    onMemoryClear={handleMemoryClear}
                    recentUserMessages={messages
                      .filter((m) => m.role === 'user')
                      .slice(-3)
                      .map((m) => m.content)}
                  />
                </div>
              </div>

              {showDocPanel && (
                <DocumentPanel
                  documents={documents}
                  open={docPanelOpen}
                  onToggle={() => setDocPanelOpen((v) => !v)}
                  onRemove={remove}
                  activeCitation={activeDocCitation}
                  onSelectDocument={(docId) => {
                    const doc = documents.find((d) => d.id === docId)
                    if (!doc) return
                    setDocPanelOpen(true)
                    handleDocCitationClick({
                      id: 0,
                      document_id: doc.id,
                      filename: doc.filename,
                      chunk_index: 0,
                      page: 1,
                      snippet: '',
                      content: '',
                    })
                  }}
                />
              )}

              <ArtifactsSidebar
                sessionId={activeSessionId}
                open={artifactsOpen}
                onToggle={() => setArtifactsOpen((v) => !v)}
                onInsert={(content) => injectAssistantMessage(`Reused artifact:\n\n\`\`\`\n${content.slice(0, 4000)}\n\`\`\``)}
              />
            </div>
          </main>
        </div>

        {isOpen && (
          <SettingsPanel
            settings={settings}
            onChange={updateSettings}
            onReset={resetSettings}
            onClose={closeSettings}
            initialTab={initialTab}
            mcpFocus={mcpFocus}
            connections={connections}
            connectionsLoading={connectionsLoading}
            connectionsError={connectionsError}
            onConnect={handleConnect}
            onDisconnect={disconnect}
            mcpPresets={mcpPresets}
            mcpServers={mcpServers}
            mcpLoading={mcpLoading}
            mcpError={mcpError}
            onMcpConnect={handleMcpConnect}
            onMcpRemove={mcpRemove}
            onMcpTest={async (id) => {
              await mcpTest(id)
            }}
            onMcpToggle={mcpToggle}
            githubRepos={githubRepos}
            githubLoading={githubLoading}
            githubError={githubError}
            onGithubAdd={handleGithubAdd}
            onGithubRemove={githubRemove}
            onGithubToggleActive={handleGithubToggleActive}
          />
        )}

        <WorkspacePanel
          open={workspaceOpen}
          section={workspaceSection}
          onSection={setWorkspaceSection}
          onClose={() => setWorkspaceOpen(false)}
          activeSessionId={activeSessionId}
          onDraftProposal={handleDraftFromJob}
          onRunSchedule={(topic) => {
            void handleRunSchedule(topic)
          }}
          onAssignProject={(projectId) => {
            void handleAssignProject(projectId)
            notify(projectId ? 'Chat assigned to project' : 'Project cleared')
            void fetchProjects().then((list) =>
              setProjects(list.map((p) => ({ id: p.id, name: p.name }))),
            )
          }}
        />

        {showOnboarding && (
          <OnboardingModal
            onClose={onOnboardingDone}
            onOpenIntegrations={() => openSettings('connections')}
          />
        )}

        {isAdmin && (
          <AdminPanel
            open={adminOpen}
            onClose={() => {
              setAdminOpen(false)
              if (window.location.pathname.startsWith('/admin')) {
                window.history.pushState({}, '', '/')
              }
            }}
          />
        )}

        <ToastStack toasts={toasts} onDismiss={dismissToast} />
      </div>
    </TerminalProvider>
  )
}
