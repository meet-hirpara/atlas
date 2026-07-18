const EDGE_OPS = /-->|---->|---|-.->|==>|--o|o--|x--|--x/
const SIMPLE_ID = /^[a-zA-Z][a-zA-Z0-9_]*$/

function escapeMermaidText(text: string): string {
  return text.replace(/"/g, '#quot;')
}

/** Escape characters that break Mermaid inside node label text */
function escapeLabelContent(label: string): string {
  return label
    .replace(/"/g, '#quot;')
    .replace(/\|/g, '#124;')
    .replace(/⟩/g, '>')
    .replace(/⟨/g, '<')
    .replace(/→/g, '->')
    .replace(/←/g, '<-')
    .replace(/[^\x20-\x7E]/g, (ch) => {
      const cp = ch.codePointAt(0)
      return cp !== undefined && cp <= 0xffff ? `#${cp};` : ch
    })
}

/** Normalize id["label"] before edge parsing so | inside labels is not mistaken for edge syntax */
function normalizeQuotedNodeLabels(code: string): string {
  return code.replace(/\b(\w+)\["((?:[^"\\]|\\.)*)"\]/g, (_m, id: string, label: string) => {
    return `${id}["${escapeLabelContent(label)}"]`
  })
}

function isStructuredNode(token: string): boolean {
  const t = token.trim()
  if (!t) return true
  if (/^["']/.test(t)) return true
  if (/^\w+[\[({\[<(]/.test(t)) return true
  if (/^subgraph\b/i.test(t)) return true
  return false
}

function slugNodeId(label: string): string {
  const slug = label
    .trim()
    .replace(/\s+/g, '_')
    .replace(/[^a-zA-Z0-9_]/g, '')
  if (slug && SIMPLE_ID.test(slug)) return slug
  return `node_${slug || 'id'}`
}

function quoteBareNode(token: string): string {
  const t = token.trim()
  if (!t || isStructuredNode(t)) return t
  if (SIMPLE_ID.test(t)) return t
  const id = slugNodeId(t)
  return `${id}["${escapeMermaidText(t)}"]`
}

function fixMissingClosingBracketBeforeEdge(line: string): string {
  return line.replace(
    /(\w+)\["([^"]+)"(\s*(?:-->|---->|---|-.->|==>|--o|o--|x--|--x))/g,
    '$1["$2"]$3',
  )
}

function fixOrphanClosingQuote(line: string): string {
  return line.replace(
    /^(\s*)([A-Za-z][\w\s]*?)"(\s*(?:-->|---->|---|-.->|==>|--o|o--|x--|--x))/,
    (_match, indent: string, label: string, suffix: string) =>
      `${indent}${slugNodeId(label)}["${escapeMermaidText(label.trim())}"]${suffix}`,
  )
}

function fixUnclosedBracketLabels(line: string): string {
  return line.replace(
    /(\w+)\[([^"\]\n]+?)"?(\s*(?:-->|---->|---|-.->|==>|--o|o--|x--|--x|\|))/g,
    (_match, id: string, label: string, suffix: string) =>
      `${id}["${escapeMermaidText(label.trim())}"]${suffix}`,
  )
}

function fixBracketLabels(code: string): string {
  return code.replace(/(\w+)\[([^\]"]+)\]/g, (_match, id: string, label: string) => {
    if (/[|&()\/=<>#:;+|\\⟩⟨]/.test(label) || /\s/.test(label)) {
      return `${id}["${escapeLabelContent(label)}"]`
    }
    return _match
  })
}

function fixBraceLabels(code: string): string {
  return code.replace(/(\w+)\{([^}"]+)\}/g, (_match, id: string, label: string) => {
    if (/[&()\/=<>#:;+|\\]/.test(label) || /\s/.test(label)) {
      return `${id}{"${escapeMermaidText(label)}"}`
    }
    return _match
  })
}

function fixParenLabels(code: string): string {
  return code.replace(/(\w+)\(([^)"]+)\)/g, (_match, id: string, label: string) => {
    if (/[&()\/=<>#:;+|\\]/.test(label) || /\s/.test(label)) {
      return `${id}("${escapeMermaidText(label)}")`
    }
    return _match
  })
}

function quoteEdgeLabels(line: string): string {
  // Only quote labels attached to arrows — never bare |...| inside node text
  return line.replace(
    /(-->|---->|---|-.->|==>|--o|o--|x--|--x)\s*\|([^|\n]+)\|/g,
    (match, op: string, label: string) => {
      const trimmed = label.trim()
      if (/^["']/.test(trimmed)) return match
      if (/[()&\/=<>#:;+[\]{}|\\"]/.test(trimmed) || /[^\x20-\x7E]/.test(trimmed)) {
        return `${op} |"${escapeMermaidText(trimmed)}"|`
      }
      return match
    },
  )
}

function sanitizeFlowchartEdgeLine(line: string): string {
  let result = fixMissingClosingBracketBeforeEdge(line)
  result = fixUnclosedBracketLabels(result)
  result = fixOrphanClosingQuote(result)
  result = quoteEdgeLabels(result)

  const edgeMatch = result.match(EDGE_OPS)
  if (!edgeMatch || edgeMatch.index === undefined) return result

  const op = edgeMatch[0]
  const idx = edgeMatch.index
  const before = result.slice(0, idx)
  const after = result.slice(idx + op.length)

  const indentMatch = before.match(/^(\s*)(.*)$/)
  const indent = indentMatch?.[1] ?? ''
  const sourceRaw = indentMatch?.[2]?.trim() ?? ''

  const edgeLabelMatch = after.match(/^\s*(\|[^|]*\|)\s*(.*)$/)
  const edgeLabel = edgeLabelMatch?.[1] ?? ''
  const targetPart = edgeLabelMatch?.[2] ?? after.trim()

  const source = quoteBareNode(sourceRaw)
  if (!targetPart) {
    return edgeLabel ? `${indent}${source} ${op} ${edgeLabel}` : `${indent}${source} ${op}`
  }

  const nextEdge = targetPart.search(/\s+(-->|---->|---|-.->|==>|--o|o--|x--|--x)/)
  let target: string
  let rest = ''
  if (nextEdge > 0) {
    target = quoteBareNode(targetPart.slice(0, nextEdge))
    rest = targetPart.slice(nextEdge)
  } else {
    const classMatch = targetPart.match(/^(.+?)(:::\S+.*)?$/)
    target = quoteBareNode(classMatch?.[1] ?? targetPart) + (classMatch?.[2] ?? '')
  }

  const spacer = edgeLabel ? ` ${edgeLabel} ` : ' '
  return `${indent}${source} ${op}${spacer}${target}${rest}`
}

export function sanitizeMermaidChart(code: string): string {
  let result = code.trim().replace(/%%.*$/gm, '')

  result = normalizeQuotedNodeLabels(result)

  result = fixBracketLabels(result)
  result = fixBraceLabels(result)
  result = fixParenLabels(result)

  result = result.replace(/subgraph\s+(\w+)\[([^\]]+)\]/gi, (_m, id: string, title: string) => {
    const safe = escapeMermaidText(title.replace(/^"|"$/g, ''))
    return `subgraph ${id}["${safe}"]`
  })

  const lines = result.split('\n')
  const isFlowchart = /^\s*(flowchart|graph)\s/i.test(lines[0] ?? '')

  if (isFlowchart) {
    result = lines
      .map((line, i) => {
        if (i === 0) return line
        if (/^\s*%%/.test(line)) return line
        // Strip interactive / XSS-prone directives (never pass click through)
        if (/^\s*(click|call)\s/i.test(line)) return ''
        if (/^\s*(classDef|class|style|linkStyle|direction)\s/i.test(line)) return line
        if (EDGE_OPS.test(line)) return sanitizeFlowchartEdgeLine(line)
        const bareMatch = line.match(/^(\s*)(.+)$/)
        if (bareMatch && /\s/.test(bareMatch[2]!) && !/[\[({"'<:]/.test(bareMatch[2]!)) {
          return `${bareMatch[1]}${quoteBareNode(bareMatch[2]!)}`
        }
        return line
      })
      .filter((line, i, arr) => line !== '' || (i > 0 && arr[i - 1] !== ''))
      .join('\n')
  }

  // Strip click/call and javascript: anywhere (non-flowchart diagrams too)
  result = result
    .split('\n')
    .filter((line) => !/^\s*(click|call)\s/i.test(line))
    .join('\n')
    .replace(/javascript\s*:/gi, 'blocked:')

  return result.trim()
}

export function repairMermaidChart(code: string): string {
  return sanitizeMermaidChart(code)
}

export type MermaidParseErrorInfo = {
  line?: number
  summary: string
  detail: string
  sourceLine?: string
}

export function parseMermaidError(message: string): MermaidParseErrorInfo {
  const lineMatch = message.match(/(?:on\s+)?line\s+(\d+)/i)
  const line = lineMatch ? Number(lineMatch[1]) : undefined
  const gotMatch = message.match(/got\s+'([^']+)'/i)
  const got = gotMatch?.[1]

  let detail = message.replace(/^Parse error on line \d+:\s*/i, '').trim()
  if (!detail) detail = message.trim()

  let summary = "Couldn't render this diagram"
  if (line) {
    summary = `Diagram syntax error on line ${line}`
    if (got) summary += ` (unexpected '${got}')`
  }

  return { line, summary, detail }
}

export function formatMermaidError(message: string, source?: string): string {
  const parsed = parseMermaidError(message)
  const lines = source?.split('\n') ?? []
  const sourceLine =
    parsed.line && parsed.line > 0 ? lines[parsed.line - 1]?.trimEnd() : undefined

  const parts = [parsed.summary]
  if (sourceLine) parts.push(`Line ${parsed.line}: ${sourceLine}`)
  if (parsed.detail && parsed.detail !== parsed.summary) parts.push(parsed.detail)
  return parts.join('\n')
}
