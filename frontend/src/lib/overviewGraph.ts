/**
 * overviewGraph — the dense synthetic org graph behind the Graph Explorer landing view.
 *
 * The real `GET /graph` route seeds a *tight* subgraph from the top-N risk alerts (great for tracing
 * one collusion ring, but visually sparse). The Explorer's headline surface instead wants the whole
 * population at a glance — every employee, the systems they touch, and the risk heat across them —
 * so an investigator can spot where the graph is "hot" before drilling in.
 *
 * We synthesise that population deterministically on the client (seeded PRNG → identical layout on
 * every reload, no backend round-trip, works whether mocks are on or off). It emits the same
 * GraphOverviewResponse shape the canvas already speaks, plus precomputed x/y so the canvas can paint
 * it with the fast `preset` layout instead of an iterative solver that would choke on ~4k nodes.
 *
 * Encodings mirror the screenshot: numeric tokenized ids, node colour + size by fused risk (a heat
 * map — cool slate for the quiet majority, red for the hot actors), a preferential-attachment system
 * backbone (a few hub systems, a long tail of lightly-touched / isolated ones), and a scatter of
 * maker-checker collusion edges wiring the riskiest actors together.
 *
 * Swap back to the live route later by pointing GraphExplorer at `apiClient.getGraphOverview`.
 */
import type { GraphEdge, GraphNode, GraphOverviewResponse } from './types'

export interface OverviewPopulation {
  employees: number
  systems: number
  edges: number
}

export interface OverviewGraph extends GraphOverviewResponse {
  /** Full-population counts for the header line ("N employees · N systems · N edges"). */
  population: OverviewPopulation
}

/* ── Target scale (matches the reference design) ─────────────────────────────────────────────── */
const EMPLOYEES = 250
const SYSTEMS = 3742
const EDGES = 6191
const COLLUSION_EDGES = 96 // maker-checker actor↔actor edges (the rest are actor→system)
const TOTAL_NODES = EMPLOYEES + SYSTEMS

/* Layout canvas (arbitrary units — cytoscape `fit` rescales to the viewport; only ratios matter). */
const W = 5200
const H = 3400
const CLUSTERS = 26

/** Deterministic PRNG (mulberry32) — stable galaxy across reloads, no Math.random. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** Rough standard-normal in ~[-2, 2] via the mean of four uniforms (central-limit). */
function gauss(rand: () => number): number {
  return (rand() + rand() + rand() + rand() - 2) * 1.15
}

