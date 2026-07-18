import type { MermaidConfig } from 'mermaid'

export {
  formatMermaidError,
  parseMermaidError,
  repairMermaidChart,
  sanitizeMermaidChart,
} from './mermaidSanitize'
export type { MermaidParseErrorInfo } from './mermaidSanitize'

const DIAGRAM_TYPE_LABELS: [RegExp, string][] = [
  [/^flowchart\b/i, 'Flowchart'],
  [/^graph\b/i, 'Flowchart'],
  [/^sequencediagram\b/i, 'Sequence diagram'],
  [/^classdiagram\b/i, 'Class diagram'],
  [/^statediagram(?:-v2)?\b/i, 'State diagram'],
  [/^erdiagram\b/i, 'ER diagram'],
  [/^gantt\b/i, 'Gantt chart'],
  [/^pie\b/i, 'Pie chart'],
  [/^gitgraph\b/i, 'Git graph'],
  [/^journey\b/i, 'User journey'],
  [/^mindmap\b/i, 'Mind map'],
  [/^timeline\b/i, 'Timeline'],
  [/^quadrantchart\b/i, 'Quadrant chart'],
  [/^xychart(?:-beta)?\b/i, 'XY chart'],
  [/^block-beta\b/i, 'Block diagram'],
  [/^architecture-beta\b/i, 'Architecture'],
  [/^c4context\b/i, 'C4 context'],
  [/^kanban\b/i, 'Kanban'],
  [/^sankey(?:-beta)?\b/i, 'Sankey'],
  [/^requirementdiagram\b/i, 'Requirements'],
]

export function detectDiagramType(code: string): string {
  const firstLine = code.trim().split('\n')[0]?.trim() ?? ''
  for (const [pattern, label] of DIAGRAM_TYPE_LABELS) {
    if (pattern.test(firstLine)) return label
  }
  return 'Diagram'
}

/** User-facing label in the diagram artifact toolbar */
export function getDiagramDisplayLabel(code?: string): string {
  if (!code) return 'Diagram'
  const kind = detectDiagramType(code)
  return kind === 'Diagram' ? 'Diagram' : kind
}

const DIAGRAM_FENCE_PATTERN =
  /```(mermaid|flowchart|graph|sequencediagram|classdiagram|statediagram-v2|statediagram|erdiagram|gantt|pie|mindmap|timeline|quadrantchart|gitgraph|journey|block-beta|architecture-beta|c4context|kanban|sankey-beta|requirementdiagram|xychart-beta|xychart)\s*\n?([\s\S]*?)```/gi

