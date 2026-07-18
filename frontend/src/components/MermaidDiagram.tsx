import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import mermaid from 'mermaid'
import {
  Maximize2,
  Minimize2,
  ZoomIn,
  ZoomOut,
  Download,
  Code2,
  ChevronDown,
  AlertCircle,
  Wand2,
  Copy,
  Check,
  Scan,
} from 'lucide-react'
import {
  computeFitZoom,
  detectDiagramType,
  getDiagramDisplayLabel,
  enhanceMermaidSvg,
  formatMermaidError,
  getAppTheme,
  getMermaidConfig,
  repairMermaidChart,
  sanitizeMermaidChart,
  type AppTheme,
} from '../utils/mermaidUtils'

let mermaidReady = false
let mermaidActiveTheme: AppTheme | null = null

function ensureMermaid(theme: AppTheme) {
  if (!mermaidReady || mermaidActiveTheme !== theme) {
    mermaid.initialize(getMermaidConfig(theme))
    mermaidReady = true
    mermaidActiveTheme = theme
  }
}

async function renderLocalSvg(code: string, renderId: string, theme: AppTheme): Promise<string> {
  ensureMermaid(theme)
  await mermaid.parse(code)
  const { svg } = await mermaid.render(renderId, code)
  return svg
}

async function fetchChartSvg(
  code: string,
  renderId: string,
  theme: AppTheme,
): Promise<string> {
  // Local-first: never send private diagram source to mermaid.ink by default.
  const sanitized = sanitizeMermaidChart(code)
  return renderLocalSvg(sanitized, `mmd-${renderId}-${Date.now()}`, theme)
}

async function tryRenderChart(
  chart: string,
  renderId: string,
  theme: AppTheme,
): Promise<{ svg: string; source: string }> {
  const sanitized = sanitizeMermaidChart(chart)
  try {
    const rawSvg = await fetchChartSvg(sanitized, renderId, theme)
    return { svg: rawSvg, source: sanitized }
  } catch (firstErr) {
    const repaired = repairMermaidChart(chart)
    if (repaired === sanitized) throw firstErr
    try {
      const rawSvg = await fetchChartSvg(repaired, `${renderId}-fix`, theme)
      return { svg: rawSvg, source: repaired }
    } catch {
      throw firstErr
    }
  }
}

interface Props {
  chart: string
}

