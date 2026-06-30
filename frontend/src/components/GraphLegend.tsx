/**
 * GraphLegend — the visual key for the entity link-analysis subgraph (FRONTEND-9; blueprint
 * Part 11 / Part 24.4 screen 4). Documents the node-type palette + shapes, the edge-type encoding
 * and the three risk overlays the investigator must be able to read at a glance:
 *   • maker-checker collusion edges (SoD red, dashed, animated)
 *   • ring_id clusters (RNG-* — a dashed convex outline / coloured members)
 *   • GNNExplainer evidence emphasis (brightened, the rest dimmed)
 *
 * Colours/shapes are kept in `GRAPH_NODE_STYLE` / `GRAPH_EDGE_STYLE` so GraphView and this legend
 * read from one source of truth (no drift between the canvas and its key).
 */
import {
  User,
  Users,
  HandCoins,
  Landmark,
  MonitorSmartphone,
  Globe,
  Phone,
  MapPin,
  Sparkles,
  ShieldAlert,
  Spline,
  type LucideIcon,
} from 'lucide-react'
import { cn } from '@/lib/cn'
import { humanize } from '@/lib/format'
import type { GraphEdgeType, GraphNodeType } from '@/lib/types'

/* ── Node encoding (colour + cytoscape shape + label/icon) — single source of truth ──────────── */
export interface NodeStyle {
  /** Domain CSS-variable name (resolved to a concrete colour in GraphView via getComputedStyle). */
  colorVar: string
  /** Static fallback colour (used in the legend swatches + when CSS vars can't be read). */
  fallback: string
  /** cytoscape node shape token. */
  shape:
    | 'ellipse'
    | 'round-rectangle'
    | 'round-diamond'
    | 'round-hexagon'
    | 'round-tag'
    | 'round-pentagon'
    | 'round-triangle'
  icon: LucideIcon
  label: string
}

export const GRAPH_NODE_STYLE: Record<GraphNodeType, NodeStyle> = {
  employee: {
    colorVar: '--severity-high',
    fallback: 'hsl(25 95% 57%)',
    shape: 'ellipse',
    icon: User,
    label: 'Employee',
  },
  customer: {
    colorVar: '--primary',
    fallback: 'hsl(199 89% 52%)',
    shape: 'round-rectangle',
    icon: Users,
    label: 'Customer',
  },
  beneficiary: {
    colorVar: '--severity-critical',
    fallback: 'hsl(348 83% 60%)',
    shape: 'round-diamond',
    icon: HandCoins,
    label: 'Beneficiary',
  },
  account: {
    colorVar: '--reason-graph',
    fallback: 'hsl(161 70% 50%)',
    shape: 'round-tag',
    icon: Landmark,
    label: 'Account',
  },
  device: {
    colorVar: '--reason-shap',
    fallback: 'hsl(271 76% 70%)',
    shape: 'round-hexagon',
    icon: MonitorSmartphone,
    label: 'Device',
  },
  ip: {
    colorVar: '--severity-medium',
    fallback: 'hsl(43 96% 58%)',
    shape: 'round-pentagon',
    icon: Globe,
    label: 'IP address',
  },
  phone: {
    colorVar: '--sla-warn',
    fallback: 'hsl(43 96% 58%)',
    shape: 'round-triangle',
    icon: Phone,
    label: 'Phone',
  },
  address: {
    colorVar: '--muted-foreground',
    fallback: 'hsl(215 18% 64%)',
    shape: 'round-rectangle',
    icon: MapPin,
    label: 'Address',
  },
}

/* ── Edge encoding (colour + line style + label) ─────────────────────────────────────────────── */
export interface EdgeStyle {
  colorVar: string
  fallback: string
  style: 'solid' | 'dashed' | 'dotted'
  label: string
  /** Edges that are inherently risk-bearing get a heavier default width. */
  emphasis?: boolean
}

export const GRAPH_EDGE_STYLE: Record<GraphEdgeType, EdgeStyle> = {
  maker_checker: {
    colorVar: '--severity-critical',
    fallback: 'hsl(348 83% 60%)',
    style: 'solid',
    label: 'Maker → checker',
    emphasis: true,
  },
  shared_device: {
    colorVar: '--reason-shap',
    fallback: 'hsl(271 76% 70%)',
    style: 'dashed',
    label: 'Shared device',
  },
  shared_ip: {
    colorVar: '--severity-medium',
    fallback: 'hsl(43 96% 58%)',
    style: 'dashed',
    label: 'Shared IP',
  },
  shared_phone: {
    colorVar: '--sla-warn',
    fallback: 'hsl(43 96% 58%)',
    style: 'dashed',
    label: 'Shared phone',
  },
  shared_address: {
    colorVar: '--muted-foreground',
    fallback: 'hsl(215 18% 64%)',
    style: 'dashed',
    label: 'Shared address',
  },
  beneficiary: {
    colorVar: '--reason-graph',
    fallback: 'hsl(161 70% 50%)',
    style: 'solid',
    label: 'Beneficiary',
  },
  circular_flow: {
    colorVar: '--severity-critical',
    fallback: 'hsl(348 83% 60%)',
    style: 'dotted',
    label: 'Circular flow',
    emphasis: true,
  },
  mule: {
    colorVar: '--severity-high',
    fallback: 'hsl(25 95% 57%)',
    style: 'dotted',
    label: 'Mule transfer',
    emphasis: true,
  },
  transaction: {
    colorVar: '--primary',
    fallback: 'hsl(199 89% 52%)',
    style: 'solid',
    label: 'Transaction',
  },
}

