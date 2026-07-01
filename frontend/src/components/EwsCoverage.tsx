import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, CircleSlash, Radar, ShieldAlert } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { formatIST, formatPercent, humanize, layerLabel } from '@/lib/format'
import { cn } from '@/lib/cn'
import { QueryBoundary } from '@/components/QueryBoundary'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { InfoTip } from '@/components/ui/tooltip'
import { useAutoAnimateList } from '@/ui'
import type { CoverageIndicator, EwsCoverageResponse } from '@/lib/types'

const CATEGORY_META: Record<CoverageIndicator['category'], { title: string; blurb: string }> = {
  EWS: {
    title: 'Early-Warning Signals (EWS)',
    blurb: 'RBI EWS indicators for incipient stress and diversion (Master Directions on Frauds).',
  },
  RFA: {
    title: 'Red-Flagged Account (RFA) indicators',
    blurb: 'RFA triggers that mandate enhanced monitoring and an EWS → RFA escalation review.',
  },
}

/** Coverage ratio → tailwind tone for the summary bar/figure. */
function ratioTone(pct: number): string {
  if (pct >= 0.9) return 'text-sla-ok'
  if (pct >= 0.7) return 'text-sla-warn'
  return 'text-sla-breached'
}

function CoverageBar({
  covered,
  total,
  className,
}: {
  covered: number
  total: number
  className?: string
}) {
  const pct = total > 0 ? covered / total : 0
  const tone = pct >= 0.9 ? 'bg-sla-ok' : pct >= 0.7 ? 'bg-sla-warn' : 'bg-sla-breached'
  return (
    <div
      className={cn('h-2 w-full overflow-hidden rounded-full bg-muted', className)}
      role="progressbar"
      aria-valuenow={Math.round(pct * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label="Coverage"
    >
      <div
        className={cn('h-full rounded-full transition-all', tone)}
        style={{ width: `${pct * 100}%` }}
      />
    </div>
  )
}

function IndicatorCard({ indicator }: { indicator: CoverageIndicator }) {
  const covered = indicator.covered
  return (
    <div
      className={cn(
        'flex flex-col gap-1.5 rounded-md border p-3',
        covered ? 'border-sla-ok/30 bg-sla-ok/5' : 'border-sla-breached/30 bg-sla-breached/5',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{indicator.label}</p>
          <p className="font-mono text-[0.7rem] text-muted-foreground">{indicator.code}</p>
        </div>
        {covered ? (
          <CheckCircle2 className="size-4 shrink-0 text-sla-ok" aria-label="Covered" />
        ) : (
          <CircleSlash className="size-4 shrink-0 text-sla-breached" aria-label="Coverage gap" />
        )}
      </div>
      {covered ? (
        <div className="flex flex-wrap items-center gap-1.5">
          {indicator.source_layer ? (
            <Badge variant="secondary" className="font-mono text-[0.65rem]">
              {layerLabel(indicator.source_layer)}
            </Badge>
          ) : null}
          {indicator.rule_id ? (
            <span className="font-mono text-[0.7rem] text-muted-foreground">
              {indicator.rule_id}
            </span>
          ) : null}
          {indicator.note ? (
            <span className="text-[0.7rem] text-muted-foreground">· {indicator.note}</span>
          ) : null}
        </div>
      ) : (
        <p className="flex items-start gap-1 text-[0.7rem] text-sla-breached">
          <ShieldAlert className="mt-0.5 size-3 shrink-0" />
          {indicator.note ?? 'No detector mapped — manual review only. Candidate for a new rule.'}
        </p>
      )}
    </div>
  )
}

function CategorySection({
  category,
  indicators,
}: {
  category: CoverageIndicator['category']
  indicators: CoverageIndicator[]
}) {
  const meta = CATEGORY_META[category] ?? { title: category, blurb: '' }
  const [gridRef] = useAutoAnimateList<HTMLDivElement>()
  const covered = indicators.filter((i) => i.covered).length
  const total = indicators.length
  const pct = total > 0 ? covered / total : 0

  if (total === 0) return null

  return (
    <section className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-display text-sm font-semibold">{meta.title}</h3>
          <p className="text-xs text-muted-foreground">{meta.blurb}</p>
        </div>
        <span className={cn('font-mono text-sm font-semibold tabular-nums', ratioTone(pct))}>
          {covered}/{total} · {formatPercent(pct)}
        </span>
      </div>
      <CoverageBar covered={covered} total={total} />
      <div ref={gridRef} className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {indicators.map((i) => (
          <IndicatorCard key={i.code} indicator={i} />
        ))}
      </div>
    </section>
  )
}

function CoverageSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-16 w-full" />
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full" />
        ))}
      </div>
    </div>
  )
}

