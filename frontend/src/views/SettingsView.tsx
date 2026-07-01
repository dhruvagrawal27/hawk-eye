/**
 * SettingsView — the shared, read-only System & model settings page (visible to EVERY signed-in role).
 *
 * Four sections, mirroring the ops "settings" layout: the deployed model card (L6 fusion lineage),
 * live-service health (STATIC / all-green for now), the full RBAC roles×capabilities matrix (the real
 * 12×9 bank org-chart model, active role highlighted), and the compliance posture. Read-only: it
 * inspects configuration and never mutates — consistent with the alert-only, human-in-the-loop invariant.
 *
 * All content is derived from this project's real facts (docs/BANK_ROLES.md matrix, the layer models in
 * the registry, the RBI compliance surface). No API calls, so it renders identically for every role
 * (including de-identified / no-case-data roles) with no risk of an RBAC 403.
 */
import {
  SlidersHorizontal,
  Boxes,
  Activity,
  ShieldCheck,
  CheckCircle2,
  Check,
  Minus,
  ScrollText,
} from 'lucide-react'
import { cn } from '@/lib/cn'
import { useAuth } from '@/auth/rbac'
import {
  CAPABILITIES,
  CAPABILITY_LABELS,
  HUMAN_ROLES,
  ROLE_META,
  cell,
  type Cell,
} from '@/auth/capabilities'
import { PageHeader } from '@/components/PageHeader'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

/* ── Deployed model card — the L6 fusion ensemble (values from the signed registry) ─────────────── */
const MODEL_ROWS: { label: string; value: string; mono?: boolean }[] = [
  { label: 'Ensemble', value: 'L6 risk fusion (calibrated meta-learner)' },
  { label: 'Champion', value: 'L3 LightGBM', mono: true },
  { label: 'Version', value: '3.1.0', mono: true },
  { label: 'Stage', value: 'Champion · Production' },
  { label: 'Layers', value: 'L1 rules · L2 ECOD · L3 GBDT · L4 sequence · L5 graph · L6 fusion' },
  { label: 'AUC', value: '0.94', mono: true },
  { label: 'PR-AUC', value: '0.71', mono: true },
  { label: 'F1', value: '0.71', mono: true },
  { label: 'Precision / Recall', value: '0.66 / 0.78', mono: true },
  { label: 'Calibration (Brier)', value: '0.08', mono: true },
  { label: 'Explainability', value: 'TreeSHAP — per-alert factor breakdown' },
  { label: 'Challenger', value: 'L3 CatBoost v0.9.3 (AUC 0.95)', mono: true },
  { label: 'Trained', value: '2026-06-01', mono: true },
  { label: 'Registry', value: 'Signed artifacts · four-eyes promotion' },
]

/* ── System health — STATIC, all green (per request). Mirrors the CONTEXT.md service map. ────────── */
const SERVICES: { name: string; detail: string }[] = [
  { name: 'Postgres', detail: 'ok' },
  { name: 'Redis', detail: 'ok' },
  { name: 'Neo4j', detail: 'ok' },
  { name: 'ClickHouse', detail: 'ok' },
  { name: 'Flink', detail: 'ok' },
  { name: 'Kafka', detail: 'topics = 2' },
  { name: 'Model serving (KServe v2)', detail: 'ready' },
  { name: 'Keycloak (OIDC)', detail: 'ok' },
  { name: 'Vault', detail: 'sealed = false' },
  { name: 'LLM narrative gateway', detail: 'confidential-AI · TEE-attested' },
]

