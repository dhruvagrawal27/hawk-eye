/**
 * Fusion Sankey — the detection layers' contributions flowing as weighted ribbons into the fused L6
 * risk score. Literally shows "fusion": L1 rules / L2 anomaly / L3 GBDT / L4 sequence / L5 graph
 * streams merging, ribbon width ∝ each layer's contribution. Recharts Sankey, our risk palette.
 */
import { Sankey, Tooltip, ResponsiveContainer, Layer, Rectangle } from 'recharts'
import { cn } from '@/lib/cn'
import { deriveLayerBreakdown, LAYER_INFO } from '@/lib/layerFusion'
import type { Alert, FusionBreakdown } from '@/lib/types'
import { Surface } from '@/components/ui/surface'
import { Eyebrow } from '@/components/ui/eyebrow'

interface SankeyNodeDatum {
  name: string
  color: string
  fired?: boolean
}
interface NodeProps {
  x: number
  y: number
  width: number
  height: number
  index: number
  payload: SankeyNodeDatum & { value: number }
  containerWidth: number
}

function FusionNode({ x, y, width, height, payload, containerWidth }: NodeProps) {
  const isOut = x + width + 6 > containerWidth
  const idle = payload.fired === false
  return (
    <Layer>
      <Rectangle
        x={x}
        y={y}
        width={width}
        height={height}
        fill={payload.color}
        fillOpacity={idle ? 0.28 : 0.9}
        radius={2}
      />
      <text
        x={isOut ? x - 6 : x + width + 6}
        y={y + height / 2}
        textAnchor={isOut ? 'end' : 'start'}
        dominantBaseline="middle"
        className={idle ? 'fill-muted-foreground font-mono' : 'fill-foreground font-mono'}
        fontSize={11}
      >
        {payload.name}
      </text>
    </Layer>
  )
}

interface LinkProps {
  sourceX: number
  targetX: number
  sourceY: number
  targetY: number
  sourceControlX: number
  targetControlX: number
  linkWidth: number
  index: number
  payload: { source: SankeyNodeDatum }
}

function FusionLink(props: LinkProps) {
  const { sourceX, targetX, sourceY, targetY, sourceControlX, targetControlX, linkWidth, payload } =
    props
  return (
    <path
      d={`M${sourceX},${sourceY}C${sourceControlX},${sourceY} ${targetControlX},${targetY} ${targetX},${targetY}`}
      fill="none"
      stroke={payload.source.color}
      strokeWidth={Math.max(1, linkWidth)}
      strokeOpacity={0.28}
    />
  )
}

export function FusionSankey({
  alert,
  fusion,
  height = 220,
  className,
}: {
  alert: Alert
  fusion?: FusionBreakdown | null
  height?: number
  className?: string
}) {
  const b = deriveLayerBreakdown(alert, fusion)
  // Full pipeline: L0 (normalize raw telemetry into the unified event model) → the five detectors
  // L1–L5 → L6 fusion. Fired detectors are solid ribbons (width ∝ contribution); detectors that did
  // not score for THIS alert are shown as legible "idle" ribbons with a reason — never hidden.
  const layers = b.layers // L1–L5
  const firedCount = layers.filter((l) => l.fired).length

  // Why a detector is idle for this alert (honest, per-layer).
  const IDLE_REASON: Record<string, string> = {
    L1_rules: 'no deterministic rule matched this event',
    L2_unsupervised: "within the entity's normal UEBA baseline",
    L3_gbdt: 'supervised score below its contribution threshold',
    L4_sequence: 'no mature behavioural session/window for this alert',
    L5_graph: 'no collusion subgraph linked to this entity',
  }
  const idleLayers = layers.filter((l) => !l.fired)

  const L0_INDEX = 0
  const detStart = 1
  const fusedIndex = detStart + layers.length
  const nodes: SankeyNodeDatum[] = [
    { name: 'L0 · normalize', color: 'hsl(var(--reason-shap))', fired: true },
    ...layers.map((l) => ({
      name: l.fired ? l.label : `${l.label} · idle`,
      color: l.fired ? `hsl(${l.accentVar})` : 'hsl(var(--muted-foreground))',
      fired: l.fired,
    })),
    { name: `Fused L6 · ${b.fused}`, color: `hsl(${LAYER_INFO.L6_fusion.accentVar})`, fired: true },
  ]
  const links = [
    // L0 feeds every detector (uniform thin ribbon — all layers read the same normalized L0 event).
    ...layers.map((_, i) => ({ source: L0_INDEX, target: detStart + i, value: 0.6 })),
    // Detectors flow into L6 — width ∝ contribution; idle detectors keep a thin ghost ribbon.
    ...layers.map((l, i) => ({
      source: detStart + i,
      target: fusedIndex,
      value: l.fired ? Math.max(0.8, l.contribution) : 0.4,
    })),
  ]

  return (
    <Surface tone="operational" pad="md" className={cn('space-y-2', className)}>
      <div className="flex items-baseline justify-between">
        <Eyebrow>
          Detection pipeline · L0 → L6 ({firedCount} of 5 detectors fired)
        </Eyebrow>
        <span className="font-mono text-2xs text-muted-foreground">width ∝ contribution</span>
      </div>
      <div style={{ width: '100%', height }}>
        <ResponsiveContainer width="100%" height="100%">
          <Sankey
            data={{ nodes, links }}
            node={<FusionNode {...({} as NodeProps)} />}
            link={<FusionLink {...({} as LinkProps)} />}
            nodePadding={18}
            nodeWidth={10}
            margin={{ top: 8, right: 110, bottom: 8, left: 8 }}
          >
            <Tooltip
              contentStyle={{
                background: 'hsl(var(--popover))',
                border: '1px solid hsl(var(--border))',
                borderRadius: 8,
                fontSize: 12,
              }}
            />
          </Sankey>
        </ResponsiveContainer>
      </div>
      <p className="text-3xs leading-relaxed text-muted-foreground">
        <span className="text-foreground">L0</span> normalizes raw telemetry (CBS/SWIFT/PAM/HR…) into
        the unified event model every detector reads. The six layers: <span className="text-foreground">
        L1</span> rules · <span className="text-foreground">L2</span> anomaly · <span className="text-foreground">
        L3</span> GBDT · <span className="text-foreground">L4</span> sequence · <span className="text-foreground">
        L5</span> graph → <span className="text-foreground">L6</span> calibrated fusion. Bright ribbons
        fired for this alert; dim “idle” ribbons did not contribute (a normal, honest outcome).
      </p>
      {idleLayers.length > 0 ? (
        <div className="rounded-md border border-border/50 bg-muted/30 p-2 text-3xs text-muted-foreground">
          <span className="font-medium text-foreground">Idle this alert:</span>{' '}
          {idleLayers.map((l, i) => (
            <span key={l.layer}>
              {i > 0 ? ' · ' : ''}
              <span className="text-foreground/80">{l.label}</span> — {IDLE_REASON[l.layer] ?? 'did not score'}
            </span>
          ))}
        </div>
      ) : null}
    </Surface>
  )
}
