import { useMemo, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { DocumentCitation } from '../api'
import DocCitationChip from './DocCitationChip'
import MermaidDiagram from './MermaidDiagram'
import CodeBlock from './CodeBlock'
import { parseCodeClassName } from '../utils/projectFiles'
import { normalizeDiagramSource } from '../utils/mermaidUtils'

function CitationText({
  text,
  citations,
  activeCitationId,
  onCitationClick,
}: {
  text: string
  citations: DocumentCitation[]
  activeCitationId?: number | null
  onCitationClick?: (citation: DocumentCitation) => void
}) {
  const parts = useMemo(() => {
    const segments: Array<{ type: 'text' | 'cite'; value: string; num?: number }> = []
    const re = /\[(\d{1,2})\]/g
    let last = 0
    let match: RegExpExecArray | null
    while ((match = re.exec(text)) !== null) {
      if (match.index > last) {
        segments.push({ type: 'text', value: text.slice(last, match.index) })
      }
      segments.push({ type: 'cite', value: match[0], num: parseInt(match[1], 10) })
      last = match.index + match[0].length
    }
    if (last < text.length) {
      segments.push({ type: 'text', value: text.slice(last) })
    }
    return segments
  }, [text])

  return (
    <>
      {parts.map((part, i) => {
        if (part.type === 'cite' && part.num) {
          const citation = citations.find((c) => c.id === part.num) ?? citations[part.num - 1]
          return (
            <DocCitationChip
              key={i}
              num={part.num}
              citation={citation}
              active={citation?.id === activeCitationId}
              onClick={onCitationClick}
            />
          )
        }
        return <span key={i}>{part.value}</span>
      })}
    </>
  )
}

function withCitations(
  children: ReactNode,
  citations: DocumentCitation[],
  activeCitationId: number | null | undefined,
  onCitationClick?: (citation: DocumentCitation) => void,
) {
  if (Array.isArray(children)) {
    return children.map((child, i) =>
      typeof child === 'string' ? (
        <CitationText
          key={i}
          text={child}
          citations={citations}
          activeCitationId={activeCitationId}
          onCitationClick={onCitationClick}
        />
      ) : (
        child
      ),
    )
  }
  if (typeof children === 'string') {
    return (
      <CitationText
        text={children}
        citations={citations}
        activeCitationId={activeCitationId}
        onCitationClick={onCitationClick}
      />
    )
  }
  return children
}

export function DocumentSourcesFooter({
  citations,
  activeCitationId,
  onCitationClick,
}: {
  citations: DocumentCitation[]
  activeCitationId?: number | null
  onCitationClick?: (citation: DocumentCitation) => void
}) {
  if (citations.length === 0) return null
  return (
    <footer className="doc-sources-footer">
      <h3 className="doc-sources-footer-title">Document sources</h3>
      <ol className="doc-sources-footer-list">
        {citations.map((citation) => {
          const pageLabel =
            citation.page_end && citation.page_end !== citation.page
              ? `pp. ${citation.page}–${citation.page_end}`
              : `p. ${citation.page}`
          return (
            <li key={citation.id}>
              <button
                type="button"
                className={`doc-sources-footer-item${activeCitationId === citation.id ? ' active' : ''}`}
                onClick={() => onCitationClick?.(citation)}
              >
                <span className="doc-sources-footer-num">{citation.id}</span>
                <span className="doc-sources-footer-text">
                  <span className="doc-sources-footer-name">{citation.filename}</span>
                  <span className="doc-sources-footer-page">{pageLabel}</span>
                  {citation.snippet ? (
                    <span className="doc-sources-footer-snippet">{citation.snippet}</span>
                  ) : null}
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </footer>
  )
}

interface Props {
  text: string
  citations: DocumentCitation[]
  activeCitationId?: number | null
  onCitationClick?: (citation: DocumentCitation) => void
}

export default function DocumentCitationMarkdown({
  text,
  citations,
  activeCitationId,
  onCitationClick,
}: Props) {
  const hasCitations = citations.length > 0

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p({ children }) {
          return (
            <p>
              {hasCitations
                ? withCitations(children, citations, activeCitationId, onCitationClick)
                : children}
            </p>
          )
        },
        li({ children }) {
          return (
            <li>
              {hasCitations
                ? withCitations(children, citations, activeCitationId, onCitationClick)
                : children}
            </li>
          )
        },
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
