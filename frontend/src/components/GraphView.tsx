/**
 * GraphView — interactive entity link-analysis subgraph (FRONTEND-9; blueprint Part 11 l.390 +
 * Part 24.4 screen 4). Renders `GET /entities/{id}/graph` (GraphResponse) on a Cytoscape.js canvas
 * (the imperative mount lives in the reusable <GraphCanvas/> — this view owns the chrome + data):
 *
 *   • nodes typed employee/customer/beneficiary/account/device/ip/phone/address/system — coloured +
 *     shaped by type (see GRAPH_NODE_STYLE), sized by risk, the `is_focus` entity ringed distinctly,
 *     and any risk≥70 node gets a glowing risk-ring (GraphCanvas RISK_RING_THRESHOLD);
 *   • edges typed maker_checker, shared_device/ip/phone/address, beneficiary, circular_flow,
 *     mule and transaction;
 *   • HIGHLIGHTS: maker-checker collusion edges (collusion=true) are thick/red/animated, and
 *     ring_id clusters (rings[]) get a matched dashed halo;
 *   • OVERLAY: GNNExplainer evidence (explainer.node_ids/edge_ids) — when toggled on the cited
 *     elements brighten and everything else dims;
 *   • DEPTH EXPAND: a 1/2/3-hop depth Select re-fetches a wider subgraph from the API;
 *   • pan/zoom, layout selection (cose/breadthfirst/concentric/circle), a Fit button, and a node
 *     click that *selects + inspects* (popover) — never auto-navigates / never mutates.
 *
 * Golden rules respected: read-only (no block/disposition here), PII rendered tokenized via
 * <MaskedPII> in the node-detail popover, money in INR, loading/error via <QueryBoundary>, empty via
 * <EmptyState>.
 */
import { useMemo, useRef, useState } from 'react'
import {
  Crosshair,
  Layers,
  Maximize2,
  Minus,
  Network,
  Plus,
  ShieldAlert,
  Sparkles,
  X,
} from 'lucide-react'
import { cn } from '@/lib/cn'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { formatINR, formatNumber, humanize, isTokenizedPii, severityForScore } from '@/lib/format'
import type { GraphNode, GraphNodeType, GraphEdgeType, GraphResponse } from '@/lib/types'
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
import { GRAPH_NODE_STYLE, GraphLegend, graphTypeLabel } from '@/components/GraphLegend'
import {
  GraphCanvas,
  LAYOUTS,
  type GraphCanvasHandle,
  type LayoutName,
} from '@/components/graph/GraphCanvas'

/** Hop depth. We AUTO-SCOPE to the smallest neighborhood that reveals a maker-checker ring (2 hops):
 *  1 hop shows only direct links (misses the collusion partner's partner); 3 hops is usually noise.
 *  The analyst can still widen to 3 for distant links, but no longer has to pick a depth up front. */
type GraphDepth = 1 | 2 | 3
const INITIAL_DEPTH: GraphDepth = 2

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
  const [depth, setDepth] = useState<GraphDepth>(INITIAL_DEPTH)
  const query = useQuery<GraphResponse>({
    queryKey: queryKeys.entityGraph(entityId, depth),
    queryFn: () => apiClient.getEntityGraph(entityId, { depth }),
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
      {query.data ? (
        <GraphViewBody
          graph={query.data}
          entityId={entityId}
          depth={depth}
          onDepthChange={setDepth}
          isFetching={query.isFetching}
        />
      ) : null}
    </QueryBoundary>
  )
}

function GraphViewBody({
  graph,
  entityId,
  depth,
  onDepthChange,
  isFetching,
}: {
  graph: GraphResponse
  entityId: string
  depth: GraphDepth
  onDepthChange: (d: GraphDepth) => void
  isFetching: boolean
}) {
  const canvasRef = useRef<GraphCanvasHandle>(null)
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

            <div className="flex items-center gap-1.5">
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Layers className="size-3.5" aria-hidden /> Scope
              </span>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1.5 text-xs"
                    onClick={() =>
                      onDepthChange(depth >= 3 ? INITIAL_DEPTH : ((depth + 1) as GraphDepth))
                    }
                  >
                    {depth <= INITIAL_DEPTH ? 'Ring neighborhood' : 'Wider network'}
                    <span className="font-mono opacity-60">{depth}-hop</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  Auto-scoped to the smallest ring-revealing neighborhood ({INITIAL_DEPTH} hops) —
                  no need to pick a depth. Click to{' '}
                  {depth >= 3 ? 'return to the ring view' : 'widen to more distant links'}.
                </TooltipContent>
              </Tooltip>
              {isFetching ? (
                <span className="text-[0.7rem] text-muted-foreground" aria-live="polite">
                  expanding…
                </span>
              ) : null}
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
              onClick={() => canvasRef.current?.zoomBy(1.25)}
              aria-label="Zoom in"
            >
              <Plus className="size-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="size-8"
              onClick={() => canvasRef.current?.zoomBy(0.8)}
              aria-label="Zoom out"
            >
              <Minus className="size-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-1.5"
              onClick={() => canvasRef.current?.fit()}
            >
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
            <GraphCanvas
              handleRef={canvasRef}
              graph={graph}
              layout={layout}
              highlightId={selectedId}
              evidenceNodeIds={showEvidence ? explainer?.node_ids : undefined}
              evidenceEdgeIds={showEvidence ? explainer?.edge_ids : undefined}
              onSelect={setSelectedId}
              className="h-[480px] w-full bg-background"
              ariaLabel={`Link-analysis graph for ${graph.entity_id}: ${graph.nodes.length} nodes, ${graph.edges.length} edges`}
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
