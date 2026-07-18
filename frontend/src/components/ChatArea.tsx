import { useRef, useEffect, useState, useCallback } from 'react'
import { ChevronDown } from 'lucide-react'

import MessageBubble from './MessageBubble'

import ActivityStatus from './ActivityStatus'

import DeepResearchPanel from './DeepResearchPanel'

import ResearchReport from './ResearchReport'

import type { ChatMessage, ActivityItem, ResearchSource, ResearchStatus, WebSearchSource, DocumentCitation, EphemeralAgent, YouTubeVideo } from '../api'

import { parseWebSources } from '../utils/sources'
import { parseDocCitations } from '../utils/docCitations'
import { parseYoutubeVideos } from '../utils/youtube'

import { parseClarification } from '../utils/clarification'
import type { ConnectIntent } from '../utils/connectIntent'
import { APP_DISPLAY_NAME, APP_NAME } from '../brand'
import { getWelcomeSuggestions } from '../utils/welcomeSuggestions'
import LampLogo from './LampLogo'



interface Props {

  messages: ChatMessage[]

  streamingContent: string

  routingMeta?: string | null

  activityLog?: ActivityItem[]

  researchStatus?: ResearchStatus | null

  researchSources?: ResearchSource[]

  webSources?: WebSearchSource[]

  youtubeVideos?: YouTubeVideo[]

  docCitations?: DocumentCitation[]

  activeDocCitationId?: number | null

  onDocCitationClick?: (citation: DocumentCitation) => void

  isDeepResearch?: boolean

  isBuildMode?: boolean

  ephemeralAgent?: EphemeralAgent | null

  onDismissAgent?: () => void

  isStreaming: boolean

  onSuggestionClick?: (text: string) => void

  onClarificationReply?: (answer: string) => void

  onConnectMcp?: (intent: ConnectIntent) => void

  onQuickReply?: (message: string) => void

  onRetry?: () => void

  onExportMd?: () => void

  onSaveProposal?: (content: string) => void

  turnStatus?: 'ok' | 'stopped' | 'failed'

}



const NEAR_BOTTOM_THRESHOLD = 80

function isNearBottom(el: HTMLElement) {
  return el.scrollHeight - el.scrollTop - el.clientHeight <= NEAR_BOTTOM_THRESHOLD
}

