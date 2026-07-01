/**
 * Reporting & KRI view (FRONTEND-13; blueprint Part 11 reporting + Part 24.4 / Part 24.2 RBAC).
 *
 * Management + board (SCBMF) dashboard built on `getKris()` → <KriDashboard>: KRI cards (alert
 * volume vs capacity, MTTD, FPR, SLA/TAT compliance, open high/critical, coverage) with
 * target/status/delta, a weekly trends chart, and a coverage map. Available to Lead / Compliance /
 * Auditor / Admin — all aggregate figures, no case PII. The regulatory CRILC/FMR export workflow
 * lives on the Compliance screen, so this view links there rather than duplicating it.
 */
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  BarChart3,
  FileSpreadsheet,
  IndianRupee,
  Info,
  ShieldAlert,
  Timer,
  TrendingUp,
} from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { formatINRCompact, formatIST } from '@/lib/format'
import { useAuth } from '@/auth/rbac'
import { PageHeader } from '@/components/PageHeader'
import { QueryBoundary } from '@/components/QueryBoundary'
import { KriDashboard } from '@/components/KriDashboard'
import { AlertHeatmap } from '@/components/AlertHeatmap'
import { TypologyAnalytics } from '@/components/TypologyAnalytics'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'

function ReportingSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-80 w-full lg:col-span-2" />
        <Skeleton className="h-80 w-full" />
      </div>
    </div>
  )
}

export function ReportingView() {
  const { can } = useAuth()
  const canExport = can('view_audit') || can('tune_rules') // compliance/lead can reach exports

  const krisQuery = useQuery({ queryKey: queryKeys.kris(), queryFn: () => apiClient.getKris() })
  const generatedTs = krisQuery.data?.generated_ts

  // Portfolio snapshot — aggregate, non-PII counts so the board/exec sees top-line health on their
  // landing screen (the same numbers investigators see on the operational dashboard).
  const statsQuery = useQuery({
    queryKey: queryKeys.alertStats(),
    queryFn: () => apiClient.getAlertStats(),
  })
  const stats = statsQuery.data

  // Org-wide alert list feeds the temporal heatmap (when alerts land, by IST day/hour).
  const alertsQuery = useQuery({
    queryKey: queryKeys.alerts({ page_size: 200 }),
    queryFn: () => apiClient.listAlerts({ page_size: 200 }),
  })
  const alerts = alertsQuery.data?.items ?? []

  return (
    <div className="space-y-4">
      <PageHeader
        icon={<BarChart3 className="size-5" />}
        title="Reporting & KRIs"
        description="Management and board (SCBMF) key risk indicators. Aggregate figures only — no case PII."
        actions={
          <div className="flex items-center gap-2">
            {generatedTs ? (
              <Badge variant="outline" className="hidden sm:inline-flex">
                As of {formatIST(generatedTs)}
              </Badge>
            ) : null}
            {canExport ? (
              <Button variant="outline" size="sm" asChild>
                <Link to="/compliance">
                  <FileSpreadsheet className="size-3.5" /> CRILC / FMR exports
                </Link>
              </Button>
            ) : null}
          </div>
        }
      />

      {/* Regulatory export pointer — the actual CRILC/FMR generation lives on Compliance. */}
      <div className="flex items-start gap-2.5 rounded-lg border border-border bg-muted/40 px-3.5 py-2.5 text-sm">
        <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
        <p className="text-muted-foreground">
          Regulatory returns (RBI <span className="font-medium text-foreground">CRILC</span> and{' '}
          <span className="font-medium text-foreground">FMR</span>) are generated and reviewed on
          the{' '}
          {canExport ? (
            <Link to="/compliance" className="font-medium text-primary hover:underline">
              Compliance
            </Link>
          ) : (
            <span className="font-medium text-foreground">Compliance</span>
          )}{' '}
          screen. This dashboard tracks the leading and lagging KRIs behind those filings.
        </p>
      </div>

      {/* Portfolio at a glance — top-line counts for the board/exec (aggregate, no case PII). */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiTile
          icon={<ShieldAlert className="size-4 text-severity-high" />}
          label="Open alerts"
          value={stats ? stats.open.toLocaleString('en-IN') : '—'}
        />
        <KpiTile
          icon={<TrendingUp className="size-4 text-severity-critical" />}
          label="High / critical"
          value={stats ? stats.high_critical.toLocaleString('en-IN') : '—'}
        />
        <KpiTile
          icon={<Timer className="size-4 text-sla-urgent" />}
          label="SLA at risk"
          value={stats ? stats.sla_at_risk.toLocaleString('en-IN') : '—'}
        />
        <KpiTile
          icon={<IndianRupee className="size-4 text-severity-high" />}
          label="Open exposure"
          value={stats ? formatINRCompact(stats.open_exposure_inr) : '—'}
        />
      </div>

      <QueryBoundary
        isLoading={krisQuery.isLoading}
        isError={krisQuery.isError}
        error={krisQuery.error}
        onRetry={() => void krisQuery.refetch()}
        skeleton={<ReportingSkeleton />}
      >
        {krisQuery.data ? <KriDashboard data={krisQuery.data} /> : null}
      </QueryBoundary>

      {alerts.length > 0 ? <AlertHeatmap alerts={alerts} /> : null}

      {/* Fraud-typology prevalence + confirmed-rate — which insider typologies actually fire. */}
      <TypologyAnalytics />
    </div>
  )
}

/** Read-only portfolio tile for the board/exec landing (no drill-through — this persona reads). */
function KpiTile({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          {icon}
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold tabular-nums">{value}</p>
      </CardContent>
    </Card>
  )
}