/** Build the dense overview graph. Pure + deterministic given the fixed seed. */
export function buildOverviewGraph(): OverviewGraph {
  const rand = mulberry32(0x1a2b3c4d)

  // ── Unique 6-digit tokenized ids (employees first, then systems). ──────────────────────────
  const ids: string[] = []
  const usedId = new Set<string>()
  while (ids.length < TOTAL_NODES) {
    const s = String(100000 + Math.floor(rand() * 899999))
    if (!usedId.has(s)) {
      usedId.add(s)
      ids.push(s)
    }
  }
  const empIds = ids.slice(0, EMPLOYEES)
  const sysIds = ids.slice(EMPLOYEES)

  // ── Cluster anchors — systems clump around these to read as an organic hairball. ────────────
  const anchors = Array.from({ length: CLUSTERS }, () => ({
    x: 0.06 * W + rand() * 0.88 * W,
    y: 0.08 * H + rand() * 0.84 * H,
    r: 150 + rand() * 240,
  }))

  // ── System nodes — 70% clustered, 30% scattered wide (the lone peripheral dots). ────────────
  const pos = new Map<string, { x: number; y: number }>()
  const sysNodes: GraphNode[] = sysIds.map((id) => {
    let x: number
    let y: number
    if (rand() < 0.7) {
      const a = anchors[Math.floor(rand() * anchors.length)]
      x = a.x + gauss(rand) * a.r
      y = a.y + gauss(rand) * a.r
    } else {
      x = rand() * W
      y = rand() * H
    }
    pos.set(id, { x, y })
    return { id, type: 'system', label: id, tokenized: true, x, y }
  })

  // ── Employee risk — a hot minority, a medium band, a cool majority. ─────────────────────────
  const empRisk = new Map<string, number>()
  for (const id of empIds) {
    const r = rand()
    const risk =
      r < 0.16
        ? 72 + Math.floor(rand() * 27) // hot 72–98
        : r < 0.45
          ? 45 + Math.floor(rand() * 25) // 45–69
          : 12 + Math.floor(rand() * 33) // 12–44
    empRisk.set(id, risk)
  }

  // ── Actor→system edges via preferential attachment (rich systems become hubs). ──────────────
  const edges: GraphEdge[] = []
  const pairSeen = new Set<string>()
  const pool: string[] = [] // endpoints already used → rich-get-richer sampling
  const sysMaxRisk = new Map<string, number>() // hottest actor touching each system
  const actorTarget = EDGES - COLLUSION_EDGES

  const pickSystem = (): string =>
    pool.length > 0 && rand() < 0.55
      ? pool[Math.floor(rand() * pool.length)]
      : sysIds[Math.floor(rand() * sysIds.length)]

  // Give every employee a base degree (skewed low, occasional heavy hub actor); hot actors touch
  // a few more systems. We keep pushing rounds until we hit the exact actor-edge target.
  let guard = 0
  while (edges.length < actorTarget && guard < actorTarget * 40) {
    for (const emp of empIds) {
      if (edges.length >= actorTarget) break
      const risk = empRisk.get(emp) ?? 30
      const degree = 4 + Math.floor(rand() * rand() * 34) + (risk >= 70 ? 6 : 0)
      for (let k = 0; k < degree && edges.length < actorTarget; k++) {
        const sys = pickSystem()
        const key = `${emp}->${sys}`
        if (pairSeen.has(key)) {
          guard++
          continue
        }
        pairSeen.add(key)
        pool.push(sys)
        sysMaxRisk.set(sys, Math.max(sysMaxRisk.get(sys) ?? 0, risk))
        edges.push({
          id: key,
          source: emp,
          target: sys,
          type: risk >= 70 ? 'transaction' : 'shared_device',
          weight: 1,
        })
      }
    }
    guard++
  }

  // ── Maker-checker collusion edges between the hottest actors (thick red). ────────────────────
  const hotActors = empIds.filter((id) => (empRisk.get(id) ?? 0) >= 68)
  let added = 0
  let cGuard = 0
  while (added < COLLUSION_EDGES && hotActors.length > 1 && cGuard < COLLUSION_EDGES * 60) {
    cGuard++
    const a = hotActors[Math.floor(rand() * hotActors.length)]
    const b = hotActors[Math.floor(rand() * hotActors.length)]
    if (a === b) continue
    const key = `${a}~${b}`
    const rev = `${b}~${a}`
    if (pairSeen.has(key) || pairSeen.has(rev)) continue
    pairSeen.add(key)
    edges.push({ id: key, source: a, target: b, type: 'maker_checker', collusion: true, weight: 2 })
    added++
  }

  // ── System risk tint — most stay cool; some inherit heat from the actors touching them, plus a
  //    handful of explicitly compromised (hot) systems. ────────────────────────────────────────
  for (const node of sysNodes) {
    const touched = sysMaxRisk.get(node.id)
    if (touched !== undefined && touched >= 70 && rand() < 0.45) {
      node.risk = Math.round(touched * 0.7) // amber glow
    }
  }
  for (let i = 0; i < 16; i++) {
    const s = sysNodes[Math.floor(rand() * sysNodes.length)]
    s.risk = 74 + Math.floor(rand() * 20) // compromised system → red
  }

  // ── Employee nodes — placed at the centroid of the systems they touch (organic clustering). ──
  const neighbourPos = new Map<string, { sx: number; sy: number; n: number }>()
  for (const e of edges) {
    const p = pos.get(e.target)
    if (!p) continue
    const acc = neighbourPos.get(e.source) ?? { sx: 0, sy: 0, n: 0 }
    acc.sx += p.x
    acc.sy += p.y
    acc.n += 1
    neighbourPos.set(e.source, acc)
  }
  const empNodes: GraphNode[] = empIds.map((id) => {
    const acc = neighbourPos.get(id)
    const cx = acc && acc.n ? acc.sx / acc.n : W / 2
    const cy = acc && acc.n ? acc.sy / acc.n : H / 2
    const x = cx + gauss(rand) * 90
    const y = cy + gauss(rand) * 90
    return { id, type: 'employee', label: id, risk: empRisk.get(id), tokenized: true, x, y }
  })

  return {
    entity_id: 'overview',
    nodes: [...empNodes, ...sysNodes],
    edges,
    min_score: 0,
    population: { employees: EMPLOYEES, systems: SYSTEMS, edges: edges.length },
  }
}
