import type { DocumentCitation } from '../api'

export function parseDocCitations(raw: string | undefined | null): DocumentCitation[] {
  if (!raw?.trim()) return []
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? (parsed as DocumentCitation[]) : []
  } catch {
    return []
  }
}

export function stripPageMarkers(text: string): string {
  return text.replace(/\[Page \d+\]\s*/g, '').trim()
}

export function highlightSnippet(content: string, snippet: string): { before: string; match: string; after: string } {
  const clean = stripPageMarkers(content)
  const needle = snippet.trim().slice(0, 120)
  if (!needle) return { before: clean, match: '', after: '' }

  const lowerContent = clean.toLowerCase()
  const lowerNeedle = needle.toLowerCase()
  const idx = lowerContent.indexOf(lowerNeedle)

  if (idx === -1) {
    const words = needle.split(/\s+/).filter(Boolean)
    for (let len = Math.min(words.length, 8); len >= 3; len--) {
      const partial = words.slice(0, len).join(' ')
      const partialIdx = lowerContent.indexOf(partial.toLowerCase())
      if (partialIdx !== -1) {
        return {
          before: clean.slice(0, partialIdx),
          match: clean.slice(partialIdx, partialIdx + partial.length),
          after: clean.slice(partialIdx + partial.length),
        }
      }
    }
    return { before: clean, match: '', after: '' }
  }

  return {
    before: clean.slice(0, idx),
    match: clean.slice(idx, idx + needle.length),
    after: clean.slice(idx + needle.length),
  }
}