const OPEN_DIAGRAM_FENCE_PATTERN =
  /```(?:mermaid|flowchart|graph|sequencediagram|classdiagram|statediagram-v2|statediagram|erdiagram|gantt|pie|mindmap|timeline|quadrantchart|gitgraph|journey|block-beta|architecture-beta|c4context|kanban|sankey-beta|requirementdiagram|xychart-beta|xychart)\b/i

const DIAGRAM_HEADER_PATTERN =
  /^(?:flowchart|graph|sequencediagram|classdiagram|statediagram(?:-v2)?|erdiagram|gantt|pie|mindmap|timeline|quadrantchart|gitgraph|journey|block-beta|architecture-beta|c4context|kanban|sankey(?:-beta)?|requirementdiagram|xychart(?:-beta)?)\b/i

export function normalizeDiagramSource(code: string, fenceLang?: string): string {
  const trimmed = code.trim()
  if (!trimmed) return trimmed
  const firstLine = trimmed.split('\n')[0]?.trim() ?? ''
  if (DIAGRAM_HEADER_PATTERN.test(firstLine)) return trimmed

  const lang = (fenceLang ?? '').toLowerCase()
  if (lang === 'flowchart' || lang === 'graph') {
    return `flowchart ${trimmed}`
  }
  if (lang && lang !== 'mermaid') {
    return `${lang} ${trimmed}`
  }
  return trimmed
}

export type AppTheme = 'dark' | 'light'

export function getAppTheme(): AppTheme {
  const explicit = document.documentElement.getAttribute('data-theme')
  if (explicit === 'light') return 'light'
  if (explicit === 'dark') return 'dark'
  return 'dark'
}

const LIGHT_THEME_VARIABLES = {
  primaryColor: '#ffffff',
  primaryTextColor: '#171717',
  primaryBorderColor: '#b8b8b4',
  secondaryColor: '#f5f5f3',
  secondaryTextColor: '#171717',
  secondaryBorderColor: '#b8b8b4',
  tertiaryColor: '#efefed',
  tertiaryTextColor: '#171717',
  tertiaryBorderColor: '#b8b8b4',
  lineColor: '#525252',
  textColor: '#171717',
  mainBkg: '#ffffff',
  nodeBorder: '#a3a3a0',
  clusterBkg: '#f5f5f3',
  clusterBorder: '#c8c8c4',
  titleColor: '#171717',
  edgeLabelBackground: '#ffffff',
  nodeTextColor: '#171717',
  actorBkg: '#f5f5f3',
  actorBorder: '#c8c8c4',
  actorTextColor: '#1a1a1a',
  actorLineColor: '#a3a3a3',
  signalColor: '#737373',
  signalTextColor: '#1a1a1a',
  labelBoxBkgColor: '#f5f5f3',
  labelBoxBorderColor: '#d4d4d0',
  labelTextColor: '#1a1a1a',
  loopTextColor: '#525252',
  noteBkgColor: '#f5f0e1',
  noteTextColor: '#1a1a1a',
  noteBorderColor: '#d4d4d0',
  activationBkgColor: '#ececea',
  activationBorderColor: '#a3a3a3',
  sequenceNumberColor: '#ffffff',
  sectionBkgColor: '#f5f5f3',
  altBackground: '#fafaf9',
  background: '#fafaf9',
  fontFamily: 'ui-sans-serif, system-ui, -apple-system, sans-serif',
  fontSize: '16px',
} as const

const DARK_THEME_VARIABLES = {
  primaryColor: '#40403e',
  primaryTextColor: '#f5f5f3',
  primaryBorderColor: '#6b6b68',
  secondaryColor: '#383836',
  secondaryTextColor: '#f5f5f3',
  secondaryBorderColor: '#6b6b68',
  tertiaryColor: '#454543',
  tertiaryTextColor: '#f5f5f3',
  tertiaryBorderColor: '#6b6b68',
  lineColor: '#c4c4c2',
  textColor: '#f5f5f3',
  mainBkg: '#40403e',
  nodeBorder: '#6b6b68',
  clusterBkg: '#333331',
  clusterBorder: '#555553',
  titleColor: '#f5f5f3',
  edgeLabelBackground: '#333331',
  nodeTextColor: '#f5f5f3',
  actorBkg: '#3a3a38',
  actorBorder: '#5a5a58',
  actorTextColor: '#ececec',
  actorLineColor: '#6b6b69',
  signalColor: '#a3a3a3',
  signalTextColor: '#ececec',
  labelBoxBkgColor: '#333331',
  labelBoxBorderColor: '#4a4a48',
  labelTextColor: '#ececec',
  loopTextColor: '#b4b4b4',
  noteBkgColor: '#3d3a30',
  noteTextColor: '#ececec',
  noteBorderColor: '#4a4a48',
  activationBkgColor: '#3a3a38',
  activationBorderColor: '#6b6b69',
  sequenceNumberColor: '#ececec',
  sectionBkgColor: '#333331',
  altBackground: '#2a2a28',
  background: '#262624',
  fontFamily: 'ui-sans-serif, system-ui, -apple-system, sans-serif',
  fontSize: '16px',
} as const

export function getMermaidConfig(theme: AppTheme = getAppTheme()): MermaidConfig {
  return {
    startOnLoad: false,
    suppressErrorRendering: true,
    theme: 'base',
    themeVariables: theme === 'dark'
      ? { ...DARK_THEME_VARIABLES }
      : { ...LIGHT_THEME_VARIABLES },
    flowchart: {
      curve: 'basis',
      padding: 28,
      htmlLabels: false,
      nodeSpacing: 64,
      rankSpacing: 72,
      useMaxWidth: true,
      wrappingWidth: 240,
    },
    sequence: {
      diagramMarginX: 28,
      diagramMarginY: 20,
      actorMargin: 64,
      width: 168,
      height: 52,
      boxMargin: 10,
      boxTextMargin: 8,
      noteMargin: 14,
      messageMargin: 44,
      useMaxWidth: true,
    },
    gantt: {
      useMaxWidth: true,
      barHeight: 24,
      barGap: 8,
      topPadding: 44,
      leftPadding: 64,
    },
    securityLevel: 'strict',
  }
}

function diagramKindSlug(label: string): string {
  return label.toLowerCase().replace(/\s+/g, '-')
}

export function enhanceMermaidSvg(svg: string, diagramLabel: string): string {
  if (typeof DOMParser === 'undefined') return svg

  const doc = new DOMParser().parseFromString(svg, 'image/svg+xml')
  const svgEl = doc.documentElement
  if (svgEl.querySelector('parsererror')) return svg

  // Strip XSS vectors before inject (click handlers, scripts, foreignObject, javascript: URLs)
  svgEl.querySelectorAll('script, foreignObject').forEach((el) => el.remove())
  svgEl.querySelectorAll('*').forEach((el) => {
    for (const attr of Array.from(el.attributes)) {
      const name = attr.name.toLowerCase()
      const value = attr.value
      if (name.startsWith('on')) {
        el.removeAttribute(attr.name)
        continue
      }
      if (
        (name === 'href' || name === 'xlink:href') &&
        /^\s*javascript:/i.test(value)
      ) {
        el.removeAttribute(attr.name)
      }
    }
  })

  const kind = diagramKindSlug(diagramLabel)
  svgEl.classList.add('claude-diagram', `claude-diagram--${kind}`)

  svgEl.querySelectorAll('.node rect, .cluster rect, .actor rect, g.label rect').forEach((shape) => {
    if (!shape.getAttribute('rx')) shape.setAttribute('rx', '6')
    if (!shape.getAttribute('ry')) shape.setAttribute('ry', '6')
  })

  svgEl.setAttribute('width', '100%')
  svgEl.removeAttribute('height')
  svgEl.setAttribute('preserveAspectRatio', 'xMidYMid meet')

  const style = svgEl.getAttribute('style')
  if (style) {
    const cleaned = style.replace(/max-width:\s*[^;]+;?/gi, '').trim()
    if (cleaned) svgEl.setAttribute('style', cleaned)
    else svgEl.removeAttribute('style')
  }

  const serialized = new XMLSerializer().serializeToString(svgEl)
  return trimSvgViewBox(serialized)
}

export function trimSvgViewBox(svg: string, padding = 16): string {
  if (typeof document === 'undefined') return svg

  const doc = new DOMParser().parseFromString(svg, 'image/svg+xml')
  const parsed = doc.documentElement
  if (parsed.querySelector('parsererror')) return svg

  const holder = document.createElement('div')
  holder.setAttribute('aria-hidden', 'true')
  holder.style.cssText = 'position:fixed;left:-10000px;top:0;opacity:0;pointer-events:none;'
  document.body.appendChild(holder)

  const clone = parsed.cloneNode(true) as SVGSVGElement
  holder.appendChild(clone)

  try {
    let bbox: DOMRect | null = null
    const measureTargets = [
      clone.querySelector('g.root'),
      clone.querySelector('g.graph'),
      clone.querySelector('.nodes'),
    ]

    for (const el of measureTargets) {
      if (!el) continue
      const graphic = el as SVGGraphicsElement
      if (typeof graphic.getBBox !== 'function') continue
      try {
        const box = graphic.getBBox()
        if (box.width > 0 && box.height > 0) {
          bbox = box
          break
        }
      } catch {
        /* getBBox can fail on empty groups */
      }
    }

    if (!bbox || bbox.width <= 0 || bbox.height <= 0) return svg

    const x = bbox.x - padding
    const y = bbox.y - padding
    const w = bbox.width + padding * 2
    const h = bbox.height + padding * 2
    clone.setAttribute('viewBox', `${x} ${y} ${w} ${h}`)
    clone.setAttribute('width', '100%')
    clone.removeAttribute('height')
    clone.setAttribute('preserveAspectRatio', 'xMidYMid meet')

    return new XMLSerializer().serializeToString(clone)
  } finally {
    document.body.removeChild(holder)
  }
}

function readSvgViewBoxSize(svgMarkup: string): { width: number; height: number } | null {
  if (typeof DOMParser === 'undefined') return null
  const doc = new DOMParser().parseFromString(svgMarkup, 'image/svg+xml')
  const svgEl = doc.documentElement
  const viewBox = svgEl.getAttribute('viewBox')
  if (viewBox) {
    const parts = viewBox.split(/\s+/).map(Number)
    if (parts.length === 4 && parts[2] > 0 && parts[3] > 0) {
      return { width: parts[2], height: parts[3] }
    }
  }
  const w = parseFloat(svgEl.getAttribute('width') ?? '0')
  const h = parseFloat(svgEl.getAttribute('height') ?? '0')
  if (w > 0 && h > 0) return { width: w, height: h }
  return null
}

export interface FitZoomOptions {
  padding?: number
  minZoom?: number
  maxZoom?: number
  /** When true, scale small diagrams up to use available height */
  fillHeight?: boolean
}

/**
 * Compute zoom so the diagram fits entirely inside the canvas (contain).
 */
export function computeFitZoom(
  svgMarkup: string,
  containerWidth: number,
  containerHeight = 0,
  options: FitZoomOptions = {},
): number {
  const size = readSvgViewBoxSize(svgMarkup)
  if (!size || containerWidth <= 0) return 1

  const pad = options.padding ?? 40
  const minZoom = options.minZoom ?? 0.45
  const maxZoom = options.maxZoom ?? 2.8

  const availW = Math.max(1, containerWidth - pad)
  const availH = containerHeight > 0 ? Math.max(1, containerHeight - pad) : 0

  // SVG is laid out at width:100% of container; base rendered height follows aspect.
  const aspect = size.height / size.width
  const baseRenderedW = availW
  const baseRenderedH = availW * aspect

  if (availH <= 0) return 1

  // True contain: scale so both width and height fit
  let zoom = Math.min(availW / baseRenderedW, availH / baseRenderedH)

  if (!Number.isFinite(zoom) || zoom <= 0) return 1
  return Math.max(minZoom, Math.min(maxZoom, zoom))
}

export function extractContentParts(content: string, isStreaming = false) {
  const parts: { type: 'text' | 'mermaid' | 'mermaid-pending'; value: string }[] = []
  const regex = new RegExp(DIAGRAM_FENCE_PATTERN.source, 'gi')
  let lastIndex = 0
  let match

  while ((match = regex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', value: content.slice(lastIndex, match.index) })
    }
    parts.push({
      type: 'mermaid',
      value: normalizeDiagramSource(match[2], match[1]),
    })
    lastIndex = match.index + match[0].length
  }

  const remaining = content.slice(lastIndex)
  if (remaining) {
    if (isStreaming && OPEN_DIAGRAM_FENCE_PATTERN.test(remaining)) {
      const openIdx = remaining.search(OPEN_DIAGRAM_FENCE_PATTERN)
      const before = remaining.slice(0, openIdx)
      if (before.trim()) parts.push({ type: 'text', value: before })
      parts.push({ type: 'mermaid-pending', value: '' })
    } else {
      parts.push({ type: 'text', value: remaining })
    }
  }

  return parts.length ? parts : [{ type: 'text' as const, value: content }]
}
