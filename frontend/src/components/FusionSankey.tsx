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
  // Show ALL five detection layers (L1–L5) flowing into L6 — fired layers as solid ribbons (width ∝
  // contribution), layers that didn't fire for this alert as a thin, dimmed "idle" ribbon. Hiding
  // the non-fired ones made it look like a 4-layer system; this shows the full 6-layer stack.
  const layers = b.layers
  const firedCount = layers.filter((l) => l.fired).length

  const nodes: SankeyNodeDatum[] = [
    ...layers.map((l) => ({
      name: l.fired ? l.label : `${l.label} · idle`,
      color: l.fired ? `hsl(${l.accentVar})` : 'hsl(var(--muted-foreground))',
      fired: l.fired,
    })),
    { name: `Fused L6 · ${b.fused}`, color: `hsl(${LAYER_INFO.L6_fusion.accentVar})`, fired: true },
  ]
  const fusedIndex = nodes.length - 1
  const links = layers.map((l, i) => ({
    source: i,
    target: fusedIndex,
    // fired layers carry width ∝ their contribution; idle layers get a thin ghost ribbon.
    value: l.fired ? Math.max(0.8, l.contribution) : 0.35,
  }))

  return (
    <Surface tone="operational" pad="md" className={cn('space-y-2', className)}>
      <div className="flex items-baseline justify-between">
        <Eyebrow>
          6-layer fusion · L1–L5 → L6 ({firedCount}/5 fired)
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
      <p className="text-3xs text-muted-foreground">
        All six layers are shown: bright ribbons are the layers that fired for this alert; dim “idle”
        ribbons are layers that did not contribute. The fused L6 score is the calibrated blend.
      </p>
    </Surface>
  )
}
