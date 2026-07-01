/**
 * Fraud-typology analytics (management / vigilance oversight) — *which* insider typologies actually
 * fire, how often they're human-confirmed vs cleared, and the exposure behind each. Ranked by
 * prevalence: a prevalence bar, a colour-coded confirmed-rate pill (real vs noise), the detection
 * layers that catch it, and exposure. Read-only portfolio view; no per-person scoring.
 */
import { useQuery } from '@tanstack/react-query'
import { ShieldCheck } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { cn } from '@/lib/cn'
import { formatINRCompact } from '@/lib/format'
import { Surface } from '@/components/ui/surface'
import { Eyebrow } from '@/components/ui/eyebrow'
import { QueryBoundary } from '@/components/QueryBoundary'
import { Skeleton } from '@/components/ui/skeleton'
import type { TypologyAnalyticsResponse, TypologyStat } from '@/lib/types'

const nf = new Intl.NumberFormat('en-IN')

/** Confirmed-rate → tone: high = mostly real (good precision), low = noisy. */
function rateTone(rate: number): string {
  if (rate >= 0.5) return 'var(--severity-high)'
  if (rate >= 0.3) return 'var(--severity-medium)'
  return 'var(--muted-foreground)'
}

function Row({ t, maxAlerts }: { t: TypologyStat; maxAlerts: number }) {
  const prevalence = maxAlerts > 0 ? (t.alerts / maxAlerts) * 100 : 0
  const ratePct = Math.round(t.confirmed_rate * 100)
  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 py-1.5">
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-xs font-medium text-foreground">{t.label}</span>
          <span className="flex shrink-0 gap-0.5">
            {t.layers.map((l) => (
              <span
                key={l}
                className="rounded bg-muted px-1 font-mono text-[0.6rem] text-muted-foreground"
              >
                {l}
              </span>
            ))}
          </span>
        </div>
        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary/70"
            style={{ width: `${Math.max(2, prevalence)}%` }}
          />
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-3 text-right">
        <span className="w-10 tabular-nums text-xs text-foreground" title="alerts raised">
          {nf.format(t.alerts)}
        </span>
        <span
          className="w-16 rounded-full px-1.5 py-0.5 text-center font-mono text-[0.65rem] tabular-nums"
          style={{
            color: `hsl(${rateTone(t.confirmed_rate)})`,
            backgroundColor: `hsl(${rateTone(t.confirmed_rate)} / 0.12)`,
          }}
          title={`${t.confirmed} confirmed · ${t.false_positive} cleared · ${t.open} open`}
        >
          {ratePct}% real
        </span>
        <span className="w-16 tabular-nums text-2xs text-muted-foreground" title="exposure">
          {formatINRCompact(t.exposure_inr)}
        </span>
      </div>
    </div>
  )
}

function Body({ data }: { data: TypologyAnalyticsResponse }) {
  const maxAlerts = Math.max(1, ...data.typologies.map((t) => t.alerts))
  const totalRatePct = Math.round(data.totals.confirmed_rate * 100)
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>
          <span className="font-semibold text-foreground">{nf.format(data.totals.alerts)}</span>{' '}
          alerts
        </span>
        <span>
          <span className="font-semibold text-foreground">{nf.format(data.totals.confirmed)}</span>{' '}
          confirmed
        </span>
        <span className="inline-flex items-center gap-1">
          <ShieldCheck className="size-3 text-severity-high" />
          <span className="font-semibold text-foreground">{totalRatePct}%</span> confirmed-rate
        </span>
        <span>
          <span className="font-semibold text-foreground">
            {formatINRCompact(data.totals.exposure_inr)}
          </span>{' '}
          exposure
        </span>
      </div>
      <div className="grid grid-cols-[1fr_auto] gap-x-3 border-b border-border/60 pb-1 text-[0.65rem] uppercase tracking-wide text-muted-foreground">
        <span>Typology · detection layers</span>
        <span className="flex gap-3 text-right">
          <span className="w-10">alerts</span>
          <span className="w-16 text-center">confirmed</span>
          <span className="w-16">exposure</span>
        </span>
      </div>
      <div className="divide-y divide-border/40">
        {data.typologies.map((t) => (
          <Row key={t.typology} t={t} maxAlerts={maxAlerts} />
        ))}
      </div>
    </div>
  )
}

export function TypologyAnalytics({ className }: { className?: string }) {
  const query = useQuery({
    queryKey: queryKeys.typologyAnalytics(),
    queryFn: () => apiClient.getTypologyAnalytics(),
  })
  return (
    <Surface tone="operational" pad="md" className={cn('space-y-3', className)}>
      <Eyebrow className="flex items-center gap-1.5">
        <ShieldCheck className="size-3" />
        Fraud typologies · prevalence &amp; confirmed-rate
      </Eyebrow>
      <QueryBoundary
        isLoading={query.isLoading}
        isError={query.isError}
        error={query.error}
        onRetry={() => void query.refetch()}
        skeleton={<Skeleton className="h-64 w-full" />}
      >
        {query.data ? <Body data={query.data} /> : null}
      </QueryBoundary>
    </Surface>
  )
}