export default function ChatArea({

  messages,

  streamingContent,

  routingMeta,

  activityLog = [],

  researchStatus = null,

  researchSources = [],

  webSources = [],

  youtubeVideos = [],

  docCitations = [],

  activeDocCitationId = null,

  onDocCitationClick,

  isDeepResearch,

  isBuildMode,

  ephemeralAgent,

  onDismissAgent,

  isStreaming,

  onSuggestionClick,

  onClarificationReply,

  onConnectMcp,

  onQuickReply,

  onRetry,

  onExportMd,

  onSaveProposal,

  turnStatus = 'ok',

}: Props) {

  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const userPinnedRef = useRef(false)
  const prevMessagesLenRef = useRef(messages.length)
  const scrollRafRef = useRef<number | null>(null)
  const [showScrollButton, setShowScrollButton] = useState(false)
  const [welcomeSuggestions, setWelcomeSuggestions] = useState<string[]>(() => getWelcomeSuggestions())
  const wasEmptyRef = useRef(true)
  const isEmpty = messages.length === 0 && !isStreaming

  useEffect(() => {
    if (isEmpty) {
      if (!wasEmptyRef.current) {
        setWelcomeSuggestions(getWelcomeSuggestions())
      }
    }
    wasEmptyRef.current = isEmpty
  }, [isEmpty])

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    bottomRef.current?.scrollIntoView({ behavior })
  }, [])

  const scrollToBottomInstant = useCallback(() => {
    const el = scrollContainerRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
      return
    }
    bottomRef.current?.scrollIntoView({ behavior: 'auto' })
  }, [])

  const scheduleStreamScroll = useCallback(() => {
    if (scrollRafRef.current !== null) return
    scrollRafRef.current = requestAnimationFrame(() => {
      scrollRafRef.current = null
      if (userPinnedRef.current) return
      const el = scrollContainerRef.current
      if (el && !isNearBottom(el)) return
      scrollToBottomInstant()
    })
  }, [scrollToBottomInstant])

  useEffect(() => {
    const el = scrollContainerRef.current
    if (!el) return

    const onScroll = () => {
      const near = isNearBottom(el)
      if (near) {
        userPinnedRef.current = false
        setShowScrollButton(false)
      } else if (isStreaming) {
        userPinnedRef.current = true
        setShowScrollButton(true)
      }
    }

    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [isStreaming])

  useEffect(() => () => {
    if (scrollRafRef.current !== null) {
      cancelAnimationFrame(scrollRafRef.current)
    }
  }, [])

  useEffect(() => {
    const isNewUserMessage =
      messages.length > prevMessagesLenRef.current &&
      messages[messages.length - 1]?.role === 'user'
    prevMessagesLenRef.current = messages.length

    if (isNewUserMessage) {
      userPinnedRef.current = false
      setShowScrollButton(false)
      scrollToBottom('smooth')
      return
    }

    if (userPinnedRef.current) return

    const el = scrollContainerRef.current
    if (el && !isNearBottom(el)) return

    scrollToBottom('smooth')
  }, [messages, isStreaming, activityLog, researchStatus, researchSources, webSources, youtubeVideos, docCitations, scrollToBottom])

  useEffect(() => {
    if (!isStreaming || !streamingContent || userPinnedRef.current) return
    scheduleStreamScroll()
  }, [streamingContent, isStreaming, scheduleStreamScroll])

  const handleScrollToBottom = () => {
    userPinnedRef.current = false
    setShowScrollButton(false)
    scrollToBottom('smooth')
  }



  const showDeepResearch = isDeepResearch && isStreaming

  const showActivity = isStreaming && activityLog.length > 0 && !showDeepResearch

  const showFallbackActivity =
    isStreaming && !showDeepResearch && activityLog.length === 0 && !streamingContent

  const reportStarted = Boolean(streamingContent && streamingContent.length > 40)

  const showAssistantTurn = isStreaming && (showDeepResearch || showActivity || showFallbackActivity || streamingContent || routingMeta)

  const liveTurnPhase = streamingContent ? 'chat-turn-live-streaming' : 'chat-turn-live-working'



  return (

    <div className="chat-scroll-wrap">
    <div className="chat-scroll" ref={scrollContainerRef}>

      {isEmpty ? (

        <div className="welcome-screen">

          <div className="welcome-mark">
            <LampLogo size={40} label={APP_DISPLAY_NAME} />
          </div>

          <h1 className="welcome-title">{APP_NAME}</h1>

          <p className="welcome-subtitle">
            Type a message below to get started — or pick a suggestion.
          </p>

          <p className="welcome-primary-hint" aria-hidden="true">
            ↓ Message box
          </p>

          <div className="welcome-chips">

            {welcomeSuggestions.map((text, index) => (

              <button

                key={`${index}-${text}`}

                type="button"

                onClick={() => onSuggestionClick?.(text)}

                className="welcome-chip"

              >

                {text}

              </button>

            ))}

          </div>

        </div>

      ) : (

        <div className="chat-thread">

          {ephemeralAgent && (
            <div className="ephemeral-agent-chip" role="status">
              <span className="ephemeral-agent-chip-label">
                Active agent: <strong>{ephemeralAgent.name}</strong>
              </span>
              {onDismissAgent && (
                <button
                  type="button"
                  className="ephemeral-agent-dismiss"
                  onClick={onDismissAgent}
                  aria-label={`Dismiss ${ephemeralAgent.name} agent`}
                >
                  Dismiss
                </button>
              )}
            </div>
          )}

          {messages.map((msg, i) => {

            const clarification =
              msg.role === 'assistant' ? parseClarification(msg.content) : null

            const clarificationAnswer =
              clarification && messages[i + 1]?.role === 'user'
                ? messages[i + 1].content
                : undefined

            const needsReply = Boolean(clarification && !clarificationAnswer)

            const sources = msg.role === 'assistant' ? parseWebSources(msg.content) : []
            const messageYoutube =
              msg.role === 'assistant' ? parseYoutubeVideos(msg.content) : []
            const messageDocCitations =
              msg.role === 'assistant' ? parseDocCitations(msg.sources) : []

            return (

              <MessageBubble
                key={msg.id}
                role={msg.role}
                content={msg.content}
                sources={sources}
                youtubeVideos={messageYoutube}
                docCitations={messageDocCitations}
                activeDocCitationId={activeDocCitationId}
                onDocCitationClick={onDocCitationClick}
                clarificationAnswer={clarificationAnswer}
                onClarificationSubmit={needsReply ? onClarificationReply : undefined}
                onConnectMcp={msg.role === 'assistant' ? onConnectMcp : undefined}
                onQuickReply={msg.role === 'assistant' ? onQuickReply : undefined}
                onRetry={msg.role === 'assistant' && i === messages.length - 1 ? onRetry : undefined}
                onExportMd={msg.role === 'assistant' && i === messages.length - 1 ? onExportMd : undefined}
                onSaveProposal={
                  msg.role === 'assistant' && onSaveProposal
                    ? () => onSaveProposal(msg.content)
                    : undefined
                }
                turnStatus={
                  msg.role === 'assistant' && i === messages.length - 1 ? turnStatus : 'ok'
                }
              />

            )

          })}

          {showAssistantTurn && (

            <div className={`chat-turn chat-turn-assistant chat-turn-live ${liveTurnPhase}`}>

              {isBuildMode && (
                <div className="build-mode-badge" role="status">
                  Production build mode
                </div>
              )}

              {showDeepResearch && (

                <DeepResearchPanel

                  status={researchStatus}

                  steps={activityLog}

                  sources={researchSources}

                  reportStarted={reportStarted}

                  collapsed={reportStarted}

                />

              )}

              {(showActivity || showFallbackActivity) && (

                <ActivityStatus

                  items={
                    showFallbackActivity
                      ? [{ id: 'working', label: 'Thinking', detail: '', phase: 'thinking', state: 'active' }]
                      : activityLog
                  }

                  compact

                  fading={Boolean(streamingContent && streamingContent.length > 80)}

                />

              )}

              {streamingContent ? (

                isDeepResearch ? (

                  <ResearchReport

                    content={streamingContent}

                    sources={researchSources}

                    isStreaming

                  />

                ) : (

                  <MessageBubble

                    role="assistant"

                    content={streamingContent}

                    sources={webSources}

                    youtubeVideos={youtubeVideos}

                    docCitations={docCitations}

                    activeDocCitationId={activeDocCitationId}

                    onDocCitationClick={onDocCitationClick}

                    isStreaming

                    bare

                  />

                )

              ) : null}

            </div>

          )}

          <div ref={bottomRef} className="scroll-anchor" />

        </div>

      )}

    </div>
    {showScrollButton && (
      <button
        type="button"
        className="scroll-to-bottom-btn"
        onClick={handleScrollToBottom}
        aria-label="Scroll to bottom"
      >
        <ChevronDown size={18} />
      </button>
    )}
    </div>

  )

}


