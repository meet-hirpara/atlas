import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { WebSearchSource, DocumentCitation } from '../api'
import MermaidDiagram from './MermaidDiagram'
import CodeBlock from './CodeBlock'
import CitationMarkdown, { SourcesFooter } from './CitationMarkdown'
import DocumentCitationMarkdown, { DocumentSourcesFooter } from './DocumentCitationMarkdown'
import MessageActions from './MessageActions'
import ProjectFilesPanel from './ProjectFilesPanel'
import { extractContentParts, normalizeDiagramSource } from '../utils/mermaidUtils'
import { extractProjectFiles, isMultiFileProject, parseCodeClassName, stripProjectFences } from '../utils/projectFiles'
import { parseWebSources, stripWebSourcesMarker, stripMarkdownSourcesSection } from '../utils/sources'
import ClarificationCard from './ClarificationCard'
import ConnectCard from './ConnectCard'
import YouTubeRecommendations from './YouTubeRecommendations'
import { parseClarification, stripClarificationMarker } from '../utils/clarification'
import { parseConnectPrompt, stripConnectMarker } from '../utils/connectIntent'
import type { ConnectIntent } from '../utils/connectIntent'
import { parseYoutubeVideos, stripYoutubeMarker } from '../utils/youtube'
import { stripModelMarker } from '../utils/modelLabel'
import type { YouTubeVideo } from '../api'
import QuickReplyChips from './QuickReplyChips'
import { shouldShowQuickReplies } from '../utils/quickReplies'

interface Props {
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  bare?: boolean
  sources?: WebSearchSource[]
  docCitations?: DocumentCitation[]
  activeDocCitationId?: number | null
  onDocCitationClick?: (citation: DocumentCitation) => void
  clarificationAnswer?: string
  onClarificationSubmit?: (answer: string) => void
  onConnectMcp?: (intent: ConnectIntent) => void
  youtubeVideos?: YouTubeVideo[]
  onQuickReply?: (message: string) => void
  onRetry?: () => void
  onExportMd?: () => void
  onSaveProposal?: () => void
  turnStatus?: 'ok' | 'stopped' | 'failed'
}

function MarkdownContent({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ className, children, ...props }) {
          const { language: lang, path } = parseCodeClassName(className)
          const codeStr = String(children).replace(/\n$/, '')

          if (lang === 'mermaid' || lang === 'flowchart' || lang === 'graph') {
            return <MermaidDiagram chart={normalizeDiagramSource(codeStr, lang)} />
          }

          if (!lang && !className?.includes('language-')) {
            return <code className="inline-code" {...props}>{children}</code>
          }

          return (
            <CodeBlock
              code={codeStr}
              language={lang}
              filePath={path}
              className={className}
            />
          )
        },
        pre({ children }) {
          return <>{children}</>
        },
      }}
    >
      {text}
    </ReactMarkdown>
  )
}

function StreamingPlainText({ text }: { text: string }) {
  return <div className="streaming-plain-text">{text}</div>
}