export default function MermaidDiagram({ chart }: Props) {
  const renderId = useId().replace(/:/g, '')
  const diagramLabel = getDiagramDisplayLabel(chart)
  const diagramKind = detectDiagramType(chart)
  const [theme, setTheme] = useState<AppTheme>(() => getAppTheme())

  const [svg, setSvg] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [errorSource, setErrorSource] = useState('')
  const [activeSource, setActiveSource] = useState('')
  const [autoFixed, setAutoFixed] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [showSource, setShowSource] = useState(false)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [copied, setCopied] = useState(false)
  const canvasRef = useRef<HTMLDivElement>(null)
  const dragging = useRef(false)
  const dragStart = useRef({ x: 0, y: 0, panX: 0, panY: 0 })
  const wasExpandedRef = useRef(false)
  const userAdjustedViewRef = useRef(false)

  const resetView = useCallback(() => {
    userAdjustedViewRef.current = false
    setPan({ x: 0, y: 0 })
    setZoom(1)
  }, [])

  const fitToView = useCallback((): boolean => {
    const el = canvasRef.current
    if (!el || !svg) return false
    const w = el.clientWidth
    const h = el.clientHeight
    if (w <= 0 || h <= 0) return false
    setPan({ x: 0, y: 0 })
    const nextZoom = computeFitZoom(svg, w, h)
    setZoom((prev) => (Math.abs(prev - nextZoom) < 0.01 ? prev : nextZoom))
    userAdjustedViewRef.current = false
    return true
  }, [svg])

  const renderChart = useCallback(async (source: string, attemptAutoFix: boolean) => {
    setLoading(true)
    setSvg('')
    setError('')
    setErrorSource('')
    setAutoFixed(false)
    resetView()

    const codeToRender = attemptAutoFix ? repairMermaidChart(source) : source
    const activeTheme = getAppTheme()

    try {
      const sanitized = sanitizeMermaidChart(codeToRender)
      const rawSvg = await fetchChartSvg(sanitized, renderId, activeTheme)
      const enhanced = enhanceMermaidSvg(rawSvg, diagramKind)
      setActiveSource(sanitized)
      setSvg(enhanced)
      if (attemptAutoFix && sanitized !== sanitizeMermaidChart(source)) {
        setAutoFixed(true)
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Invalid diagram syntax'
      setSvg('')
      setError(formatMermaidError(message, codeToRender))
      setErrorSource(codeToRender)
      setActiveSource(codeToRender)
    } finally {
      setLoading(false)
    }
  }, [diagramKind, renderId, resetView])

  useEffect(() => {
    const root = document.documentElement
    const syncTheme = () => setTheme(getAppTheme())
    syncTheme()
    const observer = new MutationObserver(syncTheme)
    observer.observe(root, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    let cancelled = false

    async function render() {
      try {
        const { svg: rawSvg, source } = await tryRenderChart(chart, renderId, theme)
        const enhanced = enhanceMermaidSvg(rawSvg, diagramKind)
        if (!cancelled) {
          setActiveSource(source)
          setSvg(enhanced)
          setAutoFixed(source !== sanitizeMermaidChart(chart))
        }
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : 'Invalid diagram syntax'
          setSvg('')
          setError(formatMermaidError(message, chart))
          setErrorSource(chart)
          setActiveSource(chart)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    setLoading(true)
    render()
    return () => { cancelled = true }
  }, [chart, renderId, diagramKind, theme, resetView])

  useEffect(() => {
    if (!expanded) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setExpanded(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [expanded])

  useEffect(() => {
    if (expanded) {
      wasExpandedRef.current = true
      const prev = document.body.style.overflow
      document.body.style.overflow = 'hidden'
      return () => {
        document.body.style.overflow = prev
      }
    }
    if (wasExpandedRef.current) {
      wasExpandedRef.current = false
    }
  }, [expanded])

  useLayoutEffect(() => {
    if (!svg || loading) return

    let cancelled = false
    let rafId = 0
    let retries = 0
    const maxRetries = 12

    const tryFit = () => {
      if (cancelled) return
      if (fitToView()) return
      if (retries < maxRetries) {
        retries += 1
        rafId = requestAnimationFrame(tryFit)
      }
    }

    tryFit()

    const el = canvasRef.current
    if (!el) {
      return () => {
        cancelled = true
        cancelAnimationFrame(rafId)
      }
    }

    const onResize = () => {
      if (cancelled || userAdjustedViewRef.current) return
      fitToView()
    }
    const observer = new ResizeObserver(onResize)
    observer.observe(el)

    return () => {
      cancelled = true
      cancelAnimationFrame(rafId)
      observer.disconnect()
    }
  }, [svg, loading, fitToView, expanded])

  const handleDownload = () => {
    if (!svg) return
    const blob = new Blob([svg], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${diagramKind.toLowerCase().replace(/\s+/g, '-')}.svg`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleCopySvg = async () => {
    if (!svg) return
    try {
      await navigator.clipboard.writeText(svg)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard unavailable */
    }
  }

  const onPointerDown = (e: React.PointerEvent) => {
    if (!expanded || e.button !== 0) return
    dragging.current = true
    dragStart.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y }
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }

  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragging.current) return
    userAdjustedViewRef.current = true
    setPan({
      x: dragStart.current.panX + (e.clientX - dragStart.current.x),
      y: dragStart.current.panY + (e.clientY - dragStart.current.y),
    })
  }

  const onPointerUp = (e: React.PointerEvent) => {
    dragging.current = false
    ;(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
  }

  const onWheel = (e: React.WheelEvent) => {
    if (!expanded) return
    e.preventDefault()
    userAdjustedViewRef.current = true
    const delta = e.deltaY > 0 ? -0.12 : 0.12
    setZoom((z) => Math.max(0.4, Math.min(3.5, z + delta)))
  }

  const openExpanded = () => setExpanded(true)

  const displaySource = activeSource || chart

  const artifactPanel = (
    <div className={`diagram-artifact ${expanded ? 'diagram-artifact-expanded' : ''}`}>
      <div className="diagram-artifact-toolbar">
        <div className="diagram-artifact-title">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
            <rect x="1.5" y="1.5" width="13" height="13" rx="2" stroke="currentColor" strokeWidth="1.2"/>
            <path d="M4 10 L7 6 L10 8.5 L12 5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span>{diagramLabel}</span>
          {diagramKind !== 'Diagram' && (
            <span className="diagram-artifact-kind">{diagramKind}</span>
          )}
          {autoFixed && <span className="diagram-artifact-fixed-badge">Auto-fixed</span>}
        </div>

        <div className="diagram-artifact-actions">
          {svg && !expanded && (
            <>
              <button
                type="button"
                className="diagram-btn-expand"
                onClick={openExpanded}
                title="Expand diagram"
              >
                <Maximize2 size={15} />
                <span>Expand</span>
              </button>
              <button type="button" onClick={handleDownload} title="Download SVG">
                <Download size={15} />
              </button>
              <button type="button" onClick={handleCopySvg} title="Copy SVG">
                {copied ? <Check size={15} /> : <Copy size={15} />}
              </button>
            </>
          )}

          {svg && expanded && (
            <>
              <button
                type="button"
                className={`diagram-source-toggle ${showSource ? 'is-active' : ''}`}
                onClick={() => setShowSource((v) => !v)}
                title={showSource ? 'Hide source' : 'View source'}
              >
                <Code2 size={14} />
                <span>Source</span>
                <ChevronDown size={13} className={`diagram-chevron ${showSource ? 'is-open' : ''}`} />
              </button>

              <span className="diagram-action-divider" aria-hidden />

              <button
                type="button"
                onClick={() => {
                  userAdjustedViewRef.current = true
                  setZoom((z) => Math.max(0.4, z - 0.15))
                }}
                title="Zoom out"
              >
                <ZoomOut size={15} />
              </button>
              <button
                type="button"
                onClick={() => {
                  userAdjustedViewRef.current = true
                  setZoom((z) => Math.min(3.5, z + 0.15))
                }}
                title="Zoom in"
              >
                <ZoomIn size={15} />
              </button>
              <button type="button" onClick={fitToView} title="Fit to view">
                <Scan size={15} />
              </button>
              <button type="button" onClick={handleCopySvg} title="Copy SVG">
                {copied ? <Check size={15} /> : <Copy size={15} />}
              </button>
              <button type="button" onClick={handleDownload} title="Download SVG">
                <Download size={15} />
              </button>
              <button
                type="button"
                onClick={() => setExpanded(false)}
                title="Close"
              >
                <Minimize2 size={15} />
              </button>
            </>
          )}
        </div>
      </div>

      {showSource && (expanded || (!svg && error)) && (
        <div className="diagram-artifact-source">
          <pre><code>{displaySource.trim()}</code></pre>
        </div>
      )}

      <div
        className={`diagram-artifact-canvas${
          expanded ? ' diagram-artifact-canvas--pannable' : ' diagram-artifact-canvas--expandable'
        }`}
        ref={canvasRef}
        role={!expanded && svg ? 'button' : undefined}
        tabIndex={!expanded && svg ? 0 : undefined}
        aria-label={!expanded && svg ? 'Expand diagram' : undefined}
        onClick={!expanded && svg ? openExpanded : undefined}
        onKeyDown={!expanded && svg ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openExpanded() } } : undefined}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onWheel={onWheel}
      >
        {loading && (
          <div className="diagram-artifact-loading" role="status" aria-live="polite">
            <div className="diagram-svg-skeleton" aria-hidden>
              <div className="diagram-svg-skeleton-node diagram-svg-skeleton-node-a" />
              <div className="diagram-svg-skeleton-node diagram-svg-skeleton-node-b" />
              <div className="diagram-svg-skeleton-node diagram-svg-skeleton-node-c diagram-svg-skeleton-node-diamond" />
              <div className="diagram-svg-skeleton-node diagram-svg-skeleton-node-d" />
              <div className="diagram-svg-skeleton-connector diagram-svg-skeleton-connector-1" />
              <div className="diagram-svg-skeleton-connector diagram-svg-skeleton-connector-2" />
              <div className="diagram-svg-skeleton-connector diagram-svg-skeleton-connector-3" />
            </div>
            <span>Rendering diagram…</span>
          </div>
        )}

        {!loading && svg && (
          <>
            <div
              className="diagram-artifact-svg-wrap"
              style={{
                transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                transformOrigin: 'center center',
              }}
              dangerouslySetInnerHTML={{ __html: svg }}
            />
            {!expanded && (
              <div className="diagram-expand-hint" aria-hidden>
                <Maximize2 size={14} />
                <span>Click to expand</span>
              </div>
            )}
          </>
        )}

        {!loading && !svg && (
          <div className="diagram-artifact-error">
            <div className="diagram-artifact-error-head">
              <AlertCircle size={16} />
              <p>Couldn&apos;t render this diagram</p>
            </div>
            {error && (
              <pre className="diagram-artifact-error-detail">{error}</pre>
            )}
            <div className="diagram-artifact-error-actions">
              <button
                type="button"
                className="diagram-artifact-error-source"
                onClick={() => setShowSource(true)}
              >
                View source
              </button>
              <button
                type="button"
                className="diagram-artifact-error-fix"
                onClick={() => renderChart(errorSource || chart, true)}
              >
                <Wand2 size={14} />
                Try auto-fix
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )

  if (expanded) {
    return createPortal(
      <>
        <button
          type="button"
          className="diagram-artifact-backdrop"
          aria-label="Close expanded diagram"
          onClick={() => setExpanded(false)}
        />
        {artifactPanel}
      </>,
      document.body,
    )
  }

  return artifactPanel
}
