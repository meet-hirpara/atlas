import { useMemo, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { WebSearchSource } from '../api'
import CitationChip from './CitationChip'
import MermaidDiagram from './MermaidDiagram'
import CodeBlock from './CodeBlock'
import { parseCodeClassName } from '../utils/projectFiles'
import { normalizeDiagramSource } from '../utils/mermaidUtils'

function CitationText({ text, sources }: { text: string; sources: WebSearchSource[] }) {
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

function withCitations(children: ReactNode, sources: WebSearchSource[]) {
  if (Array.isArray(children)) {
    return children.map((child, i) =>
      typeof child === 'string' ? (
        <CitationText key={i} text={child} sources={sources} />
      ) : (
        child
      ),
    )
  }
  if (typeof children === 'string') {
    return <CitationText text={children} sources={sources} />
  }
  return children
}

export function SourcesFooter({ sources }: { sources: WebSearchSource[] }) {
  if (sources.length === 0) return null
  return (
    <footer className="web-sources-footer">
      <h3 className="web-sources-footer-title">Sources</h3>
      <ol className="web-sources-footer-list">
        {sources.map((source, i) => (
          <li key={source.url || source.title || i}>
            <span className="web-sources-footer-num">{source.id ?? i + 1}</span>
            {source.url ? (
              <a href={source.url} target="_blank" rel="noopener noreferrer">
                {source.title || source.url}
              </a>
            ) : (
              <span>{source.title}</span>
            )}
            {source.domain ? (
              <span className="web-sources-footer-domain">{source.domain}</span>
            ) : null}
          </li>
        ))}
      </ol>
    </footer>
  )
}

interface Props {
  text: string
  sources: WebSearchSource[]
}

export default function CitationMarkdown({ text, sources }: Props) {
  const hasCitations = sources.length > 0

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p({ children }) {
          return <p>{hasCitations ? withCitations(children, sources) : children}</p>
        },
        li({ children }) {
          return <li>{hasCitations ? withCitations(children, sources) : children}</li>
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
