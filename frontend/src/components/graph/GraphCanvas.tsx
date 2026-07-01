/**
 * GraphCanvas — the reusable Cytoscape.js mount extracted from GraphView (FRONTEND-9). Owns the
 * shared element/stylesheet builders, the layout presets and the imperative cytoscape lifecycle so
 * both the entity link-analysis view (GraphView) and the global Graph Explorer (GraphExplorer) paint
 * from one source of truth. The canvas is *presentational + imperative*: it renders nodes/edges, runs
 * layouts, reflects selection/highlight/path props, and emits selection — it never fetches or mutates.
 *
 * Shared encodings:
 *   • nodes coloured + shaped by type (GRAPH_NODE_STYLE), sized by risk, the focus entity ringed;
 *   • RISK RING — any node with risk ≥ RISK_RING_THRESHOLD (from lib/risk) gets a glowing underlay +
 *     severity-coloured border so the riskiest entities pop without reading the size;
 *   • maker-checker collusion edges thick/red/animated; ring_id clusters get a dashed halo;
 *   • classes toggled imperatively for evidence emphasis (`.evidence`/`.dimmed`), path highlighting
 *     (`.path`/`.dimmed`) and a transient `.flash` pulse used by the Explorer search.
 *
 * Cytoscape requires a unique edge id — we synthesize `${source}__${target}__${i}` when absent.
 */
import { useEffect, useImperativeHandle, useRef, type Ref } from 'react'
import cytoscape, {
  type Core,
  type ElementDefinition,
  type EventObject,
  type LayoutOptions,
  type NodeSingular,
  type StylesheetStyle,
} from 'cytoscape'
import { clamp } from '@/lib/format'
import { riskLevelFromScore } from '@/lib/risk'
import type { GraphEdge, GraphEdgeType, GraphNode, GraphNodeType, GraphResponse } from '@/lib/types'
import { GRAPH_EDGE_STYLE, GRAPH_NODE_STYLE } from '@/components/GraphLegend'

/* ── Layout presets (cytoscape built-ins; no external layout plugins) ────────────────────────── */
// `preset` reads precomputed node positions (the dense Explorer overview) — no iterative solver, so
// it paints thousands of nodes instantly where cose would hang.
export type LayoutName = 'preset' | 'cose' | 'breadthfirst' | 'concentric' | 'circle'
export const LAYOUTS: { value: LayoutName; label: string }[] = [
  { value: 'cose', label: 'Force-directed' },
  { value: 'breadthfirst', label: 'Hierarchy' },
  { value: 'concentric', label: 'Concentric' },
  { value: 'circle', label: 'Circle' },
]

/** Risk score (0–100) at or above which a node earns the glowing risk ring (lib/risk `high` band). */
export const RISK_RING_THRESHOLD = 70

export function layoutOptions(name: LayoutName): LayoutOptions {
  const base = { name, fit: true, padding: 36, animate: false as const }
  if (name === 'preset') {
    return { ...base, name: 'preset', padding: 48 } as LayoutOptions
  }
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
  // Cytoscape ships its OWN colour parser, which rejects the space-separated `hsl(H S% L%)` form that
  // Tailwind CSS variables use — and silently drops the property, leaving every node/edge the default
  // grey. Normalise to a form it accepts: a bare "H S% L%" triplet (or space-`hsl(...)`) becomes comma
  // syntax `hsl(H, S%, L%)`; hex/rgb/already-comma values pass through untouched.
  const toCss = (value: string): string => {
    const inner = value
      .trim()
      .replace(/^hsl\(|\)$/gi, '')
      .trim()
    if (/^[\d.]+\s+[\d.]+%\s+[\d.]+%/.test(inner)) {
      return `hsl(${inner.split('/')[0].trim().split(/\s+/).join(', ')})`
    }
    return value.trim()
  }
  return (cssVar: string, fallback: string): string => {
    const raw = styles?.getPropertyValue(cssVar)?.trim()
    return toCss(raw ? `hsl(${raw})` : fallback)
  }
}

