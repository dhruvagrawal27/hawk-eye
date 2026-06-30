import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ChevronRight, ListChecks, ScaleIcon, ArrowLeft, ShieldQuestion } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import type { Alert } from '@/lib/types'
import { QueryBoundary } from '@/components/QueryBoundary'
import { AlertHeader } from '@/components/AlertHeader'
import { Entity360Timeline } from '@/components/Entity360Timeline'
import { ExplanationPanel } from '@/components/ExplanationPanel'
import { GraphView } from '@/components/GraphView'
import { PeerComparison } from '@/components/PeerComparison'
import { EddActionPanel } from '@/components/EddActionPanel'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'

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
  return (
    <div className="space-y-4">
      <AlertHeader alert={alert} />

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
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <Tabs defaultValue="timeline" className="min-w-0">
          <TabsList className="flex-wrap">
            <TabsTrigger value="timeline">Timeline</TabsTrigger>
            <TabsTrigger value="explanation">Explanation</TabsTrigger>
            <TabsTrigger value="graph">Graph</TabsTrigger>
            <TabsTrigger value="peers">Peers</TabsTrigger>
          </TabsList>

          <TabsContent value="timeline">
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
      <Link
        to="/triage"
        className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground focus-ring"
      >
        <ArrowLeft className="size-3.5" />
        Back
      </Link>
    </div>
  )
}

function DetailSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-28 w-full rounded-lg" />
      <Skeleton className="h-10 w-full rounded-lg" />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <Skeleton className="h-80 w-full rounded-lg" />
        <Skeleton className="h-80 w-full rounded-lg" />
      </div>
    </div>
  )
}
