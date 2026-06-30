import { FileCheck2, Gauge, Radar, ScaleIcon, ScrollText, ShieldCheck } from 'lucide-react'
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
  const { role } = useAuth()
  const roleLabel = role ? ROLE_META[role].short : undefined
  const showCommandCenter = role ? COMMAND_CENTER_ROLES.includes(role) : false

  return (
    <div className="space-y-4">
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
    </div>
  )
}
