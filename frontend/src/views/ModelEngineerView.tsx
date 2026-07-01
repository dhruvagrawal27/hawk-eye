/**
 * Model Engineer view (FRONTEND-13; blueprint Part 24.4 screen 7 + Part 24.2 RBAC).
 *
 * Three panels against de-identified model telemetry only (the data_science_lead role is
 * `view_alerts: de-identified only`, `train_models: with sign-off`, and crucially **cannot**
 * disposition/triage — SoD, Part 19.6):
 *   - Registry: champion / challenger entries with stage badge, signed flag, and quality metrics.
 *   - Drift: <DriftChart> per series with thresholds and ok/warning/drifting status.
 *   - Model quality: a compact metrics table (AUC, PR-AUC, precision/recall/F1, FPR, Brier).
 *
 * Promotion is a **request that requires sign-off** — gated to `can('train_models')`, never an
 * auto-deploy. A persistent banner reinforces that no case PII is ever shown here.
 */
import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  BadgeCheck,
  Boxes,
  CheckCircle2,
  CircleSlash,
  FlaskConical,
  Loader2,
  ShieldQuestion,
  TrendingUp,
  Upload,
} from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { formatISTDate, formatPercent, layerLabel } from '@/lib/format'
import { useAuth } from '@/auth/rbac'
import { PageHeader } from '@/components/PageHeader'
import { QueryBoundary } from '@/components/QueryBoundary'
import { DriftChart } from '@/components/DriftChart'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/ui/empty-state'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { toast } from '@/components/ui/toaster'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { CountUp, RouteTransition } from '@/ui'
import type { ModelEntry, ModelMetrics, ModelStage } from '@/lib/types'

const STAGE_VARIANT: Record<ModelStage, Parameters<typeof Badge>[0]['variant']> = {
  champion: 'success',
  challenger: 'default',
  staging: 'warning',
  archived: 'muted',
}

const METRIC_COLUMNS: { key: keyof ModelMetrics; label: string; kind: 'pct' | 'ratio' }[] = [
  { key: 'auc', label: 'AUC', kind: 'ratio' },
  { key: 'pr_auc', label: 'PR-AUC', kind: 'ratio' },
  { key: 'precision_at_k', label: 'P@K', kind: 'ratio' },
  { key: 'precision', label: 'Precision', kind: 'ratio' },
  { key: 'recall', label: 'Recall', kind: 'ratio' },
  { key: 'f1', label: 'F1', kind: 'ratio' },
  { key: 'fpr', label: 'FPR', kind: 'pct' },
  { key: 'calibration_error', label: 'Cal. err', kind: 'ratio' },
  { key: 'brier', label: 'Brier', kind: 'ratio' },
]

function metricText(value: number | undefined, kind: 'pct' | 'ratio'): string {
  if (value == null) return '—'
  return kind === 'pct' ? formatPercent(value, 1) : value.toFixed(3)
}

/**
 * Animated metric cell — rolls the number up on mount/refresh (CountUp, reduced-motion → instant),
 * formatting to match `metricText`. A missing metric renders an explicit em-dash, never a blank.
 */
function MetricValue({
  value,
  kind,
  className,
}: {
  value: number | undefined
  kind: 'pct' | 'ratio'
  className?: string
}) {
  if (value == null) return <span className={className}>—</span>
  // A custom formatter matches metricText exactly, so `decimals` is unused; format wins in CountUp.
  return <CountUp value={value} className={className} format={(n) => metricText(n, kind)} />
}

function PanelSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  )
}

