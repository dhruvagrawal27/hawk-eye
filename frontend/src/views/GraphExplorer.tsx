/**
 * GraphExplorer — the global link-analysis workbench (FRONTEND; blueprint Part 11 graph console).
 * Where GraphView renders one entity's neighbourhood, this screen renders the *whole population* as a
 * risk heat map: every employee, the systems they touch, and the collusion edges between the hottest
 * actors, painted on the shared <GraphCanvas/> in dense `overview` mode. The left panel drives it:
 *
 *   • SEARCH — filter node ids/labels; selecting a hit centres the canvas on it and flashes a pulse;
 *   • MIN-RISK slider — raise the floor to thin the dust cloud down to the hottest actors;
 *   • SHOW SYSTEMS switch — hide/show the shared-system backbone;
 *   • FIND-PATH mode — pick node A then node B; an A* search highlights the connecting path and dims
 *     the rest, exposing how two actors are linked (shared systems, maker-checker collusion, …);
 *   • a live stats panel + the shared GraphLegend.
 *
 * The population is synthesised deterministically on the client (`buildOverviewGraph`) so the surface
 * is dense and instant regardless of backend data volume; swap to `apiClient.getGraphOverview` later.
 * Read-only — like every graph surface it inspects, never mutates or auto-navigates.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  GitBranch,
  Network,
  Route,
  Search,
  Server,
  ShieldAlert,
  Sparkles,
  Users,
  X,
  ZoomIn,
  ZoomOut,
} from 'lucide-react'
import { formatNumber } from '@/lib/format'
import { riskColor } from '@/lib/risk'
import { buildOverviewGraph, type OverviewGraph } from '@/lib/overviewGraph'
import type { GraphNode, GraphNodeType, GraphEdgeType } from '@/lib/types'
import { PageHeader } from '@/components/PageHeader'
import { Surface } from '@/components/ui/surface'
import { Eyebrow } from '@/components/ui/eyebrow'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'
import { EmptyState } from '@/components/ui/empty-state'
import { toast } from '@/components/ui/toaster'
import {
  GraphCanvas,
  RISK_RING_THRESHOLD,
  type GraphCanvasHandle,
} from '@/components/graph/GraphCanvas'
import { GraphLegend, graphTypeLabel } from '@/components/GraphLegend'

export function GraphExplorer() {
  // Whole-population graph, generated once (deterministic → stable galaxy across renders).
  const graph = useMemo(() => buildOverviewGraph(), [])
  const { population } = graph

  // A live "critical alert" ping to match the SOC feel of the console — one-shot, non-blocking.
  useEffect(() => {
    const t = window.setTimeout(() => {
      toast.error('New CRITICAL alert', {
        description: 'Graph counterparty collusion ring — maker-checker breach linking 4 actors.',
      })
    }, 1400)
    return () => window.clearTimeout(t)
  }, [])

  return (
    <div className="space-y-4">
      <PageHeader
        icon={<Network className="size-5" />}
        title="Graph explorer"
        description={
          <span className="font-mono text-xs text-muted-foreground tabular-nums">
            {formatNumber(population.employees)} employees · {formatNumber(population.systems)}{' '}
            systems · {formatNumber(population.edges)} edges
          </span>
        }
        actions={
          <Badge variant="outline" className="gap-1.5">
            <Sparkles className="size-3.5" /> Link analysis
          </Badge>
        }
      />
      <ExplorerBody graph={graph} />
    </div>
  )
}

type PathState = { a: string | null; b: string | null }

function ExplorerBody({ graph }: { graph: OverviewGraph }) {
  const canvasRef = useRef<GraphCanvasHandle>(null)
  const [minScore, setMinScore] = useState(0)
  const [showSystems, setShowSystems] = useState(true)
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [pathMode, setPathMode] = useState(false)
  const [path, setPath] = useState<PathState>({ a: null, b: null })
  const [pathNodeIds, setPathNodeIds] = useState<string[]>([])
  const [pathEdgeIds, setPathEdgeIds] = useState<string[]>([])
  const [pathError, setPathError] = useState<string | null>(null)

  // Apply the min-risk floor + "show systems" filter to the rendered graph (re-mounts the canvas on
  // identity change; positions are precomputed so the rebuild is cheap even at population scale).
  const view = useMemo(() => {
    let nodes = graph.nodes
    if (minScore > 0) {
      const keptEmp = new Set(
        nodes.filter((n) => n.type === 'employee' && (n.risk ?? 0) >= minScore).map((n) => n.id),
      )
      const keep = new Set(keptEmp)
      for (const e of graph.edges) if (keptEmp.has(e.source)) keep.add(e.target)
      nodes = nodes.filter((n) => keep.has(n.id))
    }
    if (!showSystems) nodes = nodes.filter((n) => n.type !== 'system')
    const ids = new Set(nodes.map((n) => n.id))
    const edges = graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target))
    return { ...graph, nodes, edges }
  }, [graph, minScore, showSystems])

  const nodeById = useMemo(() => {
    const m = new Map<string, GraphNode>()
    for (const n of view.nodes) m.set(n.id, n)
    return m
  }, [view])

  const presentNodeTypes = useMemo(
    () => Array.from(new Set(view.nodes.map((n) => n.type))) as GraphNodeType[],
    [view],
  )
  const presentEdgeTypes = useMemo(
    () => Array.from(new Set(view.edges.map((e) => e.type))) as GraphEdgeType[],
    [view],
  )

  // Search results — match id or label, case-insensitive.
  const matches = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return []
    return view.nodes
      .filter((n) => n.id.toLowerCase().includes(q) || n.label.toLowerCase().includes(q))
      .slice(0, 8)
  }, [search, view])

  const employeeCount = view.nodes.filter((n) => n.type === 'employee').length
  const systemCount = view.nodes.filter((n) => n.type === 'system').length
  const hotCount = view.nodes.filter(
    (n) => typeof n.risk === 'number' && n.risk >= RISK_RING_THRESHOLD,
  ).length
  const collusionCount = view.edges.filter((e) => e.collusion).length

  function clearPath() {
    setPath({ a: null, b: null })
    setPathNodeIds([])
    setPathEdgeIds([])
    setPathError(null)
  }

  // Centre + flash a node (search "go to") and select it.
  function goTo(id: string) {
    setSelectedId(id)
    canvasRef.current?.flash(id)
  }

  // Run A* between the two picked endpoints and highlight the connecting path.
  function runPath(a: string, b: string) {
    const cy = canvasRef.current?.cy()
    if (!cy) return
    const result = cy.elements().aStar({
      root: cy.getElementById(a),
      goal: cy.getElementById(b),
      directed: false,
    })
    if (!result.found || result.path.length === 0) {
      setPathNodeIds([])
      setPathEdgeIds([])
      setPathError('No path connects these two nodes in the current view.')
      return
    }
    setPathError(null)
    setPathNodeIds(result.path.nodes().map((n) => n.id()))
    setPathEdgeIds(result.path.edges().map((e) => e.id()))
    // Frame the path itself — fitting the whole population would zoom out to the full galaxy and
    // bury the highlighted route among thousands of dimmed nodes.
    cy.animate({ fit: { eles: result.path, padding: 140 } }, { duration: 450 })
  }

  // Node selection from the canvas: in find-path mode, fill A then B; otherwise just inspect.
  function handleSelect(id: string | null) {
    if (!pathMode || !id) {
      setSelectedId(id)
      return
    }
    setSelectedId(id)
    setPath((prev) => {
      if (!prev.a || (prev.a && prev.b)) {
        // Start a fresh pick.
        setPathNodeIds([])
        setPathEdgeIds([])
        setPathError(null)
        return { a: id, b: null }
      }
      if (id === prev.a) return prev
      const next = { a: prev.a, b: id }
      runPath(next.a, id)
      return next
    })
  }

  // The animated force layout fits itself on load and after each filter, so no manual camera nudging
  // is needed — nodes fly in, settle, and stay draggable.
  const pathEndpointIds = useMemo(
    () => [path.a, path.b].filter((x): x is string => Boolean(x)),
    [path.a, path.b],
  )

  const selectedNode = selectedId ? (nodeById.get(selectedId) ?? null) : null

  return (
    <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
      {/* ── Left control panel ─────────────────────────────────────────────── */}
      <Surface tone="operational" pad="md" className="space-y-5 self-start">
        {/* Search */}
        <section className="space-y-2">
          <Eyebrow className="flex items-center gap-1.5">
            <Search className="size-3.5" /> Find node
          </Eyebrow>
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search id or label…"
              className="h-8 pl-8 text-xs"
              aria-label="Search graph nodes"
            />
            {search ? (
              <button
                type="button"
                onClick={() => setSearch('')}
                aria-label="Clear search"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground focus-ring"
              >
                <X className="size-3.5" />
              </button>
            ) : null}
          </div>
          {matches.length > 0 ? (
            <ul className="space-y-1">
              {matches.map((n) => (
                <li key={n.id}>
                  <button
                    type="button"
                    onClick={() => goTo(n.id)}
                    className="flex w-full items-center justify-between gap-2 rounded-md border border-border px-2 py-1 text-left text-xs hover:bg-muted/40 focus-ring"
                  >
                    <span className="truncate font-mono">{n.label}</span>
                    <span className="shrink-0 text-2xs text-muted-foreground">
                      {graphTypeLabel(n.type)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : search.trim() ? (
            <p className="text-2xs text-muted-foreground">No matching nodes.</p>
          ) : null}
        </section>

        <Separator />

        {/* Min-risk slider */}
        <section className="space-y-2">
          <div className="flex items-center justify-between">
            <Eyebrow>Min risk</Eyebrow>
            <span
              className="font-mono text-xs font-semibold tabular-nums"
              style={{ color: riskColor(minScore) }}
            >
              {minScore}
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            aria-label="Minimum risk score"
            className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-input accent-[hsl(var(--primary))]"
          />
          <p className="text-2xs text-muted-foreground">
            Raise the floor to thin the population down to the hottest actors.
          </p>
        </section>

        <Separator />

        {/* Show systems */}
        <section className="flex items-center justify-between gap-2">
          <Label htmlFor="show-systems" className="flex items-center gap-1.5 text-xs">
            <Server className="size-3.5 text-ai" aria-hidden /> Show systems
          </Label>
          <Switch
            id="show-systems"
            checked={showSystems}
            onCheckedChange={setShowSystems}
            aria-label="Show shared-system backbone"
          />
        </section>

        <Separator />

        {/* Find-path mode */}
        <section className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <Eyebrow className="flex items-center gap-1.5">
              <Route className="size-3.5" /> Find path
            </Eyebrow>
            <Switch
              checked={pathMode}
              onCheckedChange={(v) => {
                setPathMode(v)
                clearPath()
              }}
              aria-label="Toggle find-path mode"
            />
          </div>
          {pathMode ? (
            <div className="space-y-1.5 text-xs">
              <PathSlot label="A" id={path.a} hint="Pick start node" />
              <PathSlot label="B" id={path.b} hint="Pick end node" />
              {pathError ? (
                <p className="flex items-center gap-1 text-2xs text-severity-high">
                  <ShieldAlert className="size-3" /> {pathError}
                </p>
              ) : pathNodeIds.length > 0 ? (
                <p className="flex items-center gap-1 text-2xs text-primary">
                  <GitBranch className="size-3" /> {pathNodeIds.length} nodes · {pathEdgeIds.length}{' '}
                  edges on path
                </p>
              ) : (
                <p className="text-2xs text-muted-foreground">
                  Click two nodes on the canvas to trace the shortest link between them.
                </p>
              )}
              {(path.a || pathNodeIds.length > 0) && (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 w-full gap-1.5"
                  onClick={clearPath}
                >
                  <X className="size-3.5" /> Reset path
                </Button>
              )}
            </div>
          ) : (
            <p className="text-2xs text-muted-foreground">
              Trace how two actors connect through shared systems or collusion edges.
            </p>
          )}
        </section>

        <Separator />

        {/* Stats */}
        <section className="space-y-2">
          <Eyebrow>Stats</Eyebrow>
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
            <dt className="text-muted-foreground">Employees</dt>
            <dd className="text-right tabular-nums">{formatNumber(employeeCount)}</dd>
            <dt className="text-muted-foreground">Systems</dt>
            <dd className="text-right tabular-nums">{formatNumber(systemCount)}</dd>
            <dt className="text-muted-foreground">Edges</dt>
            <dd className="text-right tabular-nums">{formatNumber(view.edges.length)}</dd>
            <dt className="text-muted-foreground">High-risk</dt>
            <dd className="text-right tabular-nums text-risk-high">{formatNumber(hotCount)}</dd>
            <dt className="text-muted-foreground">Collusion</dt>
            <dd className="text-right tabular-nums text-severity-critical">
              {formatNumber(collusionCount)}
            </dd>
          </dl>
        </section>
      </Surface>

      {/* ── Canvas + legend ────────────────────────────────────────────────── */}
      <div className="space-y-4">
        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border p-3">
            <div className="flex items-center gap-2">
              <Network className="size-4 text-reason-graph" aria-hidden />
              <span className="text-sm font-semibold">Top-risk network</span>
              <Badge variant="secondary" className="gap-1 text-2xs">
                <Users className="size-3" /> {formatNumber(view.nodes.length)} nodes
              </Badge>
              {pathMode ? (
                <Badge variant="secondary" className="gap-1 text-2xs">
                  <Route className="size-3" /> Find-path
                </Badge>
              ) : null}
            </div>
            <div className="flex items-center gap-1.5">
              <Button
                variant="outline"
                size="icon"
                className="size-8"
                aria-label="Zoom in"
                onClick={() => canvasRef.current?.zoomBy(1.3)}
              >
                <ZoomIn className="size-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="size-8"
                aria-label="Zoom out"
                onClick={() => canvasRef.current?.zoomBy(1 / 1.3)}
              >
                <ZoomOut className="size-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-8"
                onClick={() => canvasRef.current?.fit()}
              >
                Fit
              </Button>
            </div>
          </div>

          {view.nodes.length === 0 ? (
            <EmptyState
              icon={Network}
              title="No entities at this risk floor"
              description="Lower the minimum-risk slider to bring more of the population back into view."
              className="m-3"
            />
          ) : (
            <div className="relative">
              <GraphCanvas
                handleRef={canvasRef}
                graph={view}
                layout="cose"
                overview
                highlightId={selectedId}
                pathNodeIds={pathNodeIds}
                pathEdgeIds={pathEdgeIds}
                pathEndpointIds={pathEndpointIds}
                onSelect={handleSelect}
                className="h-[620px] w-full bg-background"
                ariaLabel={`Top-risk network: ${view.nodes.length} nodes, ${view.edges.length} edges`}
              />
              {selectedNode ? (
                <SelectedChip node={selectedNode} onClose={() => setSelectedId(null)} />
              ) : null}
            </div>
          )}
        </Card>

        <Card className="p-3">
          <GraphLegend nodeTypes={presentNodeTypes} edgeTypes={presentEdgeTypes} />
        </Card>
      </div>
    </div>
  )
}

function PathSlot({ label, id, hint }: { label: string; id: string | null; hint: string }) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-border px-2 py-1">
      <Badge variant={id ? 'secondary' : 'outline'} className="size-5 justify-center p-0 text-2xs">
        {label}
      </Badge>
      {id ? (
        <span className="truncate font-mono text-xs">{id}</span>
      ) : (
        <span className="text-2xs text-muted-foreground">{hint}</span>
      )}
    </div>
  )
}

function SelectedChip({ node, onClose }: { node: GraphNode; onClose: () => void }) {
  return (
    <div className="absolute right-3 top-3 z-10 flex items-center gap-2 rounded-md border border-border bg-card/90 px-2.5 py-1.5 text-xs shadow-lg backdrop-blur">
      <span
        className="size-2 rounded-full"
        style={{ backgroundColor: riskColor(typeof node.risk === 'number' ? node.risk : null) }}
        aria-hidden
      />
      <span className="font-mono">{node.label}</span>
      <span className="text-2xs text-muted-foreground">{graphTypeLabel(node.type)}</span>
      {typeof node.risk === 'number' ? (
        <span className="tabular-nums font-semibold">{Math.round(node.risk)}</span>
      ) : null}
      <button
        type="button"
        onClick={onClose}
        aria-label="Clear selection"
        className="text-muted-foreground hover:text-foreground focus-ring"
      >
        <X className="size-3.5" />
      </button>
    </div>
  )
}
