/**
 * Inline L5 graph-evidence mini-map — a compact, self-contained SVG that *draws* the collusion
 * subgraph the graph model surfaced (maker-checker ring, shared-identity links) instead of only
 * describing it in text. The highest-importance node sits at the centre; the rest fan out on a ring;
 * node radius scales with GNNExplainer importance and colour encodes node type; edges are drawn with
 * width/opacity ∝ their attribution. Deterministic layout (stable across renders), no graph lib —
 * this is a *glanceable* evidence thumbnail; the full investigation surface is the Graph tab.
 */
import { humanize } from '@/lib/format'
import type { GraphEvidence } from '@/lib/types'

const TYPE_COLOR: Record<string, string> = {
  employee: 'var(--reason-graph)',
  beneficiary: 'var(--severity-high)',
  account: 'var(--severity-medium)',
  device: 'var(--ai)',
  ip: 'var(--primary)',
  vendor: 'var(--severity-medium)',
}

const W = 320
const H = 190
const CX = W / 2
const CY = H / 2

function colorFor(type: string): string {
  return `hsl(${TYPE_COLOR[type] ?? 'var(--muted-foreground)'})`
}

export function GraphEvidenceMini({ graph }: { graph: GraphEvidence }) {
  const nodes = graph.nodes ?? []
  if (nodes.length < 2) return null

  // Centre = the most important node (the ring's focal actor); others fan out on a ring.
  const sorted = [...nodes].sort((a, b) => (b.importance ?? 0) - (a.importance ?? 0))
  const centre = sorted[0]
  const ring = sorted.slice(1)
  const radius = Math.min(CX, CY) - 34

  const pos = new Map<string, { x: number; y: number }>()
  pos.set(centre.id, { x: CX, y: CY })
  ring.forEach((n, i) => {
    // start at the top and go clockwise; -90° offset so the first spoke points up
    const angle = (i / ring.length) * Math.PI * 2 - Math.PI / 2
    pos.set(n.id, { x: CX + radius * Math.cos(angle), y: CY + radius * Math.sin(angle) })
  })

  const nodeRadius = (n: (typeof nodes)[number]) => 9 + Math.round((n.importance ?? 0.4) * 9)

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full"
      role="img"
      aria-label="Collusion subgraph evidence"
      style={{ maxHeight: 200 }}
    >
      {/* edges first so nodes sit on top */}
      {(graph.edges ?? []).map((e, i) => {
        const a = pos.get(e.source)
        const b = pos.get(e.target)
        if (!a || !b) return null
        const imp = e.importance ?? 0.5
        const mx = (a.x + b.x) / 2
        const my = (a.y + b.y) / 2
        return (
          <g key={`${e.source}-${e.target}-${i}`}>
            <line
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke="hsl(var(--reason-graph))"
              strokeWidth={1 + imp * 2.5}
              strokeOpacity={0.35 + imp * 0.5}
            />
            <text
              x={mx}
              y={my - 3}
              textAnchor="middle"
              className="fill-muted-foreground"
              style={{ fontSize: 8 }}
            >
              {humanize(e.type)}
            </text>
          </g>
        )
      })}

      {/* nodes */}
      {nodes.map((n) => {
        const p = pos.get(n.id)
        if (!p) return null
        const r = nodeRadius(n)
        const isCentre = n.id === centre.id
        return (
          <g key={n.id}>
            {isCentre ? (
              <circle
                cx={p.x}
                cy={p.y}
                r={r + 4}
                fill="none"
                stroke={colorFor(n.type)}
                strokeOpacity={0.4}
                strokeWidth={1.5}
              />
            ) : null}
            <circle cx={p.x} cy={p.y} r={r} fill={colorFor(n.type)} fillOpacity={0.85} />
            <title>
              {n.label} · {humanize(n.type)}
              {n.importance != null ? ` · ${Math.round(n.importance * 100)}%` : ''}
            </title>
            <text
              x={p.x}
              y={p.y + r + 9}
              textAnchor="middle"
              className="fill-foreground"
              style={{ fontSize: 8.5, fontFamily: 'var(--font-mono, monospace)' }}
            >
              {n.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
