import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, ShieldAlert, Timer, TrendingUp } from 'lucide-react'
import { useAuth } from '@/auth/rbac'
import { ROLE_META } from '@/auth/capabilities'
import { navItemsForRole } from './nav-config'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { PageHeader } from '@/components/PageHeader'
import { LiveEventTape } from '@/components/realtime/LiveEventTape'
import { EventRateChart } from '@/components/charts/EventRateChart'
import { FusionSankey } from '@/components/FusionSankey'
import { SubThresholdPanel } from '@/components/SubThresholdPanel'
import { slaInfo, severityRank } from '@/lib/format'

/** Role-aware landing. Greets the user, surfaces their permitted screens, and (for triage roles)
 *  a live snapshot of the queue so the most urgent work is one click away. */
export function Dashboard() {
  const { user, role } = useAuth()
  const items = navItemsForRole(role).filter((i) => i.to !== '/')
  const canTriage = role
    ? ['relationship_manager', 'branch_manager', 'cluster_head', 'agm_vigilance'].includes(role)
    : false

  const alerts = useQuery({
    queryKey: queryKeys.alerts({}),
    queryFn: () => apiClient.listAlerts({}),
    enabled: canTriage,
  })

  // Portfolio counts come from the server (computed over ALL visible alerts), so the cards read at
  // true scale — the alert *list* is only a page, so counting its items would undercount.
  const stats = useQuery({
    queryKey: queryKeys.alertStats(),
    queryFn: () => apiClient.getAlertStats(),
    enabled: canTriage,
  })

  const pageOpen = (alerts.data?.items ?? []).filter((a) =>
    ['open', 'assigned', 'in_progress', 'escalated'].includes(a.status),
  )
  // Prefer the server-side totals; fall back to page-derived counts until stats load.
  const openCount = stats.data?.open ?? pageOpen.length
  const highCount =
    stats.data?.high_critical ?? pageOpen.filter((a) => severityRank[a.severity] >= 3).length
  const slaCount =
    stats.data?.sla_at_risk ??
    pageOpen.filter((a) => ['urgent', 'breached'].includes(slaInfo(a.sla_due_ts).state)).length
  // highest-risk open alert → the fusion-flow spotlight (shows our 6-layer fusion at a glance)
  const topAlert = [...pageOpen].sort((a, b) => b.risk_score - a.risk_score)[0]

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome, ${user?.name?.split(' ')[0] ?? 'Investigator'}`}
        description={role ? ROLE_META[role].description : undefined}
      />

      {canTriage ? (
        <div className="grid gap-3 sm:grid-cols-3">
          <StatCard
            icon={<ShieldAlert className="size-4 text-severity-high" />}
            label="Open alerts"
            value={openCount}
            to="/triage"
          />
          <StatCard
            icon={<TrendingUp className="size-4 text-severity-critical" />}
            label="High / critical"
            value={highCount}
            to="/triage"
          />
          <StatCard
            icon={<Timer className="size-4 text-sla-urgent" />}
            label="SLA at risk"
            value={slaCount}
            to="/triage"
          />
        </div>
      ) : null}

      {/* Live operations — realtime event tape + ingestion rate (study Phase 1). */}
      <div className="grid gap-3 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <LiveEventTape height={340} />
        </div>
        <EventRateChart height={120} />
      </div>

      {/* Fusion spotlight — the highest-risk open alert decomposed across our 6 detection layers. */}
      {canTriage && topAlert ? (
        <Link to={`/alerts/${topAlert.alert_id}`} className="block focus-ring rounded-lg">
          <FusionSankey
            alert={topAlert}
            height={180}
            className="transition-colors hover:border-primary/40"
          />
        </Link>
      ) : null}

      {/* Ambient activity — the 'hidden 95%': detection funnel + near-miss watchlist (scored < 70). */}
      <SubThresholdPanel />

      <div>
        <h2 className="mb-2 text-sm font-medium text-muted-foreground">Your screens</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => {
            const Icon = item.icon
            return (
              <Link key={item.to} to={item.to} className="group focus-ring rounded-lg">
                <Card className="h-full transition-colors group-hover:border-primary/50 group-hover:bg-accent/40">
                  <CardContent className="flex items-center gap-3 p-4">
                    <div className="flex size-9 items-center justify-center rounded-md bg-primary/10 text-primary">
                      <Icon className="size-4" />
                    </div>
                    <span className="flex-1 text-sm font-medium">{item.label}</span>
                    <ArrowRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                  </CardContent>
                </Card>
              </Link>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function StatCard({
  icon,
  label,
  value,
  to,
}: {
  icon: React.ReactNode
  label: string
  value: number
  to: string
}) {
  return (
    <Link to={to} className="focus-ring rounded-lg">
      <Card className="transition-colors hover:border-primary/50">
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
    </Link>
  )
}