function CoverageBody({ data }: { data: EwsCoverageResponse }) {
  const { ews, rfa } = useMemo(() => {
    return {
      ews: data.indicators.filter((i) => i.category === 'EWS'),
      rfa: data.indicators.filter((i) => i.category === 'RFA'),
    }
  }, [data.indicators])

  if (data.indicators.length === 0) {
    return (
      <EmptyState
        icon={Radar}
        title="No coverage data"
        description="EWS/RFA indicator coverage will appear once the detection registry is published."
      />
    )
  }

  const pct = data.total > 0 ? data.covered / data.total : 0
  const gaps = data.total - data.covered

  return (
    <div className="space-y-5">
      {/* Overall summary */}
      <div className="grid gap-3 sm:grid-cols-3">
        <Card className="bg-muted/20">
          <CardContent className="p-3">
            <p className="text-[0.7rem] uppercase tracking-wide text-muted-foreground">
              Overall coverage
            </p>
            <p className={cn('mt-1 text-2xl font-bold tabular-nums', ratioTone(pct))}>
              {formatPercent(pct)}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground tabular-nums">
              {data.covered} of {data.total} indicators
            </p>
            <CoverageBar covered={data.covered} total={data.total} className="mt-2" />
          </CardContent>
        </Card>
        <Card className="bg-muted/20">
          <CardContent className="p-3">
            <p className="text-[0.7rem] uppercase tracking-wide text-muted-foreground">Covered</p>
            <p className="mt-1 flex items-center gap-1.5 text-2xl font-bold tabular-nums text-sla-ok">
              <CheckCircle2 className="size-5" />
              {data.covered}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">Mapped to a rule or model layer.</p>
          </CardContent>
        </Card>
        <Card className="bg-muted/20">
          <CardContent className="p-3">
            <p className="text-[0.7rem] uppercase tracking-wide text-muted-foreground">
              Coverage gaps
            </p>
            <p
              className={cn(
                'mt-1 flex items-center gap-1.5 text-2xl font-bold tabular-nums',
                gaps > 0 ? 'text-sla-breached' : 'text-sla-ok',
              )}
            >
              <ShieldAlert className="size-5" />
              {gaps}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Indicators with no automated detector.
            </p>
          </CardContent>
        </Card>
      </div>

      <CategorySection category="EWS" indicators={ews} />
      <CategorySection category="RFA" indicators={rfa} />

      <p className="text-[0.7rem] text-muted-foreground">
        Coverage snapshot generated {formatIST(data.generated_ts)}. Gaps are candidates for new
        rules — propose them in Rules &amp; thresholds (change-controlled).
      </p>
    </div>
  )
}

/**
 * EWS / RFA indicator coverage dashboard (FRONTEND-12; blueprint Part 24.4 screen 5). Renders
 * `apiClient.getEwsCoverage()` as a covered-vs-gap grid grouped by category, with a coverage % summary,
 * the source layer/rule for covered indicators, and notes explaining each gap.
 */
export function EwsCoverage() {
  const coverageQuery = useQuery({
    queryKey: queryKeys.ewsCoverage(),
    queryFn: () => apiClient.getEwsCoverage(),
  })

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Radar className="size-4 text-primary" />
            EWS / RFA coverage
            <InfoTip label="Which RBI Early-Warning-Signal and Red-Flagged-Account indicators are backed by an automated detector (a rule or model layer), and which are gaps relying on manual review.">
              <span className="cursor-help text-muted-foreground">{humanize('coverage map')}</span>
            </InfoTip>
          </CardTitle>
          <CardDescription className="mt-1">
            Mapping of regulatory early-warning indicators to detection layers — covered vs gap.
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <QueryBoundary
          isLoading={coverageQuery.isLoading}
          isError={coverageQuery.isError}
          error={coverageQuery.error}
          onRetry={() => void coverageQuery.refetch()}
          skeleton={<CoverageSkeleton />}
        >
          {coverageQuery.data ? <CoverageBody data={coverageQuery.data} /> : null}
        </QueryBoundary>
      </CardContent>
    </Card>
  )
}
