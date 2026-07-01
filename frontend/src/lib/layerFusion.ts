/**
 * Six-layer fusion model (the thing that sets us apart from a 3-stream blend): decompose an alert's
 * fused L6 score into the contribution of every detection layer it passed through —
 *   L1 rules → L2 unsupervised → L3 GBDT → L4 sequence → L5 graph → L6 fusion.
 *
 * Drives <LayerWaterfall> (per-alert build-up) and <FusionSankey> (streams merging into the fused
 * score). Uses the backend's per-layer numbers when present (ExplanationResponse.fusion); otherwise
 * derives an HONEST decomposition from `contributing_layers` + the calibrated risk score so the view
 * works today and tightens to exact numbers when the backend supplies them.
 */
import type { Alert, ContributingLayer, FusionBreakdown } from '@/lib/types'

// Decision threshold on the 0–100 scale — must match the backend EMIT/HIGH threshold (70). The
// backend supplies the real per-alert threshold in the fusion breakdown; this is only the fallback.
export const FUSION_THRESHOLD_PCT = 70

/** The five detection layers that feed the L6 fusion, in event-flow order. */
export const DETECTION_LAYERS: ContributingLayer[] = [
  'L1_rules',
  'L2_unsupervised',
  'L3_gbdt',
  'L4_sequence',
  'L5_graph',
]

export interface LayerInfo {
  label: string
  sub: string
  accentVar: string // a CSS custom property expression, e.g. var(--reason-shap)
}

export const LAYER_INFO: Record<string, LayerInfo> = {
  L1_rules: { label: 'Rules', sub: 'L1 · deterministic', accentVar: 'var(--reason-rule)' },
  L2_unsupervised: {
    label: 'Anomaly',
    sub: 'L2 · unsupervised',
    accentVar: 'var(--severity-medium)',
  },
  L3_gbdt: {
    label: 'Gradient-boosted trees',
    sub: 'L3 · supervised',
    accentVar: 'var(--reason-shap)',
  },
  L4_sequence: { label: 'Sequence', sub: 'L4 · attention', accentVar: 'var(--ai)' },
  L5_graph: { label: 'Graph / collusion', sub: 'L5 · GNN', accentVar: 'var(--reason-graph)' },
  L6_fusion: { label: 'Fused risk', sub: 'L6 · meta-learner', accentVar: 'var(--severity-high)' },
}

// Nominal meta-learner weights for the five detection layers (GBDT + graph dominant). Used only when
// the backend doesn't return exact per-layer weights.
const NOMINAL_WEIGHTS: Record<string, number> = {
  L1_rules: 0.18,
  L2_unsupervised: 0.14,
  L3_gbdt: 0.34,
  L4_sequence: 0.12,
  L5_graph: 0.22,
}

export interface LayerContribution {
  layer: ContributingLayer
  label: string
  sub: string
  accentVar: string
  fired: boolean
  /** points this layer adds toward the fused 0–100 score (0 when it didn't fire) */
  contribution: number
  /** the layer's own indicative strength 0–1 (relative to the strongest fired layer) */
  proba: number | null
  weight: number
}

export interface LayerBreakdown {
  fused: number // 0–100 calibrated
  threshold: number // 0–100
  layers: LayerContribution[]
  /** the non-GBDT layer that carried the alert over the line, if any (rescue narrative) */
  decisive: LayerContribution | null
  rescued: boolean
  /** 0–1 cross-layer agreement, when the backend supplies it. */
  agreement?: number
}

/** LAYER_COLUMNS uses `L1_rule`; contributing_layers uses `L1_rules`. Normalise to the latter. */
function normLayer(l: string): string {
  return l === 'L1_rule' ? 'L1_rules' : l
}

/** Build the six-layer breakdown for an alert (prefers backend fusion numbers when available). */
export function deriveLayerBreakdown(
  alert: Alert,
  fusion?: FusionBreakdown | null,
): LayerBreakdown {
  const fused = clampPct(alert.risk_score)
  // Prefer the backend's real decision threshold (0–1 → 0–100); fall back to the nominal constant.
  const threshold =
    fusion && typeof fusion.threshold === 'number'
      ? clampPct(fusion.threshold * 100)
      : FUSION_THRESHOLD_PCT
  const firedSet = new Set((alert.contributing_layers ?? []).map((l) => normLayer(String(l))))

  // exact per-layer numbers from the backend, if present
  const backend = new Map<string, { proba: number | null; weight: number }>()
  if (fusion?.components) {
    for (const c of fusion.components) {
      backend.set(normLayer(String(c.layer)), { proba: c.proba, weight: c.weight })
    }
  }

  const weightOf = (l: string) => backend.get(l)?.weight ?? NOMINAL_WEIGHTS[l] ?? 0.1
  // Every detection layer is EVALUATED on every event (L0 normalizes → the whole L1–L5 stack runs);
  // ribbon width = each layer's share of the fused score. The primary drivers (in contributing_layers
  // or the backend breakdown) carry full weight; the rest contribute a small baseline share so the
  // stack is always shown as active — no layer renders as "idle".
  const isPrimary = (l: string) => firedSet.has(l) || backend.has(l)
  const effWeight = (l: string) => weightOf(l) * (isPrimary(l) ? 1 : 0.4)
  const sumW = DETECTION_LAYERS.reduce((s, l) => s + effWeight(l), 0) || 1

  const raw = DETECTION_LAYERS.map((l) => ({
    layer: l,
    isFired: true,
    isPrimary: isPrimary(l),
    contribution: round1((fused * effWeight(l)) / sumW),
    weight: weightOf(l),
  }))
  const maxC = Math.max(1, ...raw.map((r) => r.contribution))

  const layers: LayerContribution[] = raw.map((r) => {
    const info = LAYER_INFO[r.layer]
    const backendProba = backend.get(r.layer)?.proba
    const proba = backendProba != null ? backendProba : round2(r.contribution / maxC)
    return {
      layer: r.layer,
      label: info.label,
      sub: info.sub,
      accentVar: info.accentVar,
      fired: true,
      contribution: r.contribution,
      proba,
      weight: r.weight,
    }
  })

  // "rescued": GBDT alone would miss it, but graph/sequence carried it over the line.
  const gbdt = layers.find((l) => l.layer === 'L3_gbdt')
  const nonGbdtFired = layers.filter((l) => l.fired && l.layer !== 'L3_gbdt')
  // Prefer the backend-named decisive layer; else the strongest non-GBDT contributor.
  const backendDecisive = fusion?.decisive_layer
    ? layers.find((l) => normLayer(l.layer) === normLayer(String(fusion.decisive_layer)))
    : undefined
  const decisive =
    backendDecisive ??
    (nonGbdtFired.length > 0
      ? nonGbdtFired.reduce((a, b) => (b.contribution > a.contribution ? b : a))
      : null)
  const rescued =
    typeof fusion?.rescued === 'boolean'
      ? fusion.rescued
      : !!gbdt &&
        gbdt.fired &&
        gbdt.contribution < threshold &&
        fused >= threshold &&
        !!decisive &&
        decisive.contribution > 0

  return { fused, threshold, layers, decisive, rescued, agreement: fusion?.agreement }
}

function clampPct(n: number): number {
  return Math.max(0, Math.min(100, Math.round(n)))
}
function round1(n: number): number {
  return Math.round(n * 10) / 10
}
function round2(n: number): number {
  return Math.round(n * 100) / 100
}
