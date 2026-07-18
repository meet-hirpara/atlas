import { useState, useRef, useEffect, KeyboardEvent, useMemo, useCallback } from 'react'
import {
  ArrowUp,
  Square,
  Telescope,
  Plus,
  FileText,
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Globe,
  Terminal,
  GitFork,
  Mic,
  MicOff,
} from 'lucide-react'
import type { UploadedDocument } from '../documents'
import { formatFileSize } from '../documents'
import { useTerminal } from '../context/TerminalContext'
import { getComposerModelDisplay } from '../models'
import ModelPicker from './ModelPicker'
import SlashCommandMenu from './SlashCommandMenu'
import SlashCommandHints from './SlashCommandHints'
import {
  parseSlashInput,
  filterSlashCommands,
  executeSlashCommand,
  commandInsertText,
  buildHelpMessage,
  buildSuggestionInput,
  shouldShowSlashHints,
  getComposerPlaceholder,
  getResearchSuggestions,
  type SlashCommandContext,
  type SlashCommand,
} from '../utils/slashCommands'
import type { SettingsTabId } from '../utils/connectIntent'

interface Props {
  onSend: (message: string, options?: { deepResearch?: boolean }) => void
  disabled: boolean
  isStreaming: boolean
  isDeepResearchStreaming?: boolean
  researchPhase?: string
  onStop?: () => void
  documents?: UploadedDocument[]
  uploading?: boolean
  onUpload?: (files: FileList) => void
  onRemoveDocument?: (id: string) => void
  webSearchEnabled?: boolean
  onWebSearchToggle?: () => void
  activeGithubRepos?: { id: string; label: string }[]
  onOpenGithubSettings?: () => void
  selectedModelId?: string
  onModelSelect?: (id: string) => void
  activeModelDisplay?: string | null
  onNewChat?: () => void
  onOpenSettings?: (tab?: SettingsTabId, options?: { mcpFocus?: string | null }) => void
  onSlashHelp?: (message: string) => void
  onMemoryHelp?: () => void
  onMemoryAdd?: (text: string) => void
  onMemoryClear?: () => void
  recentUserMessages?: string[]
}

function DocStatusIcon({ status }: { status: UploadedDocument['status'] }) {
  if (status === 'ready') return <CheckCircle2 size={12} className="composer-attach-ok" />
  if (status === 'failed') return <AlertCircle size={12} className="composer-attach-err" />
  return <Loader2 size={12} className="composer-attach-spin" />
}

