/**
 * Platform Admin view (FRONTEND-13; blueprint Part 24.4 screen 8 + Part 24.2 RBAC).
 *
 * The admin holds `admin` + `view_audit` + `train_models: deploy infra`, but **no case data**
 * (`view_alerts: ❌`). So this view is users/roles, rule-deployment posture, and system health — and
 * deliberately surfaces no alert/entity PII.
 *   - Users & roles: `listUsers()` table (roles rendered via ROLE_META) with a create-user dialog
 *     gated to `can('admin')` (createUser).
 *   - Rule deployment: a surface note clarifying that admins deploy approved rule artifacts but do
 *     not author or four-eyes-approve them (that is Compliance/Lead).
 *   - System health: `getHealth()` service list plus a sandboxed <GrafanaEmbed> ops dashboard.
 */
import { useMemo, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  CheckCircle2,
  CircleDot,
  GitBranch,
  Loader2,
  Plus,
  ServerCog,
  ShieldAlert,
  UserCog,
  Users,
} from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { formatIST, formatRelative } from '@/lib/format'
import { cn } from '@/lib/cn'
import { useAuth } from '@/auth/rbac'
import { ROLE_META, HUMAN_ROLES } from '@/auth/capabilities'
import type { Role } from '@/auth/capabilities'
import { PageHeader } from '@/components/PageHeader'
import { QueryBoundary } from '@/components/QueryBoundary'
import { GrafanaEmbed } from '@/components/GrafanaEmbed'
import { ServiceMap } from '@/components/ServiceMap'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { toast } from '@/components/ui/toaster'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { CountUp, RouteTransition } from '@/ui'
import type { AdminUser, CreateUserBody, ServiceHealth } from '@/lib/types'

const HEALTH_META: Record<ServiceHealth['status'], { icon: typeof CircleDot; className: string }> =
  {
    ok: { icon: CheckCircle2, className: 'text-sla-ok' },
    degraded: { icon: AlertCircle, className: 'text-sla-warn' },
    down: { icon: ShieldAlert, className: 'text-severity-critical' },
  }

function PanelSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-11 w-full" />
      ))}
    </div>
  )
}

