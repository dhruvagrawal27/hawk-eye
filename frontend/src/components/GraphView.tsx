/**
 * GraphView — interactive entity link-analysis subgraph (FRONTEND-9; blueprint Part 11 l.390 +
 * Part 24.4 screen 4). Renders `GET /entities/{id}/graph` (GraphResponse) on a Cytoscape.js canvas:
 *
 *   • nodes typed employee/customer/beneficiary/account/device/ip/phone/address — coloured + shaped
 *     by type (see GRAPH_NODE_STYLE), sized by risk, the `is_focus` entity ringed distinctly;
 *   • edges typed maker_checker, shared_device/ip/phone/address, beneficiary, circular_flow,
 *     mule and transaction;
 *   • HIGHLIGHTS: maker-checker collusion edges (collusion=true) are thick/red/animated, and
 *     ring_id clusters (rings[]) get a matched dashed halo;
 *   • OVERLAY: GNNExplainer evidence (explainer.node_ids/edge_ids) — when toggled on the cited
 *     elements brighten and everything else dims;
 *   • pan/zoom, layout selection (cose/breadthfirst/concentric/circle), a Fit button, and a node
 *     click that *selects + inspects* (popover) — never auto-navigates / never mutates.
 *
 * Golden rules respected: read-only (no block/disposition here), PII rendered tokenized via
 * <MaskedPII> in the node-detail popover, money in INR, loading/error via <QueryBoundary>, empty via
 * <EmptyState>. Cytoscape is mounted on a ref and destroyed on unmount (no react-cytoscapejs).
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import cytoscape, {
  type Core,
  type ElementDefinition,
  type EventObject,
  type LayoutOptions,
  type NodeSingular,
  type StylesheetStyle,
} from 'cytoscape'
import { Crosshair, Maximize2, Minus, Network, Plus, ShieldAlert, Sparkles, X } from 'lucide-react'
import { cn } from '@/lib/cn'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import {
  clamp,
  formatINR,
  formatNumber,
  humanize,
  isTokenizedPii,
  severityForScore,
} from '@/lib/format'
import type { GraphEdge, GraphEdgeType, GraphNode, GraphNodeType, GraphResponse } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { EmptyState } from '@/components/ui/empty-state'
import { QueryBoundary } from '@/components/QueryBoundary'
import { MaskedPII } from '@/components/MaskedPII'
import { SeverityBadge } from '@/components/badges'
import {
  GRAPH_EDGE_STYLE,
  GRAPH_NODE_STYLE,
  GraphLegend,
  graphTypeLabel,
} from '@/components/GraphLegend'

/* ── Layout presets (cytoscape built-ins; no external layout plugins) ────────────────────────── */
type LayoutName = 'cose' | 'breadthfirst' | 'concentric' | 'circle'
const LAYOUTS: { value: LayoutName; label: string }[] = [
  { value: 'cose', label: 'Force-directed' },
  { value: 'breadthfirst', label: 'Hierarchy' },
  { value: 'concentric', label: 'Concentric' },
  { value: 'circle', label: 'Circle' },
]

function layoutOptions(name: LayoutName): LayoutOptions {
  const base = { name, fit: true, padding: 36, animate: false as const }
  if (name === 'cose') {
    return {
      ...base,
      name: 'cose',
      idealEdgeLength: () => 110,
      nodeRepulsion: () => 9000,
      nodeOverlap: 18,
      gravity: 0.55,
      componentSpacing: 90,
      randomize: false,
    } as unknown as LayoutOptions
  }
  if (name === 'breadthfirst') {
    return { ...base, name: 'breadthfirst', spacingFactor: 1.15, directed: true } as LayoutOptions
  }
  if (name === 'concentric') {
    return {
      ...base,
      name: 'concentric',
      minNodeSpacing: 28,
      concentric: (n: NodeSingular) => (n.data('focus') ? 10 : Number(n.data('risk')) || 1),
      levelWidth: () => 2,
    } as unknown as LayoutOptions
  }
  return { ...base, name: 'circle', spacingFactor: 1.1 } as LayoutOptions
}

/* ── Resolve a domain CSS variable to a concrete colour cytoscape can paint ──────────────────── */
function colourResolver() {
  const root = typeof document !== 'undefined' ? document.documentElement : null
  const styles = root ? getComputedStyle(root) : null
  return (cssVar: string, fallback: string): string => {
    const raw = styles?.getPropertyValue(cssVar)?.trim()
    return raw ? `hsl(${raw})` : fallback
  }
}

