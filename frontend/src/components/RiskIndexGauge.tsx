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
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Eyebrow } from '@/components/ui/eyebrow'
import { Skeleton } from '@/components/ui/skeleton'

const GROUPS: { key: 'hr_score' | 'access_score' | 'anomaly_score'; label: string }[] = [
  { key: 'hr_score', label: 'HR posture' },
  { key: 'access_score', label: 'Access posture' },
  { key: 'anomaly_score', label: 'Recent anomaly' },
]

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
          >
            {idx.composite}
          </div>
          <div className="min-w-0 flex-1 space-y-2">
            {GROUPS.map((g) => {
              const v = Math.round((idx[g.key] as number) * 100)
              return (
                <div key={g.key}>
                  <div className="mb-0.5 flex items-center justify-between text-2xs text-muted-foreground">
                    <span>{g.label}</span>
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
            <span className={cn('text-2xs font-medium', RISK_TEXT[level])}>Top drivers:</span>
            {idx.top_drivers.map((d) => (
              <Badge key={d} variant="secondary" className="text-2xs">
                {humanize(d)}
              </Badge>
            ))}
          </div>
        ) : null}

        <p className="text-2xs text-muted-foreground">
          Alert-only — a standing score for human review; it never triggers an automated action.
        </p>
      </CardContent>
    </Card>
  )
}