export function AdminView() {
  const { can } = useAuth()
  const canAdmin = can('admin')

  const usersQuery = useQuery({ queryKey: queryKeys.users(), queryFn: () => apiClient.listUsers() })
  const healthQuery = useQuery({
    queryKey: queryKeys.health(),
    queryFn: () => apiClient.getHealth(),
  })

  const users = useMemo(() => usersQuery.data ?? [], [usersQuery.data])
  const health = healthQuery.data

  // Aggregate posture counts, derived from the existing queries (no new API surface).
  const activeUsers = users.filter((u) => u.status === 'active').length
  const services = health?.services ?? []
  const servicesOk = services.filter((s) => s.status === 'ok').length

  return (
    <RouteTransition className="space-y-4">
      <PageHeader
        icon={<ServerCog className="size-5" />}
        title="Platform administration"
        description="Users & roles, rule deployment, and system health. No case data is shown here."
        actions={<CreateUserDialog disabled={!canAdmin} />}
      />

      {/* No-case-data banner */}
      <div className="flex items-start gap-2.5 rounded-lg border border-border bg-muted/40 px-3.5 py-2.5 text-sm">
        <ShieldAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">No case access.</span> The Platform Admin
          role manages identities and infrastructure but cannot view alerts, entities, or PII. Every
          admin action below is itself written to the audit trail.
        </p>
      </div>

      {/* Aggregate posture — roll-up counts (no PII), rolled up on load. */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SummaryStat
          icon={<Users className="size-3.5" />}
          label="Provisioned users"
          value={users.length}
        />
        <SummaryStat icon={<UserCog className="size-3.5" />} label="Active" value={activeUsers} />
        <SummaryStat
          icon={<ServerCog className="size-3.5" />}
          label="Services healthy"
          value={servicesOk}
        />
        <SummaryStat
          icon={<CheckCircle2 className="size-3.5" />}
          label="Services checked"
          value={services.length}
        />
      </div>

      {/* Users & roles */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <Users className="size-4 text-muted-foreground" /> Users & roles
          </CardTitle>
          <CardDescription>
            Identities provisioned in Keycloak. Roles map to the Part 24.1 RBAC matrix.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <QueryBoundary
            isLoading={usersQuery.isLoading}
            isError={usersQuery.isError}
            error={usersQuery.error}
            onRetry={() => void usersQuery.refetch()}
            skeleton={
              <div className="p-4">
                <PanelSkeleton rows={6} />
              </div>
            }
          >
            {users.length === 0 ? (
              <div className="p-4">
                <EmptyState icon={Users} title="No users provisioned" />
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="min-w-[12rem]">User</TableHead>
                    <TableHead>Username</TableHead>
                    <TableHead>Roles</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Last login</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((u) => (
                    <UserRow key={u.id} user={u} />
                  ))}
                </TableBody>
              </Table>
            )}
          </QueryBoundary>
        </CardContent>
      </Card>

      {/* Rule deployment surface note */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="size-4 text-muted-foreground" /> Rule deployment
          </CardTitle>
          <CardDescription>Infrastructure posture for the detection rule estate.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            Admins{' '}
            <span className="font-medium text-foreground">deploy approved rule artifacts</span>{' '}
            (CI/CD pipeline → rule engine), but never author or approve them. Rule authoring is
            Compliance; four-eyes approval is the Team Lead. Every promotion is change-controlled
            and audited — there is no path here to enable or silence a rule directly.
          </p>
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <Badge variant="outline" className="gap-1.5">
              <CheckCircle2 className="size-3.5 text-sla-ok" /> Pipeline healthy
            </Badge>
            <Badge variant="outline" className="gap-1.5">
              <GitBranch className="size-3.5" /> Change-controlled (four-eyes upstream)
            </Badge>
            <Badge variant="muted">No direct enable/disable from Admin</Badge>
          </div>
        </CardContent>
      </Card>

      {/* System health */}
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-2 space-y-0 pb-2">
          <div>
            <CardTitle className="flex items-center gap-2">
              <ServerCog className="size-4 text-muted-foreground" /> System health
            </CardTitle>
            <CardDescription>
              {health?.checked_ts
                ? `Last checked ${formatIST(health.checked_ts)}${health.version ? ` · v${health.version}` : ''}`
                : 'Live service status across the platform.'}
            </CardDescription>
          </div>
          {health ? <OverallHealthBadge status={health.status} /> : null}
        </CardHeader>
        <CardContent>
          <QueryBoundary
            isLoading={healthQuery.isLoading}
            isError={healthQuery.isError}
            error={healthQuery.error}
            onRetry={() => void healthQuery.refetch()}
            skeleton={<PanelSkeleton rows={4} />}
          >
            {!health || health.services.length === 0 ? (
              <EmptyState icon={ServerCog} title="No health data" />
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {health.services.map((s) => (
                  <ServiceRow key={s.name} service={s} />
                ))}
              </div>
            )}
          </QueryBoundary>
        </CardContent>
      </Card>

      {/* Service map — every platform service, where it's used, and live status */}
      <ServiceMap />

      {/* Grafana ops dashboard */}
      <GrafanaEmbed title="Operations dashboard (Grafana)" />
    </RouteTransition>
  )
}

/** A small aggregate-count tile — evidence figure animates up via CountUp (reduced-motion → instant). */
function SummaryStat({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border bg-card px-3.5 py-2.5">
      <p className="flex items-center gap-1.5 text-2xs uppercase tracking-widest text-muted-foreground">
        <span className="text-muted-foreground">{icon}</span>
        {label}
      </p>
      <CountUp
        value={value}
        className="mt-1 block font-mono text-2xl font-semibold text-foreground"
      />
    </div>
  )
}

function OverallHealthBadge({ status }: { status: ServiceHealth['status'] }) {
  const meta = HEALTH_META[status]
  const Icon = meta.icon
  const label =
    status === 'ok' ? 'All systems operational' : status === 'degraded' ? 'Degraded' : 'Outage'
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-xs font-medium', meta.className)}>
      <Icon className="size-4" />
      {label}
    </span>
  )
}

function ServiceRow({ service }: { service: ServiceHealth }) {
  const meta = HEALTH_META[service.status]
  const Icon = meta.icon
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-background/40 px-3 py-2">
      <div className="flex min-w-0 items-center gap-2">
        <Icon className={cn('size-4 shrink-0', meta.className)} />
        <div className="min-w-0">
          <p className="truncate text-sm">{service.name}</p>
          {service.detail ? (
            <p className="truncate text-[0.7rem] text-muted-foreground">{service.detail}</p>
          ) : null}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {service.latency_ms != null ? (
          <span className="font-mono text-xs tabular-nums text-muted-foreground">
            {service.latency_ms} ms
          </span>
        ) : null}
        <Badge
          variant={
            service.status === 'ok'
              ? 'success'
              : service.status === 'degraded'
                ? 'warning'
                : 'destructive'
          }
          className="uppercase"
        >
          {service.status}
        </Badge>
      </div>
    </div>
  )
}

