export interface ClarificationRequest {
  question: string
  options: string[]
  allowCustom: boolean
}

const MARKER = '<!--nexus-clarify:'
const MARKER_END = '-->'

export function parseClarification(content: string): ClarificationRequest | null {
  const start = content.indexOf(MARKER)
  if (start < 0) return null
  const jsonStart = start + MARKER.length
  const end = content.indexOf(MARKER_END, jsonStart)
  if (end < 0) return null
  try {
    const data = JSON.parse(content.slice(jsonStart, end)) as ClarificationRequest
    if (!data.question || !Array.isArray(data.options) || data.options.length < 2) return null
    return {
      question: data.question,
      options: data.options.map(String),
      allowCustom: data.allowCustom !== false,
    }
  } catch {
    return null
  }
}

export function stripClarificationMarker(content: string): string {
  const start = content.indexOf(MARKER)
  if (start < 0) return content.trim()
  return content.slice(0, start).trim()
}

export function isClarificationMessage(content: string): boolean {
  return content.includes(MARKER)
}

export function encodeClarificationMessage(data: ClarificationRequest): string {
  const body = {
    question: data.question,
    options: data.options,
    allowCustom: data.allowCustom,
  }
  return `${data.question}\n${MARKER}${JSON.stringify(body)}${MARKER_END}`
}
