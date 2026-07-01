import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ChevronRight, ListChecks, ScaleIcon, ArrowLeft, ShieldQuestion } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import type { Alert } from '@/lib/types'
import { QueryBoundary } from '@/components/QueryBoundary'
import { AlertHeader } from '@/components/AlertHeader'
import { LayerWaterfall } from '@/components/LayerWaterfall'
import { FusionSankey } from '@/components/FusionSankey'
import { RiskIndexGauge } from '@/components/RiskIndexGauge'
import { Entity360Timeline } from '@/components/Entity360Timeline'
import { AlertHeatmap } from '@/components/AlertHeatmap'
import { ScoreOverTime } from '@/components/ScoreOverTime'
import { ExplanationPanel } from '@/components/ExplanationPanel'
import { GraphView } from '@/components/GraphView'
import { PeerComparison } from '@/components/PeerComparison'
import { EddActionPanel } from '@/components/EddActionPanel'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { AlertReportButton } from '@/features/reports/AlertReportButton'

/**
 * Alert/case detail — the investigation workhorse (blueprint Part 24.4 screen 3). Header carries the
 * risk posture; the tabbed left column is the evidence (timeline · explanation · graph · peers); the
 * right rail is the only place a human acts. Natural justice: the machine explains, the human decides.
 */
export function AlertDetail() {
  const { alertId = '' } = useParams<{ alertId: string }>()

  const query = useQuery({
    queryKey: queryKeys.alert(alertId),
    queryFn: () => apiClient.getAlert(alertId),
    enabled: alertId.length > 0,
  })

  return (
    <div className="space-y-4">
      <Breadcrumb alertId={alertId} />

      <QueryBoundary
        isLoading={query.isLoading}
        isError={query.isError}
        error={query.error}
        onRetry={() => void query.refetch()}
        skeleton={<DetailSkeleton />}
      >
        {query.data ? (
          <AlertDetailBody alert={query.data} />
        ) : (
          <EmptyState
            icon={ShieldQuestion}
            title="Alert not found"
            description="This alert may have been closed or you may not have access to its case data."
            action={
              <Link
                to="/triage"
                className="text-sm font-medium text-primary underline-offset-4 hover:underline"
              >
                Back to triage queue
              </Link>
            }
          />
        )}
      </QueryBoundary>
    </div>
  )
}

function AlertDetailBody({ alert }: { alert: Alert }) {
  // Reuse the existing alert list to plot this entity's alerts by IST day/hour. The current alert is
  // always included so the heatmap shows a signal even before the wider list resolves.
  const entityAlertsQuery = useQuery({
    queryKey: queryKeys.alerts({ page_size: 200 }),
    queryFn: () => apiClient.listAlerts({ page_size: 200 }),
  })
  const entityAlerts = useMemo(() => {
    const others = (entityAlertsQuery.data?.items ?? []).filter(
      (a) => a.entity_id === alert.entity_id && a.alert_id !== alert.alert_id,
    )
    return [alert, ...others]
  }, [entityAlertsQuery.data, alert])

  return (
    <div className="space-y-4">
      <AlertHeader alert={alert} />

      {/* Standing per-user insider-risk index (M2.1) — the actor's baseline posture next to this
          alert's point-in-time score. Renders only when the entity has an index. Alert-only. */}
      <RiskIndexGauge entityId={alert.entity_id} />

      {/* Six-layer detection fusion — the headline "how this score was built" across L1→L6
          (our differentiator vs a 3-stream blend): the waterfall decomposes it, the Sankey shows
          the layers merging into the fused score. */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <LayerWaterfall alert={alert} />
        <FusionSankey alert={alert} />
      </div>

      {/* Natural-justice posture — set expectations before any action is taken. */}
      <div className="flex items-start gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
        <ShieldQuestion className="mt-0.5 size-4 shrink-0 text-primary" />
        <p>
          This is an <span className="font-medium text-foreground">alert, not a verdict</span>. The
          evidence below explains why the system surfaced this entity — score and reason codes come
          from layers L1–L6. No action is taken automatically; a human must review the explanation
          and decide. Block is a <span className="font-medium text-foreground">request</span> routed
          to a Lead for approval.
        </p>
      </div>

      {/* Evidence (tabs) + action rail (always visible). */}
      <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <Tabs defaultValue="timeline" className="min-w-0">
          <TabsList className="flex-wrap">
            <TabsTrigger value="timeline">Timeline</TabsTrigger>
            <TabsTrigger value="explanation">Explanation</TabsTrigger>
            <TabsTrigger value="graph">Graph</TabsTrigger>
            <TabsTrigger value="peers">Peers</TabsTrigger>
          </TabsList>

          <TabsContent value="timeline" className="space-y-4">
            <PanelCard>
              <ScoreOverTime entityId={alert.entity_id} />
            </PanelCard>
            <AlertHeatmap alerts={entityAlerts} />
            <PanelCard>
              <Entity360Timeline entityId={alert.entity_id} alertId={alert.alert_id} />
            </PanelCard>
          </TabsContent>

          <TabsContent value="explanation">
            <PanelCard>
              <ExplanationPanel alertId={alert.alert_id} />
            </PanelCard>
          </TabsContent>

          <TabsContent value="graph">
            <PanelCard>
              <GraphView entityId={alert.entity_id} />
            </PanelCard>
          </TabsContent>

          <TabsContent value="peers">
            <PanelCard>
              <PeerComparison entityId={alert.entity_id} />
            </PanelCard>
          </TabsContent>
        </Tabs>

        {/* Action & EDD rail — sticky so it stays in reach while scrolling evidence. */}
        <aside className="xl:sticky xl:top-4 xl:self-start">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            <ScaleIcon className="size-3.5" />
            Action &amp; EDD
          </div>
          <EddActionPanel alert={alert} />
        </aside>
      </div>
    </div>
  )
}

function PanelCard({ children }: { children: React.ReactNode }) {
  return (
    <Card>
      <CardContent className="p-4">{children}</CardContent>
    </Card>
  )
}

function Breadcrumb({ alertId }: { alertId: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <nav
        aria-label="Breadcrumb"
        className="flex items-center gap-1.5 text-xs text-muted-foreground"
      >
        <Link
          to="/triage"
          className="inline-flex items-center gap-1 hover:text-foreground focus-ring"
        >
          <ListChecks className="size-3.5" />
          Triage queue
        </Link>
        <ChevronRight className="size-3.5 opacity-60" aria-hidden />
        <span className="font-mono tabular-nums text-foreground">{alertId || 'Alert'}</span>
      </nav>
      <div className="flex items-center gap-2">
        <AlertReportButton alertId={alertId} />
        <Link
          to="/triage"
          className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground focus-ring"
        >
          <ArrowLeft className="size-3.5" />
          Back
        </Link>
      </div>
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-28 w-full rounded-lg" />
      <Skeleton className="h-10 w-full rounded-lg" />
      <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <Skeleton className="h-80 w-full rounded-lg" />
        <Skeleton className="h-80 w-full rounded-lg" />
      </div>
    </div>
  )
}
