import type { WebSearchSource } from '../api'

interface Props {
  num: number
  source?: WebSearchSource
}

export default function CitationChip({ num, source }: Props) {
  if (!source) {
    return (
      <sup className="citation-chip citation-chip-plain" aria-label={`Source ${num}`}>
        {num}
      </sup>
    )
  }

  const label = source.title || source.url || `Source ${num}`
  const body = (
    <>
      <span className="citation-chip-num">{num}</span>
      <span className="citation-popover" role="tooltip">
        <span className="citation-popover-title">{label}</span>
        {source.url ? (
          <span className="citation-popover-url">{source.domain || source.url}</span>
        ) : null}
        {source.snippet ? (
          <span className="citation-popover-snippet">{source.snippet}</span>
        ) : null}
      </span>
    </>
  )

  if (source.url) {
    return (
      <a
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        className="citation-chip"
        aria-label={`Source ${num}: ${label}`}
      >
        {body}
      </a>
    )
  }

  return (
    <span className="citation-chip citation-chip-static" aria-label={`Source ${num}: ${label}`}>
      {body}
    </span>
  )
}
