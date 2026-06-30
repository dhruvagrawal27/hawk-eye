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
import { slaInfo, severityRank } from '@/lib/format'

/** Role-aware landing. Greets the user, surfaces their permitted screens, and (for triage roles)
 *  a live snapshot of the queue so the most urgent work is one click away. */
export function Dashboard() {
  const { user, role } = useAuth()
  const items = navItemsForRole(role).filter((i) => i.to !== '/')
  const canTriage = role ? ['analyst', 'senior_investigator', 'team_lead'].includes(role) : false

  const alerts = useQuery({
    queryKey: queryKeys.alerts({}),
    queryFn: () => apiClient.listAlerts({}),
    enabled: canTriage,
  })

  const open = (alerts.data?.items ?? []).filter((a) =>
    ['open', 'assigned', 'in_progress', 'escalated'].includes(a.status),
  )
  const highSeverity = open.filter((a) => severityRank[a.severity] >= 3).length
  const slaAtRisk = open.filter((a) =>
    ['urgent', 'breached'].includes(slaInfo(a.sla_due_ts).state),
  ).length

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
            value={open.length}
            to="/triage"
          />
          <StatCard
            icon={<TrendingUp className="size-4 text-severity-critical" />}
            label="High / critical"
            value={highSeverity}
            to="/triage"
          />
          <StatCard
            icon={<Timer className="size-4 text-sla-urgent" />}
            label="SLA at risk"
            value={slaAtRisk}
            to="/triage"
          />
        </div>
      ) : null}

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
