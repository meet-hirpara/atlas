export const DEFAULT_MODEL_DISPLAY = 'Fable 5'

const MARKER = '<!--nexus-model:'
const MARKER_END = '-->'

export function parseModelLabel(content: string): string | null {
  const start = content.indexOf(MARKER)
  if (start < 0) return null
  const jsonStart = start + MARKER.length
  const end = content.indexOf(MARKER_END, jsonStart)
  if (end < 0) return null
  try {
    const name = JSON.parse(content.slice(jsonStart, end)) as string
    return typeof name === 'string' && name.trim() ? name.trim() : null
  } catch {
    return null
  }
}

export function stripModelMarker(content: string): string {
  const start = content.indexOf(MARKER)
  if (start < 0) return content.trim()
  return content.slice(0, start).trim()
}
