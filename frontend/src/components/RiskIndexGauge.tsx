/**
 * M2.1 — Continuous per-user insider-risk index gauge.
 *
 * A standing 0–100 insider-risk score per privileged user (HR + access + recent-anomaly posture),
 * with sub-scores and the top drivers. ALERT-ONLY: a displayed, explained score for a human — never
 * an automated action. When the index is uncalibrated (stub weights) it says so explicitly.
 * Renders nothing if the entity has no index yet (e.g. the batch job hasn't run).
 */
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/apiClient'
import { riskColor, riskLevel, RISK_TEXT } from '@/lib/risk'
import { humanize } from '@/lib/format'
import { cn } from '@/lib/cn'
import type { RiskIndex } from '@/lib/types'
import { GROUP_DEFINITIONS, driverTooltip } from '@/lib/riskIndexTooltips'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Eyebrow } from '@/components/ui/eyebrow'
import { Skeleton } from '@/components/ui/skeleton'

const GROUPS = [
  { key: 'hr_score', ...GROUP_DEFINITIONS.hr_score },
  { key: 'access_score', ...GROUP_DEFINITIONS.access_score },
  { key: 'anomaly_score', ...GROUP_DEFINITIONS.anomaly_score },
] as const

export function RiskIndexGauge({ entityId }: { entityId: string }) {
  const query = useQuery<RiskIndex>({
    queryKey: ['entities', entityId, 'risk-index'],
    queryFn: () => apiClient.getRiskIndex(entityId),
    enabled: entityId.length > 0,
    retry: false, // a 404 (no index yet) is expected — don't retry, just hide
  })

  if (query.isError) return null // no index for this entity — render nothing

  if (query.isLoading || !query.data) {
    return (
      <Card>
        <CardContent className="p-4">
          <Skeleton className="h-24 w-full rounded-lg" />
        </CardContent>
      </Card>
    )
  }

  const idx = query.data
  const level = riskLevel(idx.composite)
  const color = riskColor(idx.composite)

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex items-center justify-between gap-2">
          <Eyebrow>Insider-risk index</Eyebrow>
          {!idx.calibrated ? (
            <Badge variant="muted" className="text-2xs" title="Stub weights — human review only">
              uncalibrated · review only
            </Badge>
          ) : null}
        </div>

        <div className="flex items-center gap-4">
          <div
            className="flex size-16 shrink-0 items-center justify-center rounded-full text-xl font-semibold tabular-nums"
            style={{ color, boxShadow: `inset 0 0 0 3px ${color}` }}
            aria-label={`insider risk ${idx.composite} of 100`}
            title={`Composite insider-risk index (0–100) = 30% × HR posture + 35% × Access posture + 35% × Recent anomaly. This alert: ${idx.composite}/100.`}
          >
            {idx.composite}
          </div>
          <div className="min-w-0 flex-1 space-y-2">
            {GROUPS.map((g) => {
              const v = Math.round((idx[g.key] as number) * 100)
              return (
                <div key={g.key} title={g.tooltip} className="cursor-help">
                  <div className="mb-0.5 flex items-center justify-between text-2xs text-muted-foreground">
                    <span className="underline decoration-dotted underline-offset-2">
                      {g.label} <span className="opacity-50">· {Math.round(g.weight * 100)}%</span>
                    </span>
                    <span className="tabular-nums">{v}</span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${v}%`, backgroundColor: riskColor(v) }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {idx.top_drivers.length > 0 ? (
          <div className="flex flex-wrap items-center gap-1.5">
            <span
              className={cn('text-2xs font-medium', RISK_TEXT[level])}
              title="The signals contributing most to this score. Hover each for its meaning."
            >
              Top drivers:
            </span>
            {idx.top_drivers.map((d) => (
              <Badge
                key={d}
                variant="secondary"
                className="cursor-help text-2xs"
                title={driverTooltip(d) ?? humanize(d)}
              >
                {humanize(d)}
              </Badge>
            ))}
          </div>
        ) : null}

        {/* How this score was computed — the weighted sum, so the number is auditable. */}
        <details className="group text-2xs">
          <summary className="cursor-pointer select-none font-medium text-muted-foreground hover:text-foreground">
            How this {idx.composite} was computed
          </summary>
          <div className="mt-2 space-y-1 rounded-lg bg-muted/50 p-2">
            <div className="font-mono text-3xs text-muted-foreground">
              composite = 0.30·HR + 0.35·Access + 0.35·Anomaly (×100)
            </div>
            {GROUPS.map((g) => {
              const sub = idx[g.key] as number
              return (
                <div key={g.key} className="flex items-center justify-between tabular-nums">
                  <span className="text-muted-foreground">{g.label}</span>
                  <span className="font-mono">
                    {Math.round(sub * 100)} × {g.weight.toFixed(2)} ={' '}
                    <span className="text-foreground">{(sub * g.weight * 100).toFixed(1)}</span>
                  </span>
                </div>
              )
            })}
            <div className="flex items-center justify-between border-t border-border/60 pt-1 font-medium tabular-nums">
              <span>Composite</span>
              <span className="font-mono text-foreground">{idx.composite}</span>
            </div>
          </div>
        </details>

        <p className="text-2xs text-muted-foreground">
          Alert-only — a standing score for human review; it never triggers an automated action.
        </p>
      </CardContent>
    </Card>
  )
}
