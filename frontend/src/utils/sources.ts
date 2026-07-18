import type { WebSearchSource } from '../api'

const MARKER = '<!--nexus-sources:'
const MARKER_END = '-->'

export function parseWebSources(content: string): WebSearchSource[] {
  const start = content.indexOf(MARKER)
  if (start < 0) return []
  const jsonStart = start + MARKER.length
  const end = content.indexOf(MARKER_END, jsonStart)
  if (end < 0) return []
  try {
    const data = JSON.parse(content.slice(jsonStart, end)) as WebSearchSource[]
    if (!Array.isArray(data)) return []
    return data.filter((s) => s && (s.title || s.url))
  } catch {
    return []
  }
}

export function stripWebSourcesMarker(content: string): string {
  const start = content.indexOf(MARKER)
  if (start < 0) return content.trim()
  return content.slice(0, start).trim()
}

export function hasMarkdownSourcesSection(content: string): boolean {
  return /(?:^|\n)#{1,3}\s*Sources\b/i.test(content)
}

export function stripMarkdownSourcesSection(content: string): string {
  const match = content.match(/(?:^|\n)(#{1,3}\s*Sources\b[\s\S]*)$/i)
  if (!match || match.index === undefined) return content
  return content.slice(0, match.index).trim()
}