function UserRow({ user }: { user: AdminUser }) {
  return (
    <TableRow>
      <TableCell>
        <div className="flex items-center gap-2">
          <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted">
            <UserCog className="size-3.5 text-muted-foreground" />
          </span>
          <div>
            <p className="font-medium">{user.display_name}</p>
            {user.email ? (
              <p className="text-[0.7rem] text-muted-foreground">{user.email}</p>
            ) : null}
          </div>
        </div>
      </TableCell>
      <TableCell className="font-mono text-xs">{user.username}</TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {user.roles.map((r) => (
            <Badge key={r} variant="secondary" title={ROLE_META[r].description}>
              {ROLE_META[r].short}
            </Badge>
          ))}
        </div>
      </TableCell>
      <TableCell>
        <Badge variant={user.status === 'active' ? 'success' : 'muted'} className="uppercase">
          {user.status}
        </Badge>
      </TableCell>
      <TableCell className="text-right text-xs tabular-nums text-muted-foreground">
        {user.last_login ? formatRelative(user.last_login) : 'never'}
      </TableCell>
    </TableRow>
  )
}

const EMPTY_FORM: CreateUserBody = { username: '', display_name: '', email: '', roles: [] }

function CreateUserDialog({ disabled }: { disabled: boolean }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState<CreateUserBody>(EMPTY_FORM)

  const createUser = useMutation({
    mutationFn: (body: CreateUserBody) => apiClient.createUser(body),
    onSuccess: (created) => {
      toast.success('User provisioned', {
        description: `${created.display_name} · ${created.username}`,
      })
      void queryClient.invalidateQueries({ queryKey: queryKeys.users() })
      setForm(EMPTY_FORM)
      setOpen(false)
    },
    onError: () => toast.error('Could not provision user'),
  })

  const valid =
    form.username.trim().length > 0 && form.display_name.trim().length > 0 && form.roles.length > 0

  function toggleRole(role: Role, checked: boolean) {
    setForm((f) => ({
      ...f,
      roles: checked ? [...f.roles, role] : f.roles.filter((r) => r !== role),
    }))
  }

  if (disabled) {
    return (
      <Button disabled title="Requires the Admin capability">
        <Plus className="size-4" /> New user
      </Button>
    )
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="size-4" /> New user
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Provision user</DialogTitle>
          <DialogDescription>
            Creates a Keycloak identity with the selected roles. This action is audited.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="new-username">Username</Label>
              <Input
                id="new-username"
                placeholder="firstname.lastname"
                value={form.username}
                onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="new-display">Display name</Label>
              <Input
                id="new-display"
                placeholder="First Last"
                value={form.display_name}
                onChange={(e) => setForm((f) => ({ ...f, display_name: e.target.value }))}
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="new-email">Email (optional)</Label>
            <Input
              id="new-email"
              type="email"
              placeholder="name@bank.local"
              value={form.email ?? ''}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Roles</Label>
            <div className="grid grid-cols-2 gap-1.5 rounded-md border border-border p-2.5">
              {HUMAN_ROLES.map((role) => {
                const checked = form.roles.includes(role)
                return (
                  <label
                    key={role}
                    className="flex cursor-pointer items-center gap-2 rounded px-1.5 py-1 text-sm hover:bg-muted/50"
                  >
                    <Checkbox
                      checked={checked}
                      onCheckedChange={(v) => toggleRole(role, v === true)}
                    />
                    <span>{ROLE_META[role].short}</span>
                  </label>
                )
              })}
            </div>
            <p className="text-[0.7rem] text-muted-foreground">
              Roles grant capabilities via the RBAC matrix. Combining roles is subject to
              separation-of-duties checks server-side.
            </p>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            disabled={!valid || createUser.isPending}
            onClick={() =>
              createUser.mutate({
                username: form.username.trim(),
                display_name: form.display_name.trim(),
                email: form.email?.trim() || undefined,
                roles: form.roles,
              })
            }
          >
            {createUser.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Plus className="size-4" />
            )}
            Provision
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