/** Node diameter from risk score (undefined risk → mid). */
function nodeSize(risk?: number): number {
  const r = typeof risk === 'number' ? clamp(risk, 0, 100) : 45
  return Math.round(34 + (r / 100) * 34) // 34–68px
}

/* ── Build cytoscape elements + stylesheet from the API response ─────────────────────────────── */
function buildElements(graph: GraphResponse): ElementDefinition[] {
  const ringOf = new Map<string, string>()
  for (const ring of graph.rings ?? []) {
    for (const id of ring.member_ids) ringOf.set(id, ring.ring_id)
  }

  const nodes: ElementDefinition[] = graph.nodes.map((n: GraphNode) => ({
    group: 'nodes',
    data: {
      id: n.id,
      label: n.label,
      type: n.type,
      risk: n.risk ?? null,
      focus: n.is_focus ? 1 : 0,
      ring: ringOf.get(n.id) ?? '',
      size: nodeSize(n.risk),
    },
  }))

  const edges: ElementDefinition[] = graph.edges.map((e: GraphEdge) => ({
    group: 'edges',
    data: {
      id: e.id,
      source: e.source,
      target: e.target,
      type: e.type,
      label: e.label ?? '',
      collusion: e.collusion ? 1 : 0,
      ring: e.ring_id ?? '',
      weight: e.weight ?? 1,
    },
  }))

  return [...nodes, ...edges]
}

function buildStylesheet(): StylesheetStyle[] {
  const c = colourResolver()
  const text = c('--foreground', 'hsl(210 38% 95%)')
  const muted = c('--muted-foreground', 'hsl(215 18% 64%)')
  const card = c('--card', 'hsl(222 28% 10%)')
  const collusion = c('--severity-critical', 'hsl(348 83% 60%)')
  const ringHalo = c('--reason-graph', 'hsl(161 70% 50%)')
  const focusRing = c('--primary', 'hsl(199 89% 52%)')

  const sheet: StylesheetStyle[] = [
    {
      selector: 'node',
      style: {
        width: 'data(size)',
        height: 'data(size)',
        label: 'data(label)',
        'font-size': 9,
        'font-family': 'JetBrains Mono, ui-monospace, monospace',
        color: text,
        'text-valign': 'bottom',
        'text-margin-y': 4,
        'text-outline-width': 2,
        'text-outline-color': card,
        'border-width': 2,
        'border-color': card,
        'transition-property': 'opacity, border-width, border-color',
        'transition-duration': 180,
      },
    },
    // Type → colour + shape.
    ...(Object.keys(GRAPH_NODE_STYLE) as GraphNodeType[]).map((t): StylesheetStyle => ({
      selector: `node[type = "${t}"]`,
      style: {
        'background-color': c(GRAPH_NODE_STYLE[t].colorVar, GRAPH_NODE_STYLE[t].fallback),
        shape: GRAPH_NODE_STYLE[t].shape,
      },
    })),
    // Focus entity — bright primary ring, bigger label.
    {
      selector: 'node[focus = 1]',
      style: {
        'border-width': 4,
        'border-color': focusRing,
        'font-size': 11,
        'font-weight': 'bold',
        'z-index': 30,
      },
    },
    // Ring-cluster members — dashed reason-graph halo.
    {
      selector: 'node[ring != ""]',
      style: {
        'border-width': 3,
        'border-color': ringHalo,
        'border-style': 'dashed',
      },
    },
    // Base edge.
    {
      selector: 'edge',
      style: {
        width: 'mapData(weight, 1, 14, 1.5, 5)',
        'line-color': muted,
        'target-arrow-color': muted,
        'target-arrow-shape': 'triangle',
        'arrow-scale': 0.85,
        'curve-style': 'bezier',
        label: 'data(label)',
        'font-size': 8,
        'font-family': 'JetBrains Mono, ui-monospace, monospace',
        color: muted,
        'text-background-color': card,
        'text-background-opacity': 0.85,
        'text-background-padding': '2',
        'text-rotation': 'autorotate',
        opacity: 0.9,
        'transition-property': 'opacity, line-color, width',
        'transition-duration': 180,
      },
    },
    // Type → colour + line style.
    ...(Object.keys(GRAPH_EDGE_STYLE) as GraphEdgeType[]).map((t): StylesheetStyle => ({
      selector: `edge[type = "${t}"]`,
      style: {
        'line-color': c(GRAPH_EDGE_STYLE[t].colorVar, GRAPH_EDGE_STYLE[t].fallback),
        'target-arrow-color': c(GRAPH_EDGE_STYLE[t].colorVar, GRAPH_EDGE_STYLE[t].fallback),
        'line-style': GRAPH_EDGE_STYLE[t].style,
      },
    })),
    // Maker-checker collusion — thick, red, animated marching ants.
    {
      selector: 'edge[collusion = 1]',
      style: {
        'line-color': collusion,
        'target-arrow-color': collusion,
        'line-style': 'dashed',
        'line-dash-pattern': [8, 4],
        width: 4.5,
        color: collusion,
        'font-weight': 'bold',
        'z-index': 25,
        opacity: 1,
      },
    },
    // Selection.
    {
      selector: 'node:selected',
      style: { 'border-width': 5, 'border-color': focusRing, 'overlay-opacity': 0 },
    },
    // GNNExplainer emphasis / dimming (classes toggled imperatively).
    { selector: '.dimmed', style: { opacity: 0.12 } },
    {
      selector: 'node.evidence',
      style: { 'border-width': 4, 'border-color': c('--ai', 'hsl(271 76% 70%)'), 'z-index': 40 },
    },
    {
      selector: 'edge.evidence',
      style: {
        width: 5,
        'line-color': c('--ai', 'hsl(271 76% 70%)'),
        'target-arrow-color': c('--ai', 'hsl(271 76% 70%)'),
        opacity: 1,
        'z-index': 40,
      },
    },
  ]
  return sheet
}