/** Node diameter from risk score (undefined risk → mid). */
function nodeSize(risk?: number): number {
  const r = typeof risk === 'number' ? clamp(risk, 0, 100) : 45
  return Math.round(34 + (r / 100) * 34) // 34–68px
}

/**
 * Dense-overview node diameter — much smaller than the entity view so a few-thousand-node hairball
 * stays legible: employees scale 9→39px by risk, systems sit at 5→16px so the population reads as a
 * cool dust cloud with the hot actors punching through.
 */
function overviewNodeSize(type: GraphNode['type'], risk?: number): number {
  const r = typeof risk === 'number' ? clamp(risk, 0, 100) : 0
  return type === 'employee' ? Math.round(9 + (r / 100) * 30) : Math.round(5 + (r / 100) * 11)
}

/* ── Build cytoscape elements + stylesheet from the API response ─────────────────────────────── */
export function buildElements(
  graph: GraphResponse,
  opts: { overview?: boolean } = {},
): ElementDefinition[] {
  const ringOf = new Map<string, string>()
  for (const ring of graph.rings ?? []) {
    for (const id of ring.member_ids) ringOf.set(id, ring.ring_id)
  }

  const nodes: ElementDefinition[] = graph.nodes.map((n: GraphNode) => {
    const el: ElementDefinition = {
      group: 'nodes',
      data: {
        id: n.id,
        label: n.label,
        type: n.type,
        risk: n.risk ?? null,
        // Drives the RISK-RING selector (booleans aren't selectable in cytoscape, so use 0/1).
        hot: typeof n.risk === 'number' && n.risk >= RISK_RING_THRESHOLD ? 1 : 0,
        focus: n.is_focus ? 1 : 0,
        ring: ringOf.get(n.id) ?? '',
        size: opts.overview ? overviewNodeSize(n.type, n.risk) : nodeSize(n.risk),
      },
    }
    // Precomputed coordinates → the fast `preset` layout renders the whole population at once.
    if (typeof n.x === 'number' && typeof n.y === 'number') el.position = { x: n.x, y: n.y }
    return el
  })

  const edges: ElementDefinition[] = graph.edges.map((e: GraphEdge, i) => ({
    group: 'edges',
    data: {
      // Cytoscape REQUIRES a unique edge id — synthesize one when the payload omits it.
      id: e.id || `${e.source}__${e.target}__${i}`,
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

export function buildStylesheet(opts: { overview?: boolean } = {}): StylesheetStyle[] {
  const c = colourResolver()
  const text = c('--foreground', 'hsl(210 38% 95%)')
  const muted = c('--muted-foreground', 'hsl(215 18% 64%)')
  const card = c('--card', 'hsl(222 28% 10%)')
  const collusion = c('--severity-critical', 'hsl(348 83% 60%)')
  const ringHalo = c('--reason-graph', 'hsl(161 70% 50%)')
  const focusRing = c('--primary', 'hsl(199 89% 52%)')
  // RISK-RING glow — colour the high-risk band straight from the severity tokens (no hardcoded hex).
  const riskHigh = c(`--severity-${riskLevelFromScore(RISK_RING_THRESHOLD)}`, 'hsl(25 95% 57%)')
  const riskCritical = c('--severity-critical', 'hsl(348 83% 60%)')
  const riskMedium = c('--severity-medium', 'hsl(43 96% 58%)')

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
    // RISK RING — high-risk nodes glow (underlay halo) and gain a severity-coloured border so the
    // worst actors read instantly. critical (≥85) intensifies to the critical token below.
    {
      selector: 'node[hot = 1]',
      style: {
        'border-width': 3,
        'border-color': riskHigh,
        'underlay-color': riskHigh,
        'underlay-opacity': 0.35,
        'underlay-padding': 8,
        'underlay-shape': 'ellipse',
        'z-index': 20,
      },
    },
    {
      selector: 'node[hot = 1][risk >= 85]',
      style: {
        'border-color': riskCritical,
        'underlay-color': riskCritical,
        'underlay-opacity': 0.4,
      },
    },
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
    // Find-path highlight — the shortest path between A and B glows primary, the rest dims.
    {
      selector: 'node.path',
      style: { 'border-width': 4, 'border-color': focusRing, 'z-index': 45 },
    },
    {
      selector: 'edge.path',
      style: {
        width: 5,
        'line-color': focusRing,
        'target-arrow-color': focusRing,
        opacity: 1,
        'z-index': 45,
      },
    },
    // Transient search flash (toggled then removed) — a bright critical pulse to draw the eye.
    {
      selector: 'node.flash',
      style: {
        'border-width': 8,
        'border-color': riskCritical,
        'underlay-color': riskCritical,
        'underlay-opacity': 0.6,
        'underlay-padding': 14,
        'z-index': 60,
      },
    },
  ]

  // ── Dense-overview variant — recolour the population as a RISK HEAT MAP and swap to cheap
  //    straight (haystack) edges + zoom-gated labels so a few-thousand-node graph stays smooth.
  //    Appended last so these win over the per-type colour rules above (equal specificity, later).
  if (opts.overview) {
    const cool = c('--muted', 'hsl(215 20% 22%)')
    const coolNode = 'hsl(215, 22%, 34%)' // slate dust for the quiet majority (cytoscape comma syntax)
    sheet.push(
      {
        selector: 'node',
        style: {
          'border-width': 1,
          'border-color': card,
          'font-size': 7,
          'text-margin-y': 2,
          'text-outline-width': 1.5,
          'min-zoomed-font-size': 8, // hide labels when zoomed out → fast + uncluttered
        },
      },
      { selector: 'node[type = "system"]', style: { 'background-color': coolNode } },
      { selector: 'node[type = "employee"]', style: { 'background-color': coolNode } },
      // Risk heat ramp — ascending so the hottest band wins.
      { selector: 'node[risk >= 40]', style: { 'background-color': riskMedium } },
      { selector: 'node[risk >= 55]', style: { 'background-color': riskHigh } },
      { selector: 'node[risk >= 70]', style: { 'background-color': riskHigh } },
      { selector: 'node[risk >= 85]', style: { 'background-color': riskCritical } },
      // `[weight >= 0]` matches every edge but outranks the per-type colour rules (same specificity,
      // declared later) so the whole mesh reads as one faint uniform hairball. Class overlays
      // (.path/.dimmed) are still higher specificity and win.
      {
        selector: 'edge[weight >= 0]',
        style: {
          'curve-style': 'haystack',
          'haystack-radius': 0,
          width: 'mapData(weight, 1, 2, 0.5, 1.4)',
          'line-color': cool,
          'target-arrow-shape': 'none',
          label: '',
          opacity: 0.4,
        },
      },
      // Collusion stays loud even in the dust cloud.
      {
        selector: 'edge[collusion = 1]',
        style: { 'line-color': collusion, width: 1.6, opacity: 0.9 },
      },
    )
  }

  return sheet
}

/* ── Imperative handle so containers can centre/flash without re-mounting cytoscape ──────────── */
export interface GraphCanvasHandle {
  /** Underlying cytoscape core (find-path, fit, custom queries). Null until mounted. */
  cy: () => Core | null
  /** Re-fit the whole graph into view. */
  fit: () => void
  /** Zoom by a factor around the viewport centre. */
  zoomBy: (factor: number) => void
  /** Centre on a node and play a brief flash pulse (Explorer search "go to"). */
  flash: (id: string) => void
}

export interface GraphCanvasProps {
  graph: GraphResponse
  layout: LayoutName
  /** Reflected into cytoscape selection + centred. */
  highlightId?: string | null
  /** When set, these nodes/edges are emphasised as the find-path result and the rest dimmed. */
  pathNodeIds?: string[]
  pathEdgeIds?: string[]
  /** GNNExplainer-style evidence emphasis (node + edge ids). */
  evidenceNodeIds?: string[]
  evidenceEdgeIds?: string[]
  /** Dense-population mode: risk heat-map colours, cheap straight edges + large-graph perf flags. */
  overview?: boolean
  onSelect?: (id: string | null) => void
  className?: string
  ariaLabel?: string
  handleRef?: Ref<GraphCanvasHandle>
}

export function GraphCanvas({
  graph,
  layout,
  highlightId,
  pathNodeIds,
  pathEdgeIds,
  evidenceNodeIds,
  evidenceEdgeIds,
  overview = false,
  onSelect,
  className,
  ariaLabel,
  handleRef,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const cyRef = useRef<Core | null>(null)
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect

  /* Mount cytoscape once per graph; rebuild elements/stylesheet on data change. */
  useEffect(() => {
    if (!containerRef.current) return
    const cy = cytoscape({
      container: containerRef.current,
      elements: buildElements(graph, { overview }),
      style: buildStylesheet({ overview }),
      layout: layoutOptions(layout),
      wheelSensitivity: 0.25,
      minZoom: overview ? 0.04 : 0.25,
      maxZoom: 3,
      // Large-graph render budget: skip edges mid-pan and render the canvas as a texture while
      // interacting so a few-thousand-node overview stays smooth.
      ...(overview
        ? { hideEdgesOnViewport: true, textureOnViewport: true, pixelRatio: 1, motionBlur: false }
        : {}),
    })
    cyRef.current = cy

    cy.on('tap', 'node', (evt: EventObject) => {
      onSelectRef.current?.((evt.target as NodeSingular).id())
    })
    cy.on('tap', (evt: EventObject) => {
      if (evt.target === cy) onSelectRef.current?.(null)
    })

    return () => {
      cy.destroy()
      cyRef.current = null
    }
    // Rebuild only when the underlying graph identity changes; layout/overlays handled separately.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph])

  /* Re-run layout when the layout preset changes. */
  useEffect(() => {
    cyRef.current?.layout(layoutOptions(layout)).run()
  }, [layout])

  /* Evidence overlay — emphasise cited elements, dim the rest. */
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.batch(() => {
      cy.elements().removeClass('evidence')
      const ids = [...(evidenceNodeIds ?? []), ...(evidenceEdgeIds ?? [])]
      if (ids.length === 0) return
      const evidence = cy.collection()
      for (const id of evidenceNodeIds ?? []) evidence.merge(cy.getElementById(id))
      for (const id of evidenceEdgeIds ?? []) {
        const e = cy.getElementById(id)
        evidence.merge(e)
        evidence.merge(e.connectedNodes())
      }
      evidence.addClass('evidence')
    })
  }, [evidenceNodeIds, evidenceEdgeIds])

  /* Find-path overlay — highlight the path nodes/edges and dim everything else. */
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.batch(() => {
      cy.elements().removeClass('path dimmed')
      const ids = [...(pathNodeIds ?? []), ...(pathEdgeIds ?? [])]
      if (ids.length === 0) return
      const path = cy.collection()
      for (const id of [...(pathNodeIds ?? []), ...(pathEdgeIds ?? [])]) {
        path.merge(cy.getElementById(id))
      }
      path.addClass('path')
      cy.elements().not(path).addClass('dimmed')
    })
  }, [pathNodeIds, pathEdgeIds])

  /* Reflect external selection into cytoscape (and centre on the node). */
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.nodes().unselect()
    if (highlightId) {
      const n = cy.getElementById(highlightId)
      if (n.nonempty()) n.select()
    }
  }, [highlightId])

  useImperativeHandle(
    handleRef,
    () => ({
      cy: () => cyRef.current,
      fit: () =>
        cyRef.current?.animate(
          { fit: { eles: cyRef.current.elements(), padding: 36 } },
          { duration: 250 },
        ),
      zoomBy: (factor: number) => {
        const cy = cyRef.current
        if (!cy) return
        cy.zoom({
          level: clamp(cy.zoom() * factor, cy.minZoom(), cy.maxZoom()),
          renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
        })
      },
      flash: (id: string) => {
        const cy = cyRef.current
        if (!cy) return
        const n = cy.getElementById(id)
        if (n.empty()) return
        cy.animate({ center: { eles: n }, zoom: Math.min(1.6, cy.maxZoom()) }, { duration: 350 })
        n.addClass('flash')
        window.setTimeout(() => n.removeClass('flash'), 1100)
      },
    }),
    [],
  )

  return <div ref={containerRef} className={className} role="application" aria-label={ariaLabel} />
}