function Swatch({ color, className }: { color: string; className?: string }) {
  return (
    <span
      className={cn('size-3 shrink-0 rounded-[3px] ring-1 ring-inset ring-black/20', className)}
      style={{ backgroundColor: color }}
      aria-hidden
    />
  )
}

function LegendRow({
  swatch,
  icon: Icon,
  label,
  hint,
}: {
  swatch: React.ReactNode
  icon?: LucideIcon
  label: string
  hint?: string
}) {
  return (
    <li className="flex items-center gap-2">
      {swatch}
      {Icon ? <Icon className="size-3.5 text-muted-foreground" aria-hidden /> : null}
      <span className="text-foreground">{label}</span>
      {hint ? <span className="ml-auto text-[0.7rem] text-muted-foreground">{hint}</span> : null}
    </li>
  )
}

/**
 * GraphLegend — render the full key. `nodeTypes`/`edgeTypes`, when supplied, restrict the legend to
 * the encodings actually present in the current subgraph (so it stays dense); omit to show all.
 */
export function GraphLegend({
  nodeTypes,
  edgeTypes,
  className,
}: {
  nodeTypes?: GraphNodeType[]
  edgeTypes?: GraphEdgeType[]
  className?: string
}) {
  const nodeKeys =
    nodeTypes && nodeTypes.length
      ? (Object.keys(GRAPH_NODE_STYLE) as GraphNodeType[]).filter((t) => nodeTypes.includes(t))
      : (Object.keys(GRAPH_NODE_STYLE) as GraphNodeType[])
  const edgeKeys =
    edgeTypes && edgeTypes.length
      ? (Object.keys(GRAPH_EDGE_STYLE) as GraphEdgeType[]).filter((t) => edgeTypes.includes(t))
      : (Object.keys(GRAPH_EDGE_STYLE) as GraphEdgeType[])

  return (
    <div className={cn('space-y-3 text-xs', className)}>
      <section>
        <p className="mb-1.5 font-semibold uppercase tracking-wide text-muted-foreground">Nodes</p>
        <ul className="grid grid-cols-2 gap-x-4 gap-y-1.5">
          {nodeKeys.map((t) => {
            const s = GRAPH_NODE_STYLE[t]
            return (
              <LegendRow
                key={t}
                swatch={<Swatch color={s.fallback} className="rounded-full" />}
                icon={s.icon}
                label={s.label}
              />
            )
          })}
        </ul>
        <p className="mt-1.5 text-[0.7rem] text-muted-foreground">
          Node size scales with risk score · the focus entity has a bright ring.
        </p>
      </section>

      <section>
        <p className="mb-1.5 font-semibold uppercase tracking-wide text-muted-foreground">Edges</p>
        <ul className="grid grid-cols-2 gap-x-4 gap-y-1.5">
          {edgeKeys.map((t) => {
            const s = GRAPH_EDGE_STYLE[t]
            return (
              <LegendRow
                key={t}
                swatch={
                  <span
                    className="h-0 w-5 shrink-0"
                    style={{
                      borderTopWidth: s.emphasis ? 2.5 : 1.5,
                      borderTopStyle: s.style,
                      borderTopColor: s.fallback,
                    }}
                    aria-hidden
                  />
                }
                label={s.label}
              />
            )
          })}
        </ul>
      </section>

      <section>
        <p className="mb-1.5 font-semibold uppercase tracking-wide text-muted-foreground">
          Risk overlays
        </p>
        <ul className="space-y-1.5">
          <li className="flex items-start gap-2">
            <ShieldAlert className="mt-0.5 size-3.5 shrink-0 text-severity-critical" aria-hidden />
            <span>
              <span className="font-medium text-severity-critical">Maker-checker collusion</span> —
              segregation-of-duties breach; the edge is thick, red and animated.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <Spline className="mt-0.5 size-3.5 shrink-0 text-reason-graph" aria-hidden />
            <span>
              <span className="font-medium text-reason-graph">Ring cluster (RNG-*)</span> — members
              of a detected motif share a dashed halo and matched outline.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <Sparkles className="mt-0.5 size-3.5 shrink-0 text-ai" aria-hidden />
            <span>
              <span className="font-medium text-ai">GNNExplainer evidence</span> — when toggled on,
              the nodes/edges the graph model relied on are brightened and the rest are dimmed.
            </span>
          </li>
        </ul>
      </section>
    </div>
  )
}

/** Friendly label for an arbitrary node/edge type token (legend popovers, node detail). */
export function graphTypeLabel(type: GraphNodeType | GraphEdgeType | string): string {
  return (
    (GRAPH_NODE_STYLE as Record<string, NodeStyle>)[type]?.label ??
    (GRAPH_EDGE_STYLE as Record<string, EdgeStyle>)[type]?.label ??
    humanize(type)
  )
}
