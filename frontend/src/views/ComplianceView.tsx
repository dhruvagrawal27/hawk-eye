import {
  Eye,
  FileCheck2,
  Gauge,
  PenLine,
  Radar,
  ScaleIcon,
  ScrollText,
  ShieldCheck,
} from 'lucide-react'
import { useAuth } from '@/auth/rbac'
import { ROLE_META } from '@/auth/capabilities'
import type { Role } from '@/lib/types'
import { PageHeader } from '@/components/PageHeader'
import { RulesEditor } from '@/components/RulesEditor'
import { EwsCoverage } from '@/components/EwsCoverage'
import { RegulatoryExport } from '@/components/RegulatoryExport'
import { ApprovalQueue } from '@/components/ApprovalQueue'
import { DeptRollup } from '@/components/DeptRollup'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { RouteTransition } from '@/ui'

/**
 * Manager / executive oversight roles that see the Command center (approval queue + dept rollup)
 * embedded in the compliance console. A subset of the roles that already reach this screen.
 */
const COMMAND_CENTER_ROLES: Role[] = ['dgm_compliance', 'agm_vigilance']

/**
 * Compliance console (FRONTEND-12; blueprint Part 24.4 screen 5, l.956 + Part 11 reporting + Part 24.2
 * /rules & /reports). Three change-control surfaces for Compliance / Team-Lead roles only — no triage or
 * disposition controls live here:
 *   1. Rules &amp; thresholds — propose changes; four-eyes enforced server-side.
 *   2. EWS / RFA coverage — early-warning indicator coverage map (covered vs gap).
 *   3. Regulatory exports — CRILC + FMR draft generation and download.
 */
export function ComplianceView() {
  const { role, can, constraintFor } = useAuth()
  const roleLabel = role ? ROLE_META[role].short : undefined
  const showCommandCenter = role ? COMMAND_CENTER_ROLES.includes(role) : false

  // Four-eyes posture, made legible: whether *this* role may propose a rule change, and under what
  // constraint. Approval is a distinct, second-authoriser act enforced server-side — never the same
  // person who proposed. RBAC unchanged; this only narrates the gate the matrix already sets.
  const canPropose = can('tune_rules')
  const proposeConstraint = constraintFor('tune_rules')

  return (
    <RouteTransition className="space-y-4">
      <PageHeader
        icon={<ScaleIcon className="size-5" />}
        title="Compliance &amp; change control"
        description="Detection rules, EWS/RFA coverage, and regulatory exports. Rule changes are proposals subject to four-eyes approval; exports are drafts for review."
        actions={
          roleLabel ? (
            <Badge variant="secondary" className="gap-1">
              <ShieldCheck className="size-3.5" />
              {roleLabel}
            </Badge>
          ) : undefined
        }
      />

      {/* Four-eyes change-control explainer — propose ≠ approve, and approval is a Compliance act. */}
      <div className="flex flex-col gap-2 rounded-lg border border-tee/30 bg-tee/5 px-3.5 py-2.5 text-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-2.5">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-tee" />
          <p className="text-muted-foreground">
            <span className="font-medium text-foreground">Four-eyes change control.</span> Every
            rule edit is a <span className="font-medium text-foreground">proposal</span> — it stays
            pending until a{' '}
            <span className="font-medium text-foreground">second, different authoriser</span> in
            Compliance approves it. Nothing you change here goes live on your signature alone.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2 font-mono text-2xs">
          <span className="inline-flex items-center gap-1 rounded-md bg-reason-shap/10 px-2 py-1 uppercase tracking-widest text-reason-shap ring-1 ring-inset ring-reason-shap/25">
            <PenLine className="size-3" /> Propose
          </span>
          <ChevronArrow />
          <span className="inline-flex items-center gap-1 rounded-md bg-sla-ok/10 px-2 py-1 uppercase tracking-widest text-sla-ok ring-1 ring-inset ring-sla-ok/25">
            <Eye className="size-3" /> Approve · Compliance
          </span>
        </div>
      </div>

      {/* Whether *this* seat may propose — the matrix gate, spelled out (no widening). */}
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {canPropose ? (
          <>
            <PenLine className="size-3.5 text-reason-shap" />
            Your role can <span className="font-medium text-foreground">propose</span> rule changes
            {proposeConstraint ? (
              <span className="font-mono text-[0.7rem]"> ({proposeConstraint})</span>
            ) : null}{' '}
            — a second authoriser still approves.
          </>
        ) : (
          <>
            <Eye className="size-3.5" />
            Your role has <span className="font-medium text-foreground">read-only</span> access to
            rules — proposing and approving are reserved for change-control roles.
          </>
        )}
      </p>

      <Tabs defaultValue={showCommandCenter ? 'command' : 'rules'} className="space-y-3">
        <TabsList>
          {showCommandCenter ? (
            <TabsTrigger value="command">
              <Gauge className="size-3.5" />
              Command center
            </TabsTrigger>
          ) : null}
          <TabsTrigger value="rules">
            <ScrollText className="size-3.5" />
            Rules &amp; thresholds
          </TabsTrigger>
          <TabsTrigger value="coverage">
            <Radar className="size-3.5" />
            EWS / RFA coverage
          </TabsTrigger>
          <TabsTrigger value="exports">
            <FileCheck2 className="size-3.5" />
            Regulatory exports
          </TabsTrigger>
        </TabsList>

        {showCommandCenter ? (
          <TabsContent value="command">
            {/* Manager oversight — approval/escalation queue + department risk rollup (Agent B). */}
            <div className="grid gap-3 lg:grid-cols-2">
              <ApprovalQueue />
              <DeptRollup />
            </div>
          </TabsContent>
        ) : null}

        <TabsContent value="rules">
          <RulesEditor />
        </TabsContent>
        <TabsContent value="coverage">
          <EwsCoverage />
        </TabsContent>
        <TabsContent value="exports">
          <RegulatoryExport />
        </TabsContent>
      </Tabs>
    </RouteTransition>
  )
}

/** Tiny arrow between the propose → approve chips (decorative). */
function ChevronArrow() {
  return (
    <span className="text-muted-foreground/60" aria-hidden>
      →
    </span>
  )
}