/* ── Node detail (selection inspector — drill is optional; we inspect, never auto-navigate) ──── */
function NodeDetail({
  node,
  entityId,
  onClose,
}: {
  node: GraphNode
  entityId: string
  onClose: () => void
}) {
  const meta = GRAPH_NODE_STYLE[node.type]
  const Icon = meta.icon
  const tokenized = node.tokenized ?? isTokenizedPii(node.id)
  return (
    <Card className="absolute right-3 top-3 z-10 w-64 animate-fade-in shadow-lg">
      <CardHeader className="flex-row items-center gap-2 space-y-0 p-3">
        <span
          className="flex size-7 items-center justify-center rounded-md"
          style={{ backgroundColor: `${meta.fallback}26` }}
        >
          <Icon className="size-4" style={{ color: meta.fallback }} aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <CardTitle className="truncate text-xs">{graphTypeLabel(node.type)}</CardTitle>
          {node.is_focus ? (
            <span className="text-[0.7rem] font-medium text-primary">Focus entity</span>
          ) : null}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground focus-ring"
          aria-label="Close node detail"
        >
          <X className="size-3.5" />
        </button>
      </CardHeader>
      <CardContent className="space-y-2 p-3 pt-0 text-xs">
        <div className="flex items-center justify-between gap-2">
          <span className="text-muted-foreground">Identifier</span>
          {tokenized ? (
            <MaskedPII
              value={node.label}
              entityId={node.id === entityId || node.type === 'employee' ? node.id : undefined}
            />
          ) : (
            <span className="font-mono">{node.label}</span>
          )}
        </div>
        {typeof node.risk === 'number' ? (
          <div className="flex items-center justify-between gap-2">
            <span className="text-muted-foreground">Risk</span>
            <span className="inline-flex items-center gap-1.5">
              <span className="tabular-nums font-semibold">{Math.round(node.risk)}</span>
              <SeverityBadge severity={severityForScore(node.risk)} />
            </span>
          </div>
        ) : null}
        <p className="text-[0.7rem] text-muted-foreground">
          Inspect-only — graph analysis does not auto-navigate or change case state.
        </p>
      </CardContent>
    </Card>
  )
}

/* ── Main component ──────────────────────────────────────────────────────────────────────────── */
export function GraphView({ entityId }: { entityId: string }) {
  const query = useQuery<GraphResponse>({
    queryKey: queryKeys.entityGraph(entityId),
    queryFn: () => apiClient.getEntityGraph(entityId),
    enabled: Boolean(entityId),
  })

  return (
    <QueryBoundary
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => void query.refetch()}
      skeleton={
        <div className="h-[480px] w-full animate-pulse rounded-lg border border-border bg-muted/40" />
      }
    >
      {query.data ? <GraphCanvas graph={query.data} entityId={entityId} /> : null}
    </QueryBoundary>
  )
}