export function ModelEngineerView() {
  const { can, constraintFor, user } = useAuth()
  const queryClient = useQueryClient()
  const canPromote = can('train_models')
  const promoteConstraint = constraintFor('train_models')
  const [promoting, setPromoting] = useState<ModelEntry | null>(null)

  const modelsQuery = useQuery({
    queryKey: queryKeys.models(),
    queryFn: () => apiClient.listModels(),
  })
  const driftQuery = useQuery({ queryKey: queryKeys.drift(), queryFn: () => apiClient.getDrift() })
  const qualityQuery = useQuery({
    queryKey: queryKeys.modelMetrics(),
    queryFn: () => apiClient.getModelMetrics(),
  })

  const models = useMemo(() => modelsQuery.data ?? [], [modelsQuery.data])
  const modelName = useMemo(() => {
    const map = new Map<string, string>()
    for (const m of models) map.set(m.id, m.name)
    return map
  }, [models])

  const promote = useMutation({
    mutationFn: (args: { model: ModelEntry; signoffBy: string }) =>
      apiClient.promoteModel(args.model.id, {
        version: args.model.version,
        toStage: 'Production',
        signoffBy: args.signoffBy,
      }),
    onSuccess: (res) => {
      toast.success('Promotion request submitted', {
        description: res.requires_signoff
          ? `Routed for sign-off before deploy · ${res.audit_id}`
          : `Recorded · ${res.audit_id}`,
      })
      setPromoting(null)
      void queryClient.invalidateQueries({ queryKey: queryKeys.models() })
    },
    onError: (err) =>
      toast.error('Promotion request failed', {
        description: err instanceof Error ? err.message : undefined,
      }),
  })

  return (
    <RouteTransition className="space-y-4">
      <PageHeader
        icon={<Boxes className="size-5" />}
        title="Model registry & drift"
        description="Champion / challenger models, population drift, and quality metrics across L1–L6."
        actions={
          <Badge variant="outline" className="gap-1.5">
            <ShieldQuestion className="size-3.5" /> De-identified telemetry
          </Badge>
        }
      />

      {/* De-identified-only banner */}
      <div className="flex items-start gap-2.5 rounded-lg border border-reason-shap/30 bg-reason-shap/5 px-3.5 py-2.5 text-sm">
        <ShieldQuestion className="mt-0.5 size-4 shrink-0 text-reason-shap" />
        <p className="text-muted-foreground">
          <span className="font-medium text-foreground">De-identified data only.</span> This surface
          shows model metadata, drift, and aggregate quality — never case PII. Labels and
          dispositions are made by investigators, not here (separation of duties, Part 19.6).
        </p>
      </div>

      {/* Registry */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <Boxes className="size-4 text-muted-foreground" /> Model registry
          </CardTitle>
          <CardDescription>
            Champion is live; challengers shadow it. Promotion requires a signed artifact and
            sign-off.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <QueryBoundary
            isLoading={modelsQuery.isLoading}
            isError={modelsQuery.isError}
            error={modelsQuery.error}
            onRetry={() => void modelsQuery.refetch()}
            skeleton={<PanelSkeleton rows={6} />}
          >
            {models.length === 0 ? (
              <EmptyState icon={Boxes} title="No models registered" />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="min-w-[14rem]">Model</TableHead>
                    <TableHead>Layer</TableHead>
                    <TableHead>Stage</TableHead>
                    <TableHead>Signed</TableHead>
                    <TableHead className="text-right">AUC</TableHead>
                    <TableHead className="text-right">PR-AUC</TableHead>
                    <TableHead className="text-right">FPR</TableHead>
                    <TableHead>Registered</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {models.map((m) => (
                    <ModelRow
                      key={m.id}
                      model={m}
                      canPromote={canPromote}
                      promoteConstraint={promoteConstraint}
                      isPromoting={promote.isPending && promoting?.id === m.id}
                      onPromote={() => setPromoting(m)}
                    />
                  ))}
                </TableBody>
              </Table>
            )}
          </QueryBoundary>
        </CardContent>
      </Card>

      {/* Drift */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="size-4 text-muted-foreground" /> Population & score drift
          </CardTitle>
          <CardDescription>
            PSI / KS / JS per feature against alert thresholds. Drifting series flag a retrain
            review.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <QueryBoundary
            isLoading={driftQuery.isLoading}
            isError={driftQuery.isError}
            error={driftQuery.error}
            onRetry={() => void driftQuery.refetch()}
            skeleton={<PanelSkeleton rows={2} />}
          >
            <DriftChart series={driftQuery.data?.series ?? []} />
          </QueryBoundary>
        </CardContent>
      </Card>

      {/* Model quality */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <FlaskConical className="size-4 text-muted-foreground" /> Model quality
          </CardTitle>
          <CardDescription>
            Offline evaluation metrics per model — the evidence behind any promotion decision.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <QueryBoundary
            isLoading={qualityQuery.isLoading}
            isError={qualityQuery.isError}
            error={qualityQuery.error}
            onRetry={() => void qualityQuery.refetch()}
            skeleton={<PanelSkeleton rows={5} />}
          >
            {!qualityQuery.data?.models || qualityQuery.data.models.length === 0 ? (
              <EmptyState icon={FlaskConical} title="No quality metrics" />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="min-w-[12rem]">Model</TableHead>
                    {METRIC_COLUMNS.map((c) => (
                      <TableHead key={c.key} className="text-right">
                        {c.label}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {qualityQuery.data.models.map((row) => (
                    <TableRow key={row.model_id}>
                      <TableCell>
                        <span className="font-medium">
                          {modelName.get(row.model_id) ?? row.model_id}
                        </span>
                        <span className="ml-2 font-mono text-[0.7rem] text-muted-foreground">
                          {row.model_id}
                        </span>
                      </TableCell>
                      {METRIC_COLUMNS.map((c) => (
                        <TableCell key={c.key} className="text-right font-mono tabular-nums">
                          <MetricValue value={(row.metrics ?? {})[c.key]} kind={c.kind} />
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </QueryBoundary>
        </CardContent>
      </Card>

      <PromoteDialog
        model={promoting}
        requesterId={user?.sub ?? ''}
        isPending={promote.isPending}
        onOpenChange={(open) => {
          if (!open) setPromoting(null)
        }}
        onConfirm={(signoffBy) => {
          if (promoting) promote.mutate({ model: promoting, signoffBy })
        }}
      />
    </RouteTransition>
  )
}

/**
 * Second-person sign-off dialog. Promotion is SoD-gated server-side: the approver (`signoff_by`)
 * must differ from the requester. We collect that approver here rather than auto-deploying.
 */
function PromoteDialog({
  model,
  requesterId,
  isPending,
  onOpenChange,
  onConfirm,
}: {
  model: ModelEntry | null
  requesterId: string
  isPending: boolean
  onOpenChange: (open: boolean) => void
  onConfirm: (signoffBy: string) => void
}) {
  const [signoffBy, setSignoffBy] = useState('')
  // Reset the field whenever a different model is targeted.
  const key = model?.id ?? ''
  const [lastKey, setLastKey] = useState(key)
  if (key !== lastKey) {
    setLastKey(key)
    setSignoffBy('')
  }
  const trimmed = signoffBy.trim()
  const distinct = trimmed.length > 0 && trimmed !== requesterId
  return (
    <Dialog open={model != null} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Request promotion — sign-off required</DialogTitle>
          <DialogDescription>
            Promoting <span className="font-medium text-foreground">{model?.name}</span> (
            <span className="font-mono text-xs">{model?.id}</span> · v{model?.version}) to
            Production. This routes for a second-person sign-off and is never an auto-deploy.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-1.5">
          <Label htmlFor="signoff-by">Second-person approver (sign-off)</Label>
          <Input
            id="signoff-by"
            placeholder="e.g. EMP-ds01"
            value={signoffBy}
            onChange={(e) => setSignoffBy(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && distinct && onConfirm(trimmed)}
          />
          <p className="text-[0.7rem] text-muted-foreground">
            Separation of duties: the approver must differ from you
            {requesterId ? ` (${requesterId})` : ''}.
          </p>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button disabled={!distinct || isPending} onClick={() => onConfirm(trimmed)}>
            {isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Upload className="size-4" />
            )}
            Request promotion
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ModelRow({
  model,
  canPromote,
  promoteConstraint,
  isPromoting,
  onPromote,
}: {
  model: ModelEntry
  canPromote: boolean
  promoteConstraint?: string
  isPromoting: boolean
  onPromote: () => void
}) {
  const metrics = model.metrics ?? {}
  const isChampion = model.stage === 'champion'
  // Only non-champion, signed models are sensible promotion candidates.
  const promotable = canPromote && !isChampion
  const blockReason = isChampion
    ? 'Already the live champion.'
    : !model.signed
      ? 'Artifact is not signed — sign before requesting promotion.'
      : undefined

  return (
    <TableRow>
      <TableCell>
        <div className="flex flex-col">
          <span className="font-medium">{model.name}</span>
          <span className="font-mono text-[0.7rem] text-muted-foreground">
            {model.id} · v{model.version}
          </span>
        </div>
      </TableCell>
      <TableCell>
        <span className="rounded bg-secondary px-1.5 py-0.5 font-mono text-[0.7rem] text-secondary-foreground">
          {layerLabel(model.layer)}
        </span>
      </TableCell>
      <TableCell>
        <Badge variant={STAGE_VARIANT[model.stage]} className="uppercase">
          {model.stage}
        </Badge>
      </TableCell>
      <TableCell>
        {model.signed ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-flex items-center gap-1 text-xs text-tee">
                <BadgeCheck className="size-3.5" /> Signed
              </span>
            </TooltipTrigger>
            <TooltipContent>Model artifact is cryptographically signed.</TooltipContent>
          </Tooltip>
        ) : (
          <span className="inline-flex items-center gap-1 text-xs text-severity-medium">
            <CircleSlash className="size-3.5" /> Unsigned
          </span>
        )}
      </TableCell>
      <TableCell className="text-right tabular-nums">{metricText(metrics.auc, 'ratio')}</TableCell>
      <TableCell className="text-right tabular-nums">
        {metricText(metrics.pr_auc, 'ratio')}
      </TableCell>
      <TableCell className="text-right tabular-nums">{metricText(metrics.fpr, 'pct')}</TableCell>
      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
        {formatISTDate(model.created_ts)}
      </TableCell>
      <TableCell className="text-right">
        {isChampion ? (
          <span className="inline-flex items-center gap-1 text-xs text-sla-ok">
            <CheckCircle2 className="size-3.5" /> Live
          </span>
        ) : canPromote ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-block">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!promotable || !model.signed || isPromoting}
                  onClick={onPromote}
                >
                  {isPromoting ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <Upload className="size-3.5" />
                  )}
                  Request promotion
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>
              {blockReason ??
                `Routes for sign-off before deploy${promoteConstraint ? ` (${promoteConstraint})` : ''} — never an auto-deploy.`}
            </TooltipContent>
          </Tooltip>
        ) : (
          <span className="text-xs text-muted-foreground">Requires sign-off role</span>
        )}
      </TableCell>
    </TableRow>
  )
}