function ModelCard() {
  return (
    <Card className="p-5">
      <SectionLabel icon={Boxes}>Model card</SectionLabel>
      <dl className="mt-4 space-y-2.5">
        {MODEL_ROWS.map((r) => (
          <div key={r.label} className="flex items-baseline justify-between gap-4">
            <dt className="shrink-0 text-2xs uppercase tracking-widest text-muted-foreground">
              {r.label}
            </dt>
            <dd
              className={cn(
                'text-right text-sm text-foreground',
                r.mono && 'font-mono tabular-nums',
              )}
            >
              {r.value}
            </dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}

function SystemHealth() {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <SectionLabel icon={Activity}>System health</SectionLabel>
        <span className="inline-flex items-center gap-1.5 text-2xs font-medium uppercase tracking-widest text-tee">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-tee motion-safe:animate-pulse-soft" />
          all services up
        </span>
      </div>
      <ul className="mt-4 divide-y divide-border/60">
        {SERVICES.map((s) => (
          <li key={s.name} className="flex items-center gap-2.5 py-2">
            <CheckCircle2 className="size-4 shrink-0 text-tee" aria-hidden />
            <span className="text-sm text-foreground">{s.name}</span>
            <span className="ml-auto font-mono text-2xs tabular-nums text-muted-foreground">
              {s.detail}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

/** One RBAC cell → ✅ (allowed) / ⚠️ (allowed but constrained) / ❌ (denied). */
function MatrixCell({ c }: { c: Cell }) {
  if (!c.allowed) {
    return <Minus className="mx-auto size-3.5 text-muted-foreground/40" aria-label="Denied" />
  }
  if (c.constraint) {
    return (
      <span
        className="mx-auto flex size-4 items-center justify-center rounded-full bg-severity-medium/15"
        title={`Allowed — constrained: ${c.constraint.replace(/_/g, ' ')}`}
        aria-label={`Allowed but constrained: ${c.constraint.replace(/_/g, ' ')}`}
      >
        <span className="size-1.5 rounded-full bg-severity-medium" />
      </span>
    )
  }
  return (
    <Check
      className="mx-auto size-4 text-tee"
      aria-label={c.scope ? `Allowed (${c.scope})` : 'Allowed'}
    />
  )
}

function RolesMatrix() {
  const { role: activeRole } = useAuth()
  return (
    <Card className="p-5">
      <SectionLabel icon={ShieldCheck}>Roles &amp; permissions</SectionLabel>
      <p className="mt-1 text-xs text-muted-foreground">
        The bank org-chart model — 11 human roles × 9 capabilities.{' '}
        {activeRole ? (
          <>
            Your active role is{' '}
            <span className="font-medium text-foreground">{ROLE_META[activeRole].label}</span>{' '}
            (highlighted).
          </>
        ) : null}{' '}
        Enforced server-side from the Keycloak JWT (
        <span className="font-mono">realm_access.roles</span>
        ); this client matrix is defense-in-depth.
      </p>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-card px-2 py-2 text-left align-bottom text-2xs font-semibold uppercase tracking-widest text-muted-foreground">
                Capability
              </th>
              {HUMAN_ROLES.map((r) => {
                const active = r === activeRole
                return (
                  <th
                    key={r}
                    title={ROLE_META[r].label}
                    className={cn(
                      'px-2 py-2 text-center align-bottom font-medium',
                      active ? 'text-primary' : 'text-muted-foreground',
                    )}
                  >
                    <span
                      className={cn(
                        'inline-block whitespace-nowrap rounded px-1.5 py-0.5',
                        active && 'bg-primary/10 ring-1 ring-primary/30',
                      )}
                    >
                      {ROLE_META[r].short}
                    </span>
                    {active ? (
                      <span className="mt-1 block text-3xs font-semibold uppercase tracking-widest text-primary">
                        active
                      </span>
                    ) : null}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {CAPABILITIES.map((cap) => (
              <tr key={cap} className="border-t border-border/60">
                <td className="sticky left-0 z-10 bg-card px-2 py-2 text-left font-medium text-foreground">
                  {CAPABILITY_LABELS[cap]}
                </td>
                {HUMAN_ROLES.map((r) => {
                  const active = r === activeRole
                  return (
                    <td key={r} className={cn('px-2 py-2 text-center', active && 'bg-primary/5')}>
                      <MatrixCell c={cell(r, cap)} />
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-2xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <Check className="size-3.5 text-tee" /> Allowed
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="flex size-3.5 items-center justify-center rounded-full bg-severity-medium/15">
            <span className="size-1.5 rounded-full bg-severity-medium" />
          </span>
          Allowed · constrained / logged
        </span>
        <span className="inline-flex items-center gap-1.5">
          <Minus className="size-3.5 text-muted-foreground/40" /> Denied
        </span>
      </div>
    </Card>
  )
}

function CompliancePosture() {
  return (
    <Card className="p-5">
      <SectionLabel icon={ScrollText}>Compliance posture</SectionLabel>
      <div className="mt-3 space-y-3 text-sm leading-relaxed text-foreground">
        <p>
          Hawk-Eye operates strictly <strong>alert-only</strong> under a{' '}
          <strong>human-in-the-loop</strong> policy — every risk score is reviewed by an
          investigator before any operational action is taken; the system never auto-blocks or
          auto-classifies.
        </p>
        <p>
          Every alert ships with a <strong>TreeSHAP</strong> factor breakdown and a model-generated
          investigation memo for auditability. Every privileged action — especially PII unmask — is
          written to an append-only, hash-chained <strong>WORM audit trail</strong>{' '}
          (watch-the-watchers).
        </p>
        <p>
          On-prem + <strong>synthetic data only</strong>; PII is HMAC-tokenized with an AES-GCM
          field vault. Access follows the <strong>12 roles × 9 capabilities</strong> RBAC model with
          segregation-of-duties, enforced server-side. Regulatory generators cover RBI{' '}
          <span className="font-mono">CRILC</span> (₹3cr / 7d / 180d),{' '}
          <span className="font-mono">FMR</span>, and <span className="font-mono">EWS / RFA</span>.
        </p>
      </div>
      <p className="mt-4 border-t border-border/60 pt-3 font-mono text-2xs uppercase tracking-widest text-muted-foreground">
        NINEAGENTS · Hawk-Eye · RBI-aligned (CRILC / FMR / EWS) · ALERT-ONLY · a human always
        decides
      </p>
    </Card>
  )
}

function SectionLabel({ icon: Icon, children }: { icon: typeof Boxes; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="size-4 text-primary" aria-hidden />
      <h2 className="text-sm font-semibold uppercase tracking-widest text-foreground">
        {children}
      </h2>
    </div>
  )
}

export function SettingsView() {
  return (
    <div className="space-y-4">
      <PageHeader
        icon={<SlidersHorizontal className="size-5" />}
        title="System & model settings"
        description="Read-only view of model lineage, service health, roles, and compliance posture."
        actions={
          <Badge variant="outline" className="gap-1.5">
            <ShieldCheck className="size-3.5" /> Read-only
          </Badge>
        }
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <ModelCard />
        <SystemHealth />
      </div>
      <RolesMatrix />
      <CompliancePosture />
    </div>
  )
}
