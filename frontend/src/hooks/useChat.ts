import { useState, useEffect, useCallback, useRef } from 'react'
import { getComposerModelDisplay } from '../models'

import {

  fetchSessions,

  createSession,

  deleteSession,

  renameSession,

  fetchMessages,

  persistMessages,

  fetchSessionAgent,

  dismissSessionAgent,

  streamChat,

  researchToActivity,

  chatActivityToItem,

  type ChatSession,

  type ChatMessage,

  type ResearchStatus,

  type ChatActivityStatus,

  type ActivityItem,

  type ActivityPhase,

  type ResearchSource,

  type WebSearchSource,

  type DocumentCitation,

  type ClarificationRequest,

  type EphemeralAgent,

  type YouTubeVideo,

} from '../api'

import { encodeClarificationMessage } from '../utils/clarification'

import type { BotSettings } from '../settings'
import { settingsWithMemory } from '../settings'
import {
  tryParseMemoryCommand,
  addMemoryItem,
  clearMemoryItems,
  buildMemoryHelpMessage,
} from '../utils/userMemory'
import {
  tryParseConnectIntent,
  encodeConnectMessage,
} from '../utils/connectIntent'



export type { ActivityItem }



function makeActivityItem(

  label: string,

  detail: string,

  phase: ActivityPhase,

  state: 'active' | 'done' = 'active',

): ActivityItem {

  return {

    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,

    label,

    detail,

    phase,

    state,

  }

}



function appendActivity(

  prev: ActivityItem[],

  input: Pick<ActivityItem, 'label' | 'detail' | 'phase'>,

): ActivityItem[] {

  const done = prev.map((a) => (a.state === 'active' ? { ...a, state: 'done' as const } : a))



  const last = done[done.length - 1]

  if (last && last.label === input.label && last.detail === input.detail && last.phase === input.phase) {

    return [...done.slice(0, -1), { ...last, state: 'active' }]

  }



  return [

    ...done,

    makeActivityItem(input.label, input.detail, input.phase, 'active'),

  ]

}



function appendResearchActivity(prev: ActivityItem[], status: ResearchStatus): ActivityItem[] {

  return appendActivity(prev, researchToActivity(status))

}



function appendChatActivity(prev: ActivityItem[], status: ChatActivityStatus): ActivityItem[] {

  return appendActivity(prev, chatActivityToItem(status))

}



function transitionToWriting(prev: ActivityItem[]): ActivityItem[] {

  const done = prev.map((a) => ({ ...a, state: 'done' as const }))

  const hasWriting = done.some((a) => a.phase === 'writing')

  if (hasWriting) return done

  return [

    ...done,

    makeActivityItem('Writing', 'Composing response', 'writing', 'active'),

  ]

}



