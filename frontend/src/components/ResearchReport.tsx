import { useMemo, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ResearchSource } from '../api'
import MermaidDiagram from './MermaidDiagram'
import CodeBlock from './CodeBlock'
import CitationChip from './CitationChip'
import { SourcesFooter } from './CitationMarkdown'
import { stripMarkdownSourcesSection } from '../utils/sources'
import { extractContentParts, normalizeDiagramSource } from '../utils/mermaidUtils'

interface Props {
  content: string
  sources?: ResearchSource[]
  isStreaming?: boolean
}

function CitationText({ text, sources }: { text: string; sources: ResearchSource[] }) {
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
          const source = sources.find((s) => s.id === part.num) ?? sources[part.num - 1]
          return <CitationChip key={i} num={part.num} source={source} />
        }
        return <span key={i}>{part.value}</span>
      })}
    </>
  )
}

function renderChildrenWithCitations(
  children: ReactNode,
  sources: ResearchSource[],
): ReactNode {
  if (typeof children === 'string') {
    return <CitationText text={children} sources={sources} />
  }
  if (Array.isArray(children)) {
    return children.map((child, i) =>
      typeof child === 'string' ? (
        <CitationText key={i} text={child} sources={sources} />
      ) : (
        child
      ),
    )
  }
  return children
}

function MarkdownWithCitations({ text, sources }: { text: string; sources: ResearchSource[] }) {
  const cite = (children: ReactNode) => renderChildrenWithCitations(children, sources)
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p({ children }) {
          return <p>{cite(children)}</p>
        },
        li({ children }) {
          return <li>{cite(children)}</li>
        },
        h1({ children }) {
          return <h1>{cite(children)}</h1>
        },
        h2({ children }) {
          return <h2>{cite(children)}</h2>
        },
        h3({ children }) {
          return <h3>{cite(children)}</h3>
        },
        h4({ children }) {
          return <h4>{cite(children)}</h4>
        },
        blockquote({ children }) {
          return <blockquote>{cite(children)}</blockquote>
        },
        td({ children }) {
          return <td>{cite(children)}</td>
        },
        th({ children }) {
          return <th>{cite(children)}</th>
        },
        strong({ children }) {
          return <strong>{cite(children)}</strong>
        },
        em({ children }) {
          return <em>{cite(children)}</em>
        },
        code({ className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '')
          const lang = match?.[1]
          const codeStr = String(children).replace(/\n$/, '')
          if (lang === 'mermaid' || lang === 'flowchart' || lang === 'graph') {
            return <MermaidDiagram chart={normalizeDiagramSource(codeStr, lang)} />
          }
          if (!match) return <code className="inline-code" {...props}>{children}</code>
          return <CodeBlock code={codeStr} language={lang} className={className} />
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

export default function ResearchReport({ content, sources = [], isStreaming }: Props) {
  const renderContent = useMemo(
    () => (sources.length > 0 ? stripMarkdownSourcesSection(content) : content),
    [content, sources.length],
  )
  const parts = useMemo(
    () => extractContentParts(renderContent, isStreaming),
    [renderContent, isStreaming],
  )

  return (
    <div className="research-report">
      <div className="prose-chat prose-research">
        {parts.map((part, i) => {
          if (part.type === 'mermaid') {
            return <MermaidDiagram key={i} chart={part.value} />
          }
          if (part.type === 'mermaid-pending') {
            return (
              <div key={i} className="diagram-pending">
                <div className="diagram-spinner" />
                <span>Rendering SVG diagram…</span>
              </div>
            )
          }
          if (isStreaming) {
            return <StreamingPlainText key={i} text={part.value} />
          }
          return <MarkdownWithCitations key={i} text={part.value} sources={sources} />
        })}
        {isStreaming && <span className="streaming-cursor" />}
      </div>
      {sources.length > 0 && !isStreaming ? <SourcesFooter sources={sources} /> : null}
    </div>
  )
}
