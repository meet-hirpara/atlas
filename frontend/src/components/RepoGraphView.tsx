import { useEffect, useMemo, useRef, useState } from 'react'

import type { GraphEdge, GraphNode, RepoGraph } from '../github'

interface Props {
  graph: RepoGraph
  selectedNodeId?: string | null
  onSelectNode?: (id: string | null) => void
}

const TYPE_COLORS: Record<string, string> = {
  module: '#6366f1',
  function: '#22c55e',
  class: '#f59e0b',
  import: '#94a3b8',
}

function layoutNodes(nodes: GraphNode[], _edges: GraphEdge[], width: number, height: number) {
  const positions = new Map<string, { x: number; y: number }>()
  const byFile = new Map<string, GraphNode[]>()
  for (const n of nodes) {
    const file = n.file || 'unknown'
    if (!byFile.has(file)) byFile.set(file, [])
    byFile.get(file)!.push(n)
  }

  const files = Array.from(byFile.keys())
  const cols = Math.ceil(Math.sqrt(files.length)) || 1
  const cellW = width / cols
  const rows = Math.ceil(files.length / cols) || 1
  const cellH = height / rows

  files.forEach((file, fi) => {
    const col = fi % cols
    const row = Math.floor(fi / cols)
    const fileNodes = byFile.get(file)!
    fileNodes.forEach((n, ni) => {
      const nx = col * cellW + cellW * 0.15 + (ni % 3) * (cellW * 0.25)
      const ny = row * cellH + cellH * 0.2 + Math.floor(ni / 3) * 36
      positions.set(n.id, { x: nx, y: ny })
    })
  })

  return positions
}

export default function RepoGraphView({ graph, selectedNodeId, onSelectNode }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [size, setSize] = useState({ w: 800, h: 500 })

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect
      setSize({ w: Math.max(400, width), h: Math.max(320, height) })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const displayGraph = useMemo(() => {
    const maxNodes = 120
    if (graph.nodes.length <= maxNodes) return graph
    const modules = graph.nodes.filter((n) => n.type === 'module')
    const picked = new Set(modules.slice(0, 40).map((n) => n.id))
    for (const n of graph.nodes) {
      if (picked.size >= maxNodes) break
      if (n.type === 'function') picked.add(n.id)
    }
    const nodes = graph.nodes.filter((n) => picked.has(n.id))
    const nodeIds = new Set(nodes.map((n) => n.id))
    const edges = graph.edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
    return { nodes, edges }
  }, [graph])

  const positions = useMemo(
    () => layoutNodes(displayGraph.nodes, displayGraph.edges, size.w, size.h),
    [displayGraph, size],
  )

  if (!displayGraph.nodes.length) {
    return (
      <div className="github-graph-empty">
        No code graph yet — index a repo with Python or JS/TS files.
      </div>
    )
  }

  return (
    <div className="github-graph-wrap" ref={containerRef}>
      {graph.nodes.length > displayGraph.nodes.length && (
        <p className="github-graph-truncate">
          Showing {displayGraph.nodes.length} of {graph.nodes.length} nodes
        </p>
      )}
      <svg className="github-graph-svg" width={size.w} height={size.h}>
        {displayGraph.edges.map((e, i) => {
          const s = positions.get(e.source)
          const t = positions.get(e.target)
          if (!s || !t) return null
          return (
            <line
              key={`${e.source}-${e.target}-${i}`}
              x1={s.x}
              y1={s.y}
              x2={t.x}
              y2={t.y}
              className={`github-graph-edge github-graph-edge-${e.type}`}
            />
          )
        })}
        {displayGraph.nodes.map((n) => {
          const p = positions.get(n.id)
          if (!p) return null
          const selected = selectedNodeId === n.id
          const color = TYPE_COLORS[n.type] || '#64748b'
          return (
            <g
              key={n.id}
              transform={`translate(${p.x}, ${p.y})`}
              className={`github-graph-node${selected ? ' github-graph-node-selected' : ''}`}
              onClick={() => onSelectNode?.(selected ? null : n.id)}
            >
              <circle r={selected ? 10 : 7} fill={color} opacity={selected ? 1 : 0.85} />
              <text y={18} textAnchor="middle" className="github-graph-label">
                {n.label.length > 22 ? `${n.label.slice(0, 20)}…` : n.label}
              </text>
            </g>
          )
        })}
      </svg>
      <div className="github-graph-legend">
        {Object.entries(TYPE_COLORS).map(([type, color]) => (
          <span key={type} className="github-graph-legend-item">
            <span className="github-graph-legend-dot" style={{ background: color }} />
            {type}
          </span>
        ))}
      </div>
    </div>
  )
}
