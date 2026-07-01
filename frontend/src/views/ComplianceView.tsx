import type { ReactNode } from 'react'
import { FileCheck2, Gauge, Info, Radar, ScaleIcon, ScrollText, ShieldCheck } from 'lucide-react'
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
        description="Your compliance control centre. Each tab is one job: Command center = decide the alerts that route to you; Rules & thresholds = propose change-controlled rule edits (four-eyes); EWS/RFA coverage = check RBI indicator coverage; Regulatory exports = generate draft returns for review. Nothing here is auto-filed or auto-actioned."
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
          <TabsContent value="command" className="space-y-3">
            <TabIntro>
              <strong className="text-foreground">Your job here:</strong> approve or reject the
              alerts and block-requests that route up to you, and see where risk is concentrated.
              Expand any queue row for the evidence and the person&apos;s history before you decide —
              approving permits containment; it never blocks money automatically.
            </TabIntro>
            {/* Manager oversight — approval/escalation queue + department risk rollup (Agent B). */}
            <div className="grid gap-3 lg:grid-cols-2">
              <ApprovalQueue />
              <DeptRollup />
            </div>
          </TabsContent>
        ) : null}

        <TabsContent value="rules" className="space-y-3">
          <TabIntro>
            <strong className="text-foreground">Your job here:</strong> propose and review changes to
            the detection rules and their thresholds. Every edit is a proposal that needs a second
            authoriser (four-eyes) before it goes live — nothing changes silently.
          </TabIntro>
          <RulesEditor />
        </TabsContent>
        <TabsContent value="coverage" className="space-y-3">
          <TabIntro>
            <strong className="text-foreground">Your job here:</strong> confirm every RBI
            early-warning (EWS) and red-flag (RFA) indicator maps to a live detection layer, and spot
            any gaps in coverage.
          </TabIntro>
          <EwsCoverage />
        </TabsContent>
        <TabsContent value="exports" className="space-y-3">
          <TabIntro>
            <strong className="text-foreground">Your job here:</strong> generate draft regulatory
            returns (CRILC, FMR) from confirmed cases and download them for review. These are drafts
            for a human — they are not filed with the regulator, and PII stays tokenized.
          </TabIntro>
          <RegulatoryExport />
        </TabsContent>
      </Tabs>
    </div>
  )
}

/** A short "what this tab is for" banner shown at the top of each compliance tab. */
function TabIntro({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
      <Info className="mt-0.5 size-4 shrink-0 text-primary/70" />
      <p>{children}</p>
    </div>
  )
}