export default function MessageBubble({
  role,
  content,
  isStreaming,
  bare,
  sources: sourcesProp,
  docCitations: docCitationsProp,
  activeDocCitationId,
  onDocCitationClick,
  clarificationAnswer,
  onClarificationSubmit,
  onConnectMcp,
  youtubeVideos: youtubeVideosProp,
  onQuickReply,
  onRetry,
  onExportMd,
  onSaveProposal,
  turnStatus = 'ok',
}: Props) {
  const clarification = useMemo(
    () => (role === 'assistant' && !isStreaming ? parseClarification(content) : null),
    [role, content, isStreaming],
  )
  const connectPrompt = useMemo(
    () => (role === 'assistant' && !isStreaming ? parseConnectPrompt(content) : null),
    [role, content, isStreaming],
  )
  const embeddedYoutube = useMemo(
    () => (role === 'assistant' && !isStreaming ? parseYoutubeVideos(content) : []),
    [role, content, isStreaming],
  )
  const embeddedSources = useMemo(
    () => (isStreaming ? [] : parseWebSources(content)),
    [content, isStreaming],
  )
  const displayContent = useMemo(() => {
    let text = stripWebSourcesMarker(content)
    text = stripYoutubeMarker(text)
    text = stripModelMarker(text)
    if (clarification) text = stripClarificationMarker(text)
    if (connectPrompt) text = stripConnectMarker(text)
    return text
  }, [content, clarification, connectPrompt])
  const sources = sourcesProp?.length ? sourcesProp : embeddedSources
  const renderContent = useMemo(() => {
    if (sources.length > 0) return stripMarkdownSourcesSection(displayContent)
    return displayContent
  }, [displayContent, sources.length])
  const youtubeVideos = youtubeVideosProp?.length ? youtubeVideosProp : embeddedYoutube
  const docCitations = docCitationsProp ?? []
  const hasWebSources = sources.length > 0
  const hasDocCitations = docCitations.length > 0

  const parts = useMemo(
    () => extractContentParts(renderContent, isStreaming),
    [renderContent, isStreaming],
  )

  const projectFiles = useMemo(
    () => (isStreaming ? [] : extractProjectFiles(renderContent)),
    [renderContent, isStreaming],
  )
  const showProjectPanel = !isStreaming && isMultiFileProject(renderContent)

  const showCopy = !isStreaming && displayContent.trim().length > 0 && !connectPrompt

  const renderTextPart = (partText: string, key: number) => {
    if (isStreaming) {
      return <StreamingPlainText key={key} text={partText} />
    }
    if (hasDocCitations) {
      return (
        <DocumentCitationMarkdown
          key={key}
          text={partText}
          citations={docCitations}
          activeCitationId={activeDocCitationId}
          onCitationClick={onDocCitationClick}
        />
      )
    }
    if (hasWebSources) {
      return <CitationMarkdown key={key} text={partText} sources={sources} />
    }
    return <MarkdownContent key={key} text={partText} />
  }

  const prose = (
    <div className={`prose-chat${isStreaming ? ' prose-chat-streaming' : ''}`}>
      {showProjectPanel ? <ProjectFilesPanel files={projectFiles} /> : null}
      {parts.map((part, i) => {
        if (part.type === 'mermaid') {
          return <MermaidDiagram key={i} chart={part.value} />
        }
        if (part.type === 'mermaid-pending') {
          return (
            <div key={i} className="diagram-pending">
              <div className="diagram-spinner" />
              <span>Rendering diagram…</span>
            </div>
          )
        }
        const partText = showProjectPanel ? stripProjectFences(part.value) : part.value
        return renderTextPart(partText, i)
      })}
      {isStreaming && <span className="streaming-cursor" />}
      {!isStreaming && hasDocCitations ? (
        <DocumentSourcesFooter
          citations={docCitations}
          activeCitationId={activeDocCitationId}
          onCitationClick={onDocCitationClick}
        />
      ) : null}
      {!isStreaming && hasWebSources ? <SourcesFooter sources={sources} /> : null}
      {youtubeVideos.length > 0 ? <YouTubeRecommendations videos={youtubeVideos} /> : null}
    </div>
  )

  if (role === 'user') {
    return (
      <div className="chat-turn chat-turn-user">
        <p className="user-text">{displayContent}</p>
        {showCopy && <MessageActions content={displayContent} />}
      </div>
    )
  }

  const body = (
    <>
      {clarification ? (
        <ClarificationCard
          data={clarification}
          onSubmit={onClarificationSubmit ?? (() => {})}
          disabled={!onClarificationSubmit}
          answered={clarificationAnswer}
        />
      ) : connectPrompt ? (
        <ConnectCard
          data={connectPrompt}
          onConnect={onConnectMcp ?? (() => {})}
        />
      ) : (
        prose
      )}
      {showCopy && (
        <MessageActions
          content={displayContent}
          onRetry={role === 'assistant' ? onRetry : undefined}
          onExportMd={role === 'assistant' ? onExportMd : undefined}
          onSaveProposal={role === 'assistant' ? onSaveProposal : undefined}
          status={role === 'assistant' ? turnStatus : 'ok'}
        />
      )}
      {!isStreaming && !clarification && !connectPrompt && content.trim() && onQuickReply && shouldShowQuickReplies(content) ? (
        <QuickReplyChips
          assistantContent={displayContent}
          onSelect={onQuickReply}
        />
      ) : null}
    </>
  )

  if (bare) {
    return body
  }

  return (
    <div className="chat-turn chat-turn-assistant">
      {body}
    </div>
  )
}
