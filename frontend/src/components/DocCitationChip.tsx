import type { DocumentCitation } from '../api'

interface Props {
  num: number
  citation?: DocumentCitation
  active?: boolean
  onClick?: (citation: DocumentCitation) => void
}

export default function DocCitationChip({ num, citation, active, onClick }: Props) {
  if (!citation) {
    return (
      <sup className="citation-chip citation-chip-plain doc-citation-chip" aria-label={`Document source ${num}`}>
        {num}
      </sup>
    )
  }

  const pageLabel =
    citation.page_end && citation.page_end !== citation.page
      ? `pp. ${citation.page}–${citation.page_end}`
      : `p. ${citation.page}`

  return (
    <button
      type="button"
      className={`citation-chip doc-citation-chip${active ? ' doc-citation-chip-active' : ''}`}
      aria-label={`Source ${num}: ${citation.filename}, ${pageLabel}`}
      onClick={() => onClick?.(citation)}
    >
      <span className="citation-chip-num">{num}</span>
      <span className="citation-popover" role="tooltip">
        <span className="citation-popover-title">{citation.filename}</span>
        <span className="citation-popover-url">{pageLabel}</span>
        {citation.snippet ? (
          <span className="citation-popover-snippet">{citation.snippet}</span>
        ) : null}
      </span>
    </button>
  )
}
