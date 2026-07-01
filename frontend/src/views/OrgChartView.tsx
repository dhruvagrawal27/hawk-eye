/**
 * Org-chart view (blueprint Part 24.4; docs/BANK_ROLES.md "Org-chart view").
 *
 * A **read-only** rendering of the console RBAC reporting tree, derived entirely from `ROLE_META`
 * (org-chart placement) and the capability matrix (`can()`), grouped by the RBI **Three Lines of
 * Defense** plus the Board/Exec and IT tiers. Each role is a card showing its label, short-code,
 * tier, department, and a one-line capability summary (the capabilities it may use, derived live so
 * the card can never drift from the FROZEN matrix). This screen mutates nothing — it documents the
 * org chart that the route guards enforce elsewhere.
 *
 * Note: this is the *console/RBAC* axis (who uses the fraud console). The actor/subject roles in the
 * monitored employee population (ops_maker, ops_checker, …) are a different axis and not shown here.
 */
import { GitBranch, Network, ShieldCheck } from 'lucide-react'
import { ROLE_META, HUMAN_ROLES, can, CAPABILITIES, CAPABILITY_LABELS } from '@/auth/capabilities'
import type { Role, Capability } from '@/auth/capabilities'
import { PageHeader } from '@/components/PageHeader'
import { Surface } from '@/components/ui/surface'
import { Eyebrow } from '@/components/ui/eyebrow'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { RouteTransition, m, staggerParent, staggerItem } from '@/ui'

/**
 * The chart sections, top-to-bottom. The three Lines of Defense come first (1st = ownership /
 * investigation, 2nd = risk & compliance oversight, 3rd = independent assurance), then the
 * Board/Exec tier, then IT/Platform. `service_account` is excluded — it isn't an interactive
 * console persona — which is exactly the set `HUMAN_ROLES` already enumerates.
 */
interface Section {
  key: string
  /** Short label rendered in the section eyebrow (e.g. "1st line"). */
  eyebrow: string
  title: string
  description: string
  /** Predicate over a role's ROLE_META — which roles belong to this section. */
  match: (role: Role) => boolean
}

const SECTIONS: Section[] = [
  {
    key: '1st',
    eyebrow: '1st line',
    title: 'First Line of Defense — Ownership & Investigation',
    description:
      'Branch and fraud-function staff who own, triage, and disposition alerts — from the relationship manager up to the AGM (Vigilance).',
    match: (role) => ROLE_META[role].line === '1st',
  },
  {
    key: '2nd',
    eyebrow: '2nd line',
    title: 'Second Line of Defense — Risk & Compliance Oversight',
    description:
      'Risk, compliance, and model-risk functions that set thresholds and challenge the first line. De-identified data at the executive (CGM) tier.',
    match: (role) => ROLE_META[role].line === '2nd',
  },
  {
    key: '3rd',
    eyebrow: '3rd line',
    title: 'Third Line of Defense — Independent Assurance',
    description:
      'Internal Audit — read-only assurance over the immutable trail. Watches the watchers; mutates nothing.',
    match: (role) => ROLE_META[role].line === '3rd',
  },
  {
    key: 'exec',
    eyebrow: 'Board / Exec',
    title: 'Board & Executive',
    description:
      'Executive Director and Managing Director & CEO. Board oversight on de-identified aggregates and KRIs — no case PII.',
    match: (role) => ROLE_META[role].line === 'Exec',
  },
  {
    key: 'it',
    eyebrow: 'Technology',
    title: 'IT / Platform',
    description:
      'Platform administration — users, roles, and infrastructure. Sits outside the Lines of Defense and sees no case data.',
    match: (role) => ROLE_META[role].line === '—',
  },
]

/**
 * Human-readable, one-line summary of what a role may do, derived live from the matrix so it can
 * never disagree with the FROZEN capability grants. We surface the *operational* capabilities (the
 * ones that distinguish roles) and fall back to "View-only" / "No console capabilities" so every
 * card reads naturally.
 */
const SUMMARY_CAPS: Capability[] = CAPABILITIES.filter((c) => c !== 'view_alerts')

function capabilitySummary(role: Role): string {
  const granted = SUMMARY_CAPS.filter((cap) => can(role, cap)).map((cap) => CAPABILITY_LABELS[cap])
  if (granted.length === 0) {
    return can(role, 'view_alerts') ? 'View-only access' : 'No console capabilities'
  }
  return granted.join(' · ')
}

export function OrgChartView() {
  // Sections that actually render (non-empty), so the staggered reveal cascades over them.
  const sections = SECTIONS.map((section) => ({
    section,
    // Preserve HUMAN_ROLES ordering (top-of-chart first) within each section.
    roles: HUMAN_ROLES.filter(section.match),
  })).filter(({ roles }) => roles.length > 0)

  return (
    <RouteTransition className="space-y-4">
      <PageHeader
        icon={<Network className="size-5" />}
        title="Org chart"
        description="Console RBAC reporting tree, grouped by the RBI Three Lines of Defense. Read-only."
        actions={
          <Badge variant="outline" className="gap-1.5">
            <ShieldCheck className="size-3.5" /> Read-only
          </Badge>
        }
      />

      {/* Staggered reveal — each Line-of-Defense tier cascades in; reduced-motion shows all at once. */}
      <m.div className="space-y-4" variants={staggerParent} initial="hidden" animate="show">
        {sections.map(({ section, roles }) => (
          <m.div key={section.key} variants={staggerItem}>
            <Surface tone="reference" pad="md" className="space-y-3">
              <div>
                <Eyebrow>{section.eyebrow}</Eyebrow>
                <h2 className="mt-1 font-display text-base font-semibold tracking-tight">
                  {section.title}
                </h2>
                <p className="mt-0.5 text-sm text-muted-foreground">{section.description}</p>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                {roles.map((role) => (
                  <RoleCard key={role} role={role} />
                ))}
              </div>
            </Surface>
          </m.div>
        ))}
      </m.div>
    </RouteTransition>
  )
}

function RoleCard({ role }: { role: Role }) {
  const meta = ROLE_META[role]
  const reportsTo = meta.reportsTo ? ROLE_META[meta.reportsTo] : null
  return (
    <Card className="flex flex-col gap-2 p-3.5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-display text-sm font-semibold leading-tight">{meta.label}</p>
          <p className="mt-0.5 text-2xs text-muted-foreground">{meta.dept}</p>
        </div>
        <Badge variant="secondary" className="shrink-0 font-mono">
          {meta.short}
        </Badge>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <Badge variant="outline" className="text-2xs">
          {meta.tier}
        </Badge>
        {reportsTo ? (
          <span className="inline-flex items-center gap-1 text-2xs text-muted-foreground">
            <GitBranch className="size-3" /> reports to {reportsTo.short}
          </span>
        ) : (
          <span className="text-2xs text-muted-foreground">top of chart</span>
        )}
      </div>

      <p className="mt-auto text-xs leading-snug text-muted-foreground">
        {capabilitySummary(role)}
      </p>
    </Card>
  )
}