export default function InputArea({
  onSend,
  disabled,
  isStreaming,
  isDeepResearchStreaming = false,
  researchPhase,
  onStop,
  documents = [],
  uploading = false,
  onUpload,
  onRemoveDocument,
  webSearchEnabled = true,
  onWebSearchToggle,
  activeGithubRepos = [],
  onOpenGithubSettings,
  selectedModelId = 'mistral-large',
  onModelSelect,
  activeModelDisplay = null,
  onNewChat,
  onOpenSettings,
  onSlashHelp,
  onMemoryHelp,
  onMemoryAdd,
  onMemoryClear,
  recentUserMessages = [],
}: Props) {
  const [input, setInput] = useState('')
  const [deepResearch, setDeepResearch] = useState(false)
  const [researchSuggestions, setResearchSuggestions] = useState<string[]>([])
  const [menuOpen, setMenuOpen] = useState(false)
  const [listening, setListening] = useState(false)
  const recognitionRef = useRef<SpeechRecognition | null>(null)

  const speechSupported =
    typeof window !== 'undefined' &&
    Boolean((window as unknown as { SpeechRecognition?: unknown; webkitSpeechRecognition?: unknown }).SpeechRecognition
      || (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition)

  const toggleVoice = useCallback(() => {
    if (!speechSupported) return
    const SR =
      (window as unknown as { SpeechRecognition?: new () => SpeechRecognition }).SpeechRecognition ||
      (window as unknown as { webkitSpeechRecognition?: new () => SpeechRecognition }).webkitSpeechRecognition
    if (!SR) return

    if (listening && recognitionRef.current) {
      recognitionRef.current.stop()
      setListening(false)
      return
    }

    const recognition = new SR()
    recognition.lang = 'en-US'
    recognition.interimResults = true
    recognition.continuous = false
    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let transcript = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript
      }
      if (transcript) {
        setInput((prev) => (prev ? `${prev.trim()} ${transcript.trim()}` : transcript.trim()))
      }
    }
    recognition.onerror = () => setListening(false)
    recognition.onend = () => setListening(false)
    recognitionRef.current = recognition
    recognition.start()
    setListening(true)
  }, [listening, speechSupported])
  const [slashIndex, setSlashIndex] = useState(0)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const plusRef = useRef<HTMLButtonElement>(null)
  const { open: terminalOpen, openPanel, close: closeTerminal } = useTerminal()

  const slashParsed = parseSlashInput(input)
  const slashMenuOpen = slashParsed.menuOpen
  const hintCommand = shouldShowSlashHints(input)
  const filteredCommands = useMemo(
    () => (slashMenuOpen ? filterSlashCommands(slashParsed.menuQuery) : []),
    [slashMenuOpen, slashParsed.menuQuery],
  )

  const composerPlaceholder = getComposerPlaceholder(
    input,
    deepResearch,
    'Send a message…  (type / for commands)',
  )

  useEffect(() => {
    setSlashIndex(0)
  }, [slashParsed.menuQuery])

  useEffect(() => {
    if (hintCommand?.name === 'research') {
      setResearchSuggestions(getResearchSuggestions(recentUserMessages))
    }
  }, [hintCommand?.name, input, recentUserMessages])

  useEffect(() => {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`
    }
  }, [input])

  useEffect(() => {
    if (!menuOpen) return
    const onPointerDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (menuRef.current?.contains(t) || plusRef.current?.contains(t)) return
      setMenuOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [menuOpen])

  const slashContext = useCallback((): SlashCommandContext => ({
    onHelp: () => onSlashHelp?.(buildHelpMessage()),
    onNewChat: () => onNewChat?.(),
    onOpenSettings: (tab, options) => onOpenSettings?.(tab, options),
    onToggleWebSearch: () => onWebSearchToggle?.(),
    onToggleTerminal: () => (terminalOpen ? closeTerminal() : openPanel()),
    onPickPdf: () => fileInputRef.current?.click(),
    onModelSelect: (id) => onModelSelect?.(id),
    setDeepResearch,
    webSearchEnabled,
    onMemoryHelp: () => onMemoryHelp?.(),
    onMemoryAdd: (text) => onMemoryAdd?.(text),
    onMemoryClear: () => onMemoryClear?.(),
  }), [
    onSlashHelp,
    onNewChat,
    onOpenSettings,
    onWebSearchToggle,
    terminalOpen,
    closeTerminal,
    openPanel,
    onModelSelect,
    webSearchEnabled,
    onMemoryHelp,
    onMemoryAdd,
    onMemoryClear,
  ])

  const runSlashCommand = useCallback((text: string) => {
    let pendingDeepResearch = deepResearch
    const base = slashContext()
    const ctx: SlashCommandContext = {
      ...base,
      setDeepResearch: (enabled) => {
        pendingDeepResearch = enabled
        setDeepResearch(enabled)
      },
    }
    const result = executeSlashCommand(text, ctx)
    if (result.type === 'handled') {
      setInput('')
      return true
    }
    if (result.type === 'insert') {
      setInput(result.text)
      return true
    }
    if (result.type === 'send') {
      onSend(result.message, { deepResearch: result.deepResearch ?? pendingDeepResearch })
      setInput('')
      setDeepResearch(false)
      if (textareaRef.current) textareaRef.current.style.height = 'auto'
      return true
    }
    return false
  }, [deepResearch, onSend, slashContext])

  const handleSend = () => {
    const trimmed = input.trim()
    if (!trimmed || disabled || trimmed === '/') return
    if (trimmed.startsWith('/') && runSlashCommand(trimmed)) return
    onSend(trimmed, { deepResearch })
    setInput('')
    setDeepResearch(false)
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const selectSlashCommand = (cmd: SlashCommand) => {
    const chained = slashParsed.command && slashParsed.args.trimStart().startsWith('/')
    const text = commandInsertText(cmd)

    if (chained) {
      const chainStart = input.indexOf('/', input.indexOf(' ') + 1)
      const prefix = input.slice(0, chainStart)
      const next = `${prefix}${text}`
      if (cmd.acceptsArgs) {
        setInput(next)
        textareaRef.current?.focus()
        return
      }
      runSlashCommand(next)
      return
    }

    if (cmd.acceptsArgs) {
      const result = executeSlashCommand(text, slashContext())
      if (result.type === 'insert') {
        setInput(result.text)
        textareaRef.current?.focus()
        return
      }
      if (result.type === 'handled') {
        setInput(text)
        textareaRef.current?.focus()
        return
      }
      if (result.type === 'send') {
        onSend(result.message, { deepResearch: result.deepResearch ?? deepResearch })
        setInput('')
        setDeepResearch(false)
        return
      }
    }
    runSlashCommand(text)
  }

  const handleSuggestionClick = useCallback((suggestion: string) => {
    if (!hintCommand || disabled) return
    const chained = slashParsed.command && slashParsed.args.trimStart().startsWith('/')
    const cmdInput = buildSuggestionInput(hintCommand, suggestion)
    const text = chained
      ? `${input.slice(0, input.indexOf('/', input.indexOf(' ') + 1))}${cmdInput}`
      : cmdInput
    runSlashCommand(text)
  }, [hintCommand, disabled, runSlashCommand, slashParsed.command, slashParsed.args, input])

  const handleKeyDown = (e: KeyboardEvent) => {
    if (slashMenuOpen && filteredCommands.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSlashIndex((i) => (i + 1) % filteredCommands.length)
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSlashIndex((i) => (i - 1 + filteredCommands.length) % filteredCommands.length)
        return
      }
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
        e.preventDefault()
        const cmd = filteredCommands[slashIndex]
        if (cmd) selectSlashCommand(cmd)
        return
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        setInput('')
        return
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const pickPdf = () => {
    setMenuOpen(false)
    fileInputRef.current?.click()
  }

  const hasAttachments = documents.length > 0 || uploading || activeGithubRepos.length > 0

  const researchLabel =
    researchPhase === 'writing'
      ? 'Writing report…'
      : researchPhase === 'analyzing'
        ? 'Analyzing sources…'
        : researchPhase === 'searching'
          ? 'Searching the web…'
          : 'Researching…'

  const chipDisplay =
    activeModelDisplay ?? getComposerModelDisplay(selectedModelId)

  return (
    <footer className="composer">
      <div className="composer-inner">
        <div className={`composer-box${deepResearch || isDeepResearchStreaming ? ' composer-box-deep' : ''}`}>
          {(deepResearch || isDeepResearchStreaming) && (
            <div className="deep-research-banner">
              <Telescope size={14} className={isDeepResearchStreaming ? 'deep-research-banner-pulse' : ''} />
              <span>
                {isDeepResearchStreaming
                  ? researchLabel
                  : 'Deep research — multi-step web search with a cited report'}
              </span>
            </div>
          )}
          {hasAttachments && (
            <div className="composer-attachments">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className={`composer-attach-chip composer-attach-${doc.status}`}
                  title={doc.filename}
                >
                  <FileText size={14} className="composer-attach-file-icon" />
                  <span className="composer-attach-name">{doc.filename}</span>
                  <span className="composer-attach-meta">
                    {doc.status === 'ready'
                      ? formatFileSize(doc.file_size)
                      : doc.status === 'failed'
                        ? 'Failed'
                        : 'Processing…'}
                  </span>
                  <DocStatusIcon status={doc.status} />
                  {onRemoveDocument && (
                    <button
                      type="button"
                      className="composer-attach-remove"
                      onClick={() => onRemoveDocument(doc.id)}
                      aria-label={`Remove ${doc.filename}`}
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              ))}
              {uploading && documents.length === 0 && (
                <div className="composer-attach-chip composer-attach-processing">
                  <Loader2 size={14} className="composer-attach-spin" />
                  <span className="composer-attach-name">Uploading…</span>
                </div>
              )}
              {activeGithubRepos.map((repo) => (
                <button
                  key={repo.id}
                  type="button"
                  className="composer-attach-chip composer-attach-ready composer-attach-github"
                  title={`GitHub context: ${repo.label}`}
                  onClick={() => onOpenGithubSettings?.()}
                >
                  <GitFork size={14} className="composer-attach-file-icon" />
                  <span className="composer-attach-name">{repo.label}</span>
                  <span className="composer-attach-meta">Repo context</span>
                </button>
              ))}
            </div>
          )}

          <div className="composer-row">
            {slashMenuOpen && (
              <SlashCommandMenu
                commands={filteredCommands}
                selectedIndex={slashIndex}
                query={slashParsed.menuQuery}
                onSelect={selectSlashCommand}
                onHover={setSlashIndex}
              />
            )}
            {hintCommand && (
              <SlashCommandHints
                command={hintCommand}
                suggestions={
                  hintCommand.name === 'research' ? researchSuggestions : undefined
                }
                onSuggestionClick={handleSuggestionClick}
                disabled={disabled && !isStreaming}
              />
            )}
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={composerPlaceholder}
              rows={1}
              disabled={disabled && !isStreaming}
              className="composer-input"
            />

            <div className="composer-toolbar">
              <div className="composer-toolbar-left">
                <div className="composer-plus-wrap" ref={menuRef}>
                  <button
                    ref={plusRef}
                    type="button"
                    className={`composer-btn composer-btn-plus${menuOpen ? ' active' : ''}`}
                    title="Add attachment"
                    aria-expanded={menuOpen}
                    aria-haspopup="menu"
                    disabled={disabled && !isStreaming}
                    onClick={() => setMenuOpen((v) => !v)}
                  >
                    <Plus size={18} strokeWidth={2.25} />
                  </button>
                  {menuOpen && (
                    <div className="composer-menu" role="menu">
                      <button
                        type="button"
                        className="composer-menu-item"
                        role="menuitem"
                        onClick={pickPdf}
                        disabled={disabled || uploading}
                      >
                        <FileText size={16} />
                        <span>
                          <strong>Upload PDF</strong>
                          <small>Add documents for the assistant to read</small>
                        </span>
                      </button>
                    </div>
                  )}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,application/pdf"
                    multiple
                    hidden
                    onChange={(e) => {
                      if (e.target.files?.length && onUpload) onUpload(e.target.files)
                      e.target.value = ''
                    }}
                  />
                </div>
                <ModelPicker
                  selectedId={selectedModelId}
                  displayName={chipDisplay}
                  onSelect={(id) => onModelSelect?.(id)}
                  disabled={disabled && !isStreaming}
                />
              </div>

              <div className="composer-actions">
                {!isStreaming && (
                  <button
                    type="button"
                    onClick={() => (terminalOpen ? closeTerminal() : openPanel())}
                    className={`composer-btn composer-btn-mode${terminalOpen ? ' active' : ''}`}
                    title="Terminal"
                    aria-pressed={terminalOpen}
                  >
                    <Terminal size={16} />
                  </button>
                )}
                {onWebSearchToggle && (
                  <button
                    type="button"
                    onClick={onWebSearchToggle}
                    disabled={deepResearch || isStreaming}
                    className={`composer-btn composer-btn-mode${
                      deepResearch || webSearchEnabled ? ' active' : ' off'
                    }${deepResearch ? ' locked' : ''}`}
                    title={
                      deepResearch
                        ? 'Internet always on in deep research'
                        : isStreaming
                          ? 'Web search (change after response finishes)'
                          : webSearchEnabled
                            ? 'Web search on — click to disable'
                            : 'Web search off — click to enable'
                    }
                    aria-pressed={deepResearch || webSearchEnabled}
                    aria-disabled={deepResearch || isStreaming}
                  >
                    <Globe size={16} />
                  </button>
                )}
                {!isStreaming && (
                  <button
                    type="button"
                    onClick={() => setDeepResearch((v) => !v)}
                    className={`composer-btn composer-btn-mode${deepResearch ? ' active' : ''}`}
                    title="Deep research"
                    aria-pressed={deepResearch}
                  >
                    <Telescope size={16} />
                  </button>
                )}
                <button
                  type="button"
                  onClick={toggleVoice}
                  disabled={!speechSupported || (disabled && !isStreaming)}
                  className={`composer-btn composer-btn-mode${listening ? ' active' : ''}${!speechSupported ? ' off' : ''}`}
                  title={
                    speechSupported
                      ? listening
                        ? 'Stop voice input'
                        : 'Voice input'
                      : 'Voice input not supported in this browser'
                  }
                  aria-pressed={listening}
                  aria-label="Voice input"
                >
                  {listening ? <MicOff size={16} /> : <Mic size={16} />}
                </button>
                {isStreaming ? (
                  <button type="button" onClick={onStop} className="composer-btn composer-btn-stop" title="Stop">
                    <Square size={14} fill="currentColor" />
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={handleSend}
                    disabled={!input.trim() || disabled}
                    className="composer-btn composer-btn-send"
                    title="Send"
                  >
                    <ArrowUp size={18} strokeWidth={2.5} />
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
}