export function useChat(settings: BotSettings) {

  const [sessions, setSessions] = useState<ChatSession[]>([])

  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)

  const [messages, setMessages] = useState<ChatMessage[]>([])

  const [streamingContent, setStreamingContent] = useState('')

  const [routingMeta, setRoutingMeta] = useState<string | null>(null)

  const [activeModelDisplay, setActiveModelDisplay] = useState<string | null>(
    () => getComposerModelDisplay(settings.modelSelection),
  )

  const [researchStatus, setResearchStatus] = useState<ResearchStatus | null>(null)

  const [researchSources, setResearchSources] = useState<ResearchSource[]>([])

  const [webSources, setWebSources] = useState<WebSearchSource[]>([])

  const [youtubeVideos, setYoutubeVideos] = useState<YouTubeVideo[]>([])

  const [docCitations, setDocCitations] = useState<DocumentCitation[]>([])

  const [activeDocCitation, setActiveDocCitation] = useState<DocumentCitation | null>(null)

  const [activityLog, setActivityLog] = useState<ActivityItem[]>([])

  const [isDeepResearch, setIsDeepResearch] = useState(false)

  const [isBuildMode, setIsBuildMode] = useState(false)

  const [ephemeralAgent, setEphemeralAgent] = useState<EphemeralAgent | null>(null)

  const [isStreaming, setIsStreaming] = useState(false)

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const abortRef = useRef(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  const lastFailedMessageRef = useRef<string | null>(null)
  const [turnStatus, setTurnStatus] = useState<'ok' | 'stopped' | 'failed'>('ok')

  const reasoningTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const streamBufferRef = useRef('')

  const streamFlushRafRef = useRef<number | null>(null)

  const writingTransitionedRef = useRef(false)

  const cancelStreamFlush = useCallback(() => {
    if (streamFlushRafRef.current !== null) {
      cancelAnimationFrame(streamFlushRafRef.current)
      streamFlushRafRef.current = null
    }
  }, [])

  const flushStreamingBuffer = useCallback(() => {
    streamFlushRafRef.current = null
    setStreamingContent(streamBufferRef.current)
  }, [])

  const scheduleStreamingFlush = useCallback(() => {
    if (streamFlushRafRef.current !== null) return
    streamFlushRafRef.current = requestAnimationFrame(flushStreamingBuffer)
  }, [flushStreamingBuffer])

  const resetStreamBuffer = useCallback(() => {
    cancelStreamFlush()
    streamBufferRef.current = ''
    writingTransitionedRef.current = false
  }, [cancelStreamFlush])



  const clearReasoningTimer = () => {

    if (reasoningTimerRef.current) {

      clearTimeout(reasoningTimerRef.current)

      reasoningTimerRef.current = null

    }

  }



  const loadSessions = useCallback(async () => {

    try {

      const data = await fetchSessions()

      setSessions(data)

    } catch (e) {

      console.error('Failed to load sessions:', e)

    }

  }, [])



  const loadMessages = useCallback(async (sessionId: string) => {

    try {

      const data = await fetchMessages(sessionId)

      setMessages(data)

    } catch (e) {

      console.error('Failed to load messages:', e)

    }

  }, [])



  const loadSessionAgent = useCallback(async (sessionId: string) => {

    try {

      const agent = await fetchSessionAgent(sessionId)

      setEphemeralAgent(agent)

    } catch (e) {

      console.error('Failed to load session agent:', e)

      setEphemeralAgent(null)

    }

  }, [])



  useEffect(() => {

    loadSessions()

  }, [loadSessions])



  useEffect(() => {
    setActiveModelDisplay(getComposerModelDisplay(settings.modelSelection))
  }, [settings.modelSelection])



  useEffect(() => {

    if (activeSessionId) {

      loadMessages(activeSessionId)

      loadSessionAgent(activeSessionId)

    } else {

      setMessages([])

      setEphemeralAgent(null)

    }

  }, [activeSessionId, loadMessages, loadSessionAgent])



  useEffect(() => () => {
    clearReasoningTimer()
    cancelStreamFlush()
  }, [cancelStreamFlush])



  const handleNewChat = async () => {

    try {

      const session = await createSession()

      setSessions((prev) => [session, ...prev])

      setActiveSessionId(session.id)

      setMessages([])

      setStreamingContent('')

    } catch (e) {

      console.error('Failed to create session:', e)

    }

  }



  const handleSelectSession = (id: string) => {

    if (isStreaming) return

    setActiveSessionId(id)

    setStreamingContent('')

    setActiveDocCitation(null)

    setDocCitations([])

  }



  const handleDeleteSession = async (id: string) => {

    try {

      await deleteSession(id)

      setSessions((prev) => prev.filter((s) => s.id !== id))

      if (activeSessionId === id) {

        setActiveSessionId(null)

        setMessages([])

      }

    } catch (e) {

      console.error('Failed to delete session:', e)

    }

  }



  const handleRenameSession = async (id: string, title: string) => {

    try {

      const updated = await renameSession(id, title)

      setSessions((prev) => prev.map((s) => (s.id === id ? updated : s)))

    } catch (e) {

      console.error('Failed to rename session:', e)

    }

  }



  const notifyResearchComplete = (topic: string) => {

    if (typeof Notification === 'undefined') return

    if (Notification.permission !== 'granted') return

    try {

      new Notification('Deep research complete', {

        body: topic.length > 80 ? `${topic.slice(0, 80)}…` : topic,

        tag: 'nexus-deep-research',

      })

    } catch {

      // ignore notification errors

    }

  }



  const handleDismissAgent = async () => {

    if (!activeSessionId || !ephemeralAgent) return

    try {

      await dismissSessionAgent(activeSessionId, ephemeralAgent.id)

      setEphemeralAgent(null)

    } catch (e) {

      console.error('Failed to dismiss agent:', e)

    }

  }



  const injectAssistantMessage = useCallback((content: string) => {
    const msg: ChatMessage = {
      id: `cmd-${Date.now()}`,
      session_id: activeSessionId ?? '',
      role: 'assistant',
      content,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, msg])
  }, [activeSessionId])

  const handleMemoryHelp = useCallback(() => {
    injectAssistantMessage(buildMemoryHelpMessage())
  }, [injectAssistantMessage])

  const handleMemoryAdd = useCallback((text: string) => {
    const item = addMemoryItem(text)
    injectAssistantMessage(
      item ? `Saved to memory: **${item.text}**` : 'Nothing to save.',
    )
  }, [injectAssistantMessage])

  const handleMemoryClear = useCallback(() => {
    clearMemoryItems()
    injectAssistantMessage('Memory cleared. All saved facts have been removed.')
  }, [injectAssistantMessage])

  const handleSend = async (message: string, options?: { deepResearch?: boolean }) => {
    const memoryCmd = tryParseMemoryCommand(message)
    if (memoryCmd) {
      if (memoryCmd.kind === 'add') {
        handleMemoryAdd(memoryCmd.text)
      } else {
        handleMemoryClear()
      }
      return
    }

    const connectIntent = tryParseConnectIntent(message)
    if (connectIntent) {
      let sessionId = activeSessionId
      if (!sessionId) {
        try {
          const session = await createSession()
          setSessions((prev) => [session, ...prev])
          sessionId = session.id
          setActiveSessionId(sessionId)
        } catch (e) {
          console.error('Failed to create session for connect intent:', e)
          return
        }
      }

      const userContent = message.trim()
      const assistantContent = encodeConnectMessage(connectIntent)
      const now = new Date().toISOString()
      const userMsg: ChatMessage = {
        id: `temp-connect-u-${Date.now()}`,
        session_id: sessionId,
        role: 'user',
        content: userContent,
        created_at: now,
      }
      const assistantMsg: ChatMessage = {
        id: `temp-connect-a-${Date.now()}`,
        session_id: sessionId,
        role: 'assistant',
        content: assistantContent,
        created_at: now,
      }
      setMessages((prev) => [...prev, userMsg, assistantMsg])
      try {
        const saved = await persistMessages(sessionId, [
          { role: 'user', content: userContent },
          { role: 'assistant', content: assistantContent },
        ])
        if (saved.length) {
          setMessages((prev) => {
            const withoutTemps = prev.filter(
              (m) => m.id !== userMsg.id && m.id !== assistantMsg.id,
            )
            return [...withoutTemps, ...saved]
          })
        }
        void loadSessions()
      } catch (e) {
        console.error('Failed to persist connect messages:', e)
      }
      return
    }

    let sessionId = activeSessionId



    if (!sessionId) {

      try {

        const session = await createSession()

        setSessions((prev) => [session, ...prev])

        sessionId = session.id

        setActiveSessionId(sessionId)

      } catch (e) {

        console.error('Failed to create session:', e)

        return

      }

    }



    const userMsg: ChatMessage = {

      id: `temp-${Date.now()}`,

      session_id: sessionId,

      role: 'user',

      content: message,

      created_at: new Date().toISOString(),

    }

    setMessages((prev) => [...prev, userMsg])

    setIsStreaming(true)
    setTurnStatus('ok')
    lastFailedMessageRef.current = message

    resetStreamBuffer()

    setStreamingContent('')

    setRoutingMeta(null)

    setActiveModelDisplay(getComposerModelDisplay(settings.modelSelection))

    const deepResearch = options?.deepResearch ?? false

    setIsDeepResearch(deepResearch)
    setIsBuildMode(false)

    setResearchStatus(null)

    setResearchSources([])

    setWebSources([])

    setYoutubeVideos([])

    setDocCitations([])

    clearReasoningTimer()

    setActivityLog(

      deepResearch

        ? []

        : [makeActivityItem('Thinking', 'Understanding your request', 'thinking', 'active')],

    )

    abortRef.current = false
    abortControllerRef.current?.abort()
    const abortController = new AbortController()
    abortControllerRef.current = abortController

    if (!deepResearch) {

      reasoningTimerRef.current = setTimeout(() => {

        setActivityLog((prev) => {

          const active = prev.find((a) => a.state === 'active')

          if (!active || active.phase !== 'thinking') return prev

          return appendActivity(prev, {

            label: 'Reasoning',

            detail: 'Working through the problem',

            phase: 'reasoning',

          })

        })

      }, 1400)

    }



    if (deepResearch && typeof Notification !== 'undefined' && Notification.permission === 'default') {

      void Notification.requestPermission()

    }



    let accumulated = ''

    let clarificationPayload: ClarificationRequest | null = null



    await streamChat(

      sessionId,

      message,

      settingsWithMemory(settings),

      (token) => {

        if (abortRef.current) return

        accumulated += token

        streamBufferRef.current = accumulated

        scheduleStreamingFlush()

        clearReasoningTimer()

        if (accumulated.length > 0 && !writingTransitionedRef.current) {

          writingTransitionedRef.current = true

          setActivityLog((prev) => transitionToWriting(prev))

        }

      },

      (wasClarification) => {

        clearReasoningTimer()

        const aborted = abortRef.current || abortController.signal.aborted

        if (!aborted) {

          if (wasClarification && clarificationPayload) {

            const assistantMsg: ChatMessage = {

              id: `temp-${Date.now()}-assistant`,

              session_id: sessionId!,

              role: 'assistant',

              content: encodeClarificationMessage(clarificationPayload),

              created_at: new Date().toISOString(),

            }

            setMessages((prev) => [...prev, assistantMsg])

          } else if (!wasClarification && accumulated) {

            const assistantMsg: ChatMessage = {

              id: `temp-${Date.now()}-assistant`,

              session_id: sessionId!,

              role: 'assistant',

              content: accumulated,

              created_at: new Date().toISOString(),

            }

            setMessages((prev) => [...prev, assistantMsg])

            if (deepResearch) {

              notifyResearchComplete(message)

            }

          }

        }

        cancelStreamFlush()

        setStreamingContent('')

        resetStreamBuffer()

        setRoutingMeta(null)

        setActiveModelDisplay(null)

        setResearchStatus(null)

        setResearchSources([])

        setWebSources([])

        setDocCitations([])

        setActivityLog([])

        setIsDeepResearch(false)
        setIsBuildMode(false)

        setIsStreaming(false)

        loadSessions()

        // Don't reload after user abort — that would replace the stopped partial with a full backend reply
        if (!aborted) {
          loadMessages(sessionId!)
        }

      },

      (error) => {

        console.error('Stream error:', error)

        clearReasoningTimer()

        if (!abortRef.current && sessionId) {
          const friendly =
            error.includes('Invalid model') || error.includes('invalid_model')
              ? 'The selected model could not be reached. Try another model in the picker or restart the backend.'
              : error.includes('401') || error.toLowerCase().includes('unauthorized')
                ? 'Mistral API key is missing or invalid. Check backend/.env and restart the server.'
                : `Sorry, something went wrong: ${error}`

          const errorMsg: ChatMessage = {
            id: `temp-${Date.now()}-error`,
            session_id: sessionId,
            role: 'assistant',
            content: friendly,
            created_at: new Date().toISOString(),
          }
          setMessages((prev) => [...prev, errorMsg])
          setTurnStatus('failed')
          void persistMessages(sessionId, [{ role: 'assistant', content: friendly }])
            .then((saved) => {
              if (!saved.length) return
              setMessages((prev) => {
                const withoutTemp = prev.filter((m) => m.id !== errorMsg.id)
                return [...withoutTemp, ...saved]
              })
            })
            .catch((persistErr) => {
              console.error('Failed to persist stream error:', persistErr)
            })
        }

        cancelStreamFlush()

        setIsStreaming(false)

        setStreamingContent('')

        resetStreamBuffer()

        setRoutingMeta(null)

        setActiveModelDisplay(null)

        setResearchStatus(null)

        setResearchSources([])

        setWebSources([])

        setDocCitations([])

        setActivityLog([])

        setIsDeepResearch(false)
        setIsBuildMode(false)

      },

      (meta) => {

        setRoutingMeta(meta)

        if (meta.toLowerCase().includes('production build')) {
          setIsBuildMode(true)
        }

        if (!deepResearch) {

          clearReasoningTimer()

          const lower = meta.toLowerCase()

          if (lower.includes('web search') || lower.includes('web:')) {

            setActivityLog((prev) =>

              appendActivity(prev, {

                label: 'Searching the web',

                detail: meta.replace(/^Web search:\s*/i, '').trim(),

                phase: 'searching',

              }),

            )

          } else if (lower.includes('orchestrat') || lower.includes('specialist')) {

            setActivityLog((prev) =>

              appendActivity(prev, {

                label: 'Reasoning',

                detail: 'Coordinating specialist models',

                phase: 'reasoning',

              }),

            )

          } else if (lower.includes('rout')) {

            setActivityLog((prev) =>

              appendActivity(prev, {

                label: 'Reasoning',

                detail: meta,

                phase: 'reasoning',

              }),

            )

          }

        }

      },

      (name) => setActiveModelDisplay(name),

      deepResearch,

      (status) => {

        setResearchStatus(status)

        if (deepResearch) {

          setActivityLog((prev) => appendResearchActivity(prev, status))

          if (status.new_sources?.length) {

            setResearchSources((prev) => {

              const seen = new Set(prev.map((s) => s.url || s.title))

              const added = status.new_sources!.filter((s) => {

                const key = s.url || s.title

                if (!key || seen.has(key)) return false

                seen.add(key)

                return true

              })

              return [...prev, ...added]

            })

          }

        }

      },

      (status) => {

        if (!deepResearch) {

          clearReasoningTimer()

          setActivityLog((prev) => appendChatActivity(prev, status))

        }

      },

      (meta) => {

        if (deepResearch && meta.source_list?.length) {

          setResearchSources(meta.source_list)

        }

      },

      (active) => {

        if (active) setIsBuildMode(true)

      },

      (payload) => {

        if (payload.action === 'created' && payload.agent) {

          setEphemeralAgent(payload.agent)

        } else if (payload.action === 'dismissed') {

          setEphemeralAgent(null)

        }

      },

      (clarification) => {

        clarificationPayload = clarification

        setActivityLog([])

      },

      (sources) => {

        if (!abortRef.current) {

          setWebSources(sources)

        }

      },

      (citations) => {

        if (!abortRef.current) {

          setDocCitations(citations)

          if (citations.length > 0) {

            setActiveDocCitation(citations[0])

          }

        }

      },

      (videos) => {

        if (!abortRef.current) {

          setYoutubeVideos(videos)

        }

      },

      abortController.signal,

    )

  }



  const handleClarificationReply = (answer: string) => {

    void handleSend(answer)

  }



  const handleStop = () => {

    abortRef.current = true
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    setTurnStatus('stopped')

    clearReasoningTimer()

    cancelStreamFlush()

    const stoppedContent = streamBufferRef.current || streamingContent

    if (stoppedContent) {

      const assistantMsg: ChatMessage = {

        id: `temp-${Date.now()}-assistant`,

        session_id: activeSessionId!,

        role: 'assistant',

        content: stoppedContent,

        created_at: new Date().toISOString(),

      }

      setMessages((prev) => [...prev, assistantMsg])

    }

    setStreamingContent('')

    resetStreamBuffer()

    setIsStreaming(false)

    setResearchStatus(null)

    setResearchSources([])

    setWebSources([])

    setYoutubeVideos([])

    setDocCitations([])

    setActiveDocCitation(null)

    setActivityLog([])

    setIsDeepResearch(false)
    setIsBuildMode(false)

  }



  const handleDocCitationClick = (citation: DocumentCitation) => {

    setActiveDocCitation(citation)

  }



  const activeSession = sessions.find((s) => s.id === activeSessionId)



  const ensureSession = async (): Promise<string> => {

    if (activeSessionId) return activeSessionId

    const session = await createSession()

    setSessions((prev) => [session, ...prev])

    setActiveSessionId(session.id)

    return session.id

  }

  const handlePinSession = async (id: string, pinned: boolean) => {
    try {
      const { pinSession } = await import('../api')
      const updated = await pinSession(id, pinned)
      setSessions((prev) => {
        const next = prev.map((s) => (s.id === id ? { ...s, ...updated } : s))
        return next.sort((a, b) => Number(!!b.pinned) - Number(!!a.pinned))
      })
    } catch (e) {
      console.error('Failed to pin session:', e)
    }
  }

  const handleAssignProject = async (projectId: string | null) => {
    if (!activeSessionId) return
    try {
      const { updateSession } = await import('../api')
      const updated = await updateSession(
        activeSessionId,
        projectId ? { project_id: projectId } : { clear_project: true },
      )
      setSessions((prev) => prev.map((s) => (s.id === activeSessionId ? { ...s, ...updated } : s)))
    } catch (e) {
      console.error('Failed to assign project:', e)
    }
  }

  const handleRetry = async () => {
    const msg = lastFailedMessageRef.current
    if (!msg || isStreaming) return
    setTurnStatus('ok')
    await handleSend(msg)
  }

  return {

    sessions,

    activeSessionId,

    activeSession,

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

    setTurnStatus,

    lastFailedMessageRef,

    ensureSession,

    injectAssistantMessage,

    handleMemoryHelp,

    handleMemoryAdd,

    handleMemoryClear,

  }

}

