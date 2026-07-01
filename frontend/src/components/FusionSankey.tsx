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
  return (
    <Layer>
      <Rectangle x={x} y={y} width={width} height={height} fill={payload.color} fillOpacity={0.9} radius={2} />
      <text
        x={isOut ? x - 6 : x + width + 6}
        y={y + height / 2}
        textAnchor={isOut ? 'end' : 'start'}
        dominantBaseline="middle"
        className="fill-foreground font-mono"
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
  const fired = b.layers.filter((l) => l.fired && l.contribution > 0)

  // nodes: each fired layer, then the fused node (last)
  const nodes: SankeyNodeDatum[] = [
    ...fired.map((l) => ({ name: l.label, color: `hsl(${l.accentVar})` })),
    { name: `Fused L6 · ${b.fused}`, color: `hsl(${LAYER_INFO.L6_fusion.accentVar})` },
  ]
  const fusedIndex = nodes.length - 1
  const links = fired.map((l, i) => ({ source: i, target: fusedIndex, value: Math.max(0.5, l.contribution) }))

  if (fired.length === 0) {
    return (
      <Surface tone="operational" pad="md" className={className}>
        <Eyebrow>Fusion flow</Eyebrow>
        <p className="mt-2 text-xs text-muted-foreground">
          No detection layers fired for this alert.
        </p>
      </Surface>
    )
  }

  return (
    <Surface tone="operational" pad="md" className={cn('space-y-2', className)}>
      <div className="flex items-baseline justify-between">
        <Eyebrow>Fusion flow · {fired.length} layers → L6</Eyebrow>
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
    </Surface>
  )
}