function GraphCanvas({ graph, entityId }: { graph: GraphResponse; entityId: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const cyRef = useRef<Core | null>(null)
  const [layout, setLayout] = useState<LayoutName>('cose')
  const [showEvidence, setShowEvidence] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const nodeById = useMemo(() => {
    const m = new Map<string, GraphNode>()
    for (const n of graph.nodes) m.set(n.id, n)
    return m
  }, [graph])

  const presentNodeTypes = useMemo(
    () => Array.from(new Set(graph.nodes.map((n) => n.type))) as GraphNodeType[],
    [graph],
  )
  const presentEdgeTypes = useMemo(
    () => Array.from(new Set(graph.edges.map((e) => e.type))) as GraphEdgeType[],
    [graph],
  )

  const rings = graph.rings ?? []
  const collusionCount = graph.edges.filter((e) => e.collusion).length
  const explainer = graph.explainer
  const hasEvidence = Boolean(explainer && (explainer.node_ids.length || explainer.edge_ids.length))

  const isEmpty = graph.nodes.length === 0

  /* Mount cytoscape once per graph; rebuild elements/stylesheet on data change. */
  useEffect(() => {
    if (isEmpty || !containerRef.current) return
    const cy = cytoscape({
      container: containerRef.current,
      elements: buildElements(graph),
      style: buildStylesheet(),
      layout: layoutOptions('cose'),
      wheelSensitivity: 0.25,
      minZoom: 0.25,
      maxZoom: 3,
    })
    cyRef.current = cy

    cy.on('tap', 'node', (evt: EventObject) => {
      setSelectedId((evt.target as NodeSingular).id())
    })
    cy.on('tap', (evt: EventObject) => {
      if (evt.target === cy) setSelectedId(null)
    })

    return () => {
      cy.destroy()
      cyRef.current = null
    }
    // Rebuild only when the underlying graph identity changes; layout/evidence handled separately.
  }, [graph, isEmpty])

  /* Re-run layout when the layout preset changes. */
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.layout(layoutOptions(layout)).run()
  }, [layout])

  /* GNNExplainer overlay — emphasise cited elements, dim the rest. */
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.batch(() => {
      cy.elements().removeClass('evidence dimmed')
      if (!showEvidence || !explainer) return
      const nodeSel = explainer.node_ids
      const edgeSel = explainer.edge_ids
      const evidence = cy.collection()
      for (const id of nodeSel) evidence.merge(cy.getElementById(id))
      for (const id of edgeSel) {
        const e = cy.getElementById(id)
        evidence.merge(e)
        evidence.merge(e.connectedNodes())
      }
      evidence.addClass('evidence')
      cy.elements().not(evidence).addClass('dimmed')
    })
  }, [showEvidence, explainer])

  /* Reflect external selection into cytoscape (and centre on the node). */
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.nodes().unselect()
    if (selectedId) {
      const n = cy.getElementById(selectedId)
      if (n.nonempty()) n.select()
    }
  }, [selectedId])

  const fit = () =>
    cyRef.current?.animate(
      { fit: { eles: cyRef.current.elements(), padding: 36 } },
      { duration: 250 },
    )
  const zoomBy = (factor: number) => {
    const cy = cyRef.current
    if (!cy) return
    cy.zoom({
      level: clamp(cy.zoom() * factor, cy.minZoom(), cy.maxZoom()),
      renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
    })
  }

  const selectedNode = selectedId ? (nodeById.get(selectedId) ?? null) : null

  return (
    <Card className="overflow-hidden">
      <CardHeader className="gap-3 border-b border-border p-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Network className="size-4 text-reason-graph" aria-hidden />
            <CardTitle>Link analysis</CardTitle>
            <Badge variant="outline" className="font-mono text-[0.7rem]">
              {graph.entity_id}
            </Badge>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {collusionCount > 0 ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="inline-flex items-center gap-1 rounded-full bg-severity-critical/15 px-2 py-0.5 text-xs font-medium text-severity-critical">
                    <ShieldAlert className="size-3.5" />
                    {collusionCount} collusion {collusionCount === 1 ? 'edge' : 'edges'}
                  </span>
                </TooltipTrigger>
                <TooltipContent>
                  Maker-checker pairs that recur in isolation — a segregation-of-duties red flag.
                </TooltipContent>
              </Tooltip>
            ) : null}
            {rings.map((r) => (
              <Tooltip key={r.ring_id}>
                <TooltipTrigger asChild>
                  <span className="inline-flex items-center gap-1 rounded-full bg-reason-graph/12 px-2 py-0.5 font-mono text-[0.7rem] text-reason-graph">
                    {r.ring_id}
                  </span>
                </TooltipTrigger>
                <TooltipContent>
                  {r.motif ? `${humanize(r.motif)} · ` : ''}
                  {r.member_ids.length} members
                </TooltipContent>
              </Tooltip>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="graph-layout" className="text-xs text-muted-foreground">
                Layout
              </Label>
              <Select value={layout} onValueChange={(v) => setLayout(v as LayoutName)}>
                <SelectTrigger id="graph-layout" className="h-8 w-40 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LAYOUTS.map((l) => (
                    <SelectItem key={l.value} value={l.value}>
                      {l.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Tooltip>
              <TooltipTrigger asChild>
                <label
                  className={cn(
                    'flex items-center gap-2 rounded-md border border-border px-2 py-1',
                    !hasEvidence && 'opacity-50',
                  )}
                >
                  <Sparkles className="size-3.5 text-ai" aria-hidden />
                  <span className="text-xs">GNNExplainer evidence</span>
                  <Switch
                    checked={showEvidence}
                    onCheckedChange={setShowEvidence}
                    disabled={!hasEvidence}
                    aria-label="Show GNNExplainer evidence"
                  />
                </label>
              </TooltipTrigger>
              <TooltipContent>
                {hasEvidence
                  ? `Emphasise the ${explainer?.model ?? 'GNNExplainer'} evidence subgraph; dim the rest.`
                  : 'No explainer evidence available for this subgraph.'}
              </TooltipContent>
            </Tooltip>
          </div>

          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="icon"
              className="size-8"
              onClick={() => zoomBy(1.25)}
              aria-label="Zoom in"
            >
              <Plus className="size-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="size-8"
              onClick={() => zoomBy(0.8)}
              aria-label="Zoom out"
            >
              <Minus className="size-4" />
            </Button>
            <Button variant="outline" size="sm" className="h-8 gap-1.5" onClick={fit}>
              <Maximize2 className="size-3.5" /> Fit
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-0">
        {isEmpty ? (
          <EmptyState
            icon={Network}
            title="No linked entities"
            description="This entity has no graph relationships in the current window. Connections appear here as shared devices, beneficiaries, accounts or maker-checker pairs surface."
            className="m-3"
          />
        ) : (
          <div className="relative">
            <div
              ref={containerRef}
              className="h-[480px] w-full bg-background"
              role="application"
              aria-label={`Link-analysis graph for ${graph.entity_id}: ${graph.nodes.length} nodes, ${graph.edges.length} edges`}
            />
            {selectedNode ? (
              <NodeDetail
                node={selectedNode}
                entityId={entityId}
                onClose={() => setSelectedId(null)}
              />
            ) : (
              <div className="pointer-events-none absolute left-3 top-3 z-10 flex items-center gap-1 rounded-md bg-card/80 px-2 py-1 text-[0.7rem] text-muted-foreground backdrop-blur">
                <Crosshair className="size-3" /> Click a node to inspect · drag to pan · scroll to
                zoom
              </div>
            )}
          </div>
        )}
      </CardContent>

      {!isEmpty ? (
        <>
          <Separator />
          <div className="grid gap-4 p-3 sm:grid-cols-[1fr_auto] sm:items-start">
            <GraphLegend nodeTypes={presentNodeTypes} edgeTypes={presentEdgeTypes} />
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:w-44">
              <dt className="text-muted-foreground">Nodes</dt>
              <dd className="text-right tabular-nums">{formatNumber(graph.nodes.length)}</dd>
              <dt className="text-muted-foreground">Edges</dt>
              <dd className="text-right tabular-nums">{formatNumber(graph.edges.length)}</dd>
              <dt className="text-muted-foreground">Rings</dt>
              <dd className="text-right tabular-nums">{formatNumber(rings.length)}</dd>
              {(() => {
                const txn = graph.edges.reduce((sum, e) => sum + (e.amount_inr ?? 0), 0)
                return txn > 0 ? (
                  <>
                    <dt className="text-muted-foreground">Flow</dt>
                    <dd className="text-right tabular-nums">{formatINR(txn)}</dd>
                  </>
                ) : null
              })()}
            </dl>
          </div>
        </>
      ) : null}
    </Card>
  )
}
