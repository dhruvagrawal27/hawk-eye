/**
 * Printable case dossier (Agent D).
 *
 * A print-to-PDF layout that is hidden on screen and rendered only for `window.print()`
 * (Tailwind `print:` utilities — no print CSS file, index.css untouched). The "Export
 * dossier" button on the case detail triggers `window.print()`; Cmd-P yields the same
 * clean PDF. Contains the case header, linked alerts, reason codes, disposition summary
 * and an audit footer (generated-at + case id + operator) for the regulatory paper trail.
 */
import { FileDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/auth/rbac'
import {
  formatINR,
  formatINRCompact,
  formatIST,
  layerLabel,
  reasonSourceLabels,
  statusLabel,
} from '@/lib/format'
import { riskLevelFromScore, RISK_VAR } from '@/lib/risk'
import type { Alert, CaseDetail, ReasonCode } from '@/lib/types'

/** Human-readable case disposition derived from the workflow status. */
const DISPOSITION_META: Record<CaseDetail['status'], { label: string; detail: string }> = {
  open: { label: 'Open', detail: 'Triage pending — no disposition recorded.' },
  in_progress: { label: 'Under investigation', detail: 'Investigation in progress.' },
  escalated: {
    label: 'Escalated',
    detail: 'Escalated for senior review / regulatory consideration.',
  },
  closed: { label: 'Closed', detail: 'Case closed; disposition finalised in the audit trail.' },
}

/** Render a single reason code as a one-line, print-friendly string. */
function reasonCodeText(rc: ReasonCode): string {
  switch (rc.source) {
    case 'rule':
      return `${rc.code} — ${rc.detail}`
    case 'shap':
      return `${rc.feature} (${rc.contribution >= 0 ? '+' : ''}${rc.contribution.toFixed(3)})`
    case 'graph':
      return rc.ring_id ? `${rc.detail} [ring ${rc.ring_id}]` : rc.detail
  }
}

/* ── Trigger button ─────────────────────────────────────────────────────── */

/** "Export dossier" button — opens the OS print dialog (print-to-PDF) for the case. */
export function ExportDossierButton({ className }: { className?: string }) {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className={className}
      onClick={() => window.print()}
    >
      <FileDown />
      Export dossier
    </Button>
  )
}

/* ── Print-only dossier ─────────────────────────────────────────────────── */

/**
 * Hidden on screen (`hidden`), shown only when printing (`print:block`). Kept in normal
 * document flow during print so it paginates naturally. Uses plain print-safe markup
 * (no app chrome) so the generated PDF reads as a standalone document.
 */
export function CaseDossier({ detail }: { detail: CaseDetail }) {
  const { user, role } = useAuth()
  const generatedAt = new Date().toISOString()
  const operator = user?.username ?? user?.name ?? 'unknown'

  const exposure =
    detail.exposure_inr ?? detail.alerts.reduce((sum, a) => sum + (a.exposure_inr ?? 0), 0)
  const disposition = DISPOSITION_META[detail.status]

  return (
    <section
      aria-hidden="true"
      className="hidden text-black print:block print:bg-white print:text-[11px] print:leading-snug"
    >
      {/* Header */}
      <header className="mb-4 border-b-2 border-black pb-3">
        <p className="text-[9px] font-semibold uppercase tracking-widest text-neutral-600">
          Hawkeye · Case Dossier · Confidential
        </p>
        <h1 className="mt-1 text-xl font-bold">{detail.title}</h1>
        <p className="mt-0.5 font-mono text-[10px] text-neutral-700">{detail.case_id}</p>
        <dl className="mt-2 grid grid-cols-2 gap-x-8 gap-y-1 text-[10px] sm:grid-cols-4">
          <DossierField label="Status" value={statusLabel(detail.status)} />
          <DossierField label="Severity" value={detail.severity.toUpperCase()} />
          <DossierField label="Entity" value={detail.entity_id} mono />
          <DossierField label="Assignee" value={detail.assignee || 'Unassigned'} />
          <DossierField label="Linked alerts" value={String(detail.alert_ids.length)} />
          <DossierField label="Exposure" value={formatINR(exposure)} />
          <DossierField label="Opened" value={formatIST(detail.created_ts)} />
          <DossierField label="Updated" value={formatIST(detail.updated_ts)} />
        </dl>
      </header>

      {/* Disposition */}
      <DossierSection title="Disposition">
        <p>
          <span className="font-semibold">{disposition.label}.</span> {disposition.detail}
        </p>
      </DossierSection>

      {/* Linked alerts + reason codes */}
      <DossierSection title={`Linked alerts (${detail.alerts.length})`}>
        {detail.alerts.length === 0 ? (
          <p className="text-neutral-600">No alerts associated with this case.</p>
        ) : (
          <div className="space-y-3">
            {detail.alerts.map((alert) => (
              <AlertBlock key={alert.alert_id} alert={alert} />
            ))}
          </div>
        )}
      </DossierSection>

      {/* Investigation notes */}
      {detail.notes.length > 0 ? (
        <DossierSection title={`Investigation notes (${detail.notes.length})`}>
          <ul className="space-y-1.5">
            {detail.notes.map((n) => (
              <li key={n.id} className="break-inside-avoid">
                <span className="font-semibold">{n.author}</span>
                {n.author_role ? (
                  <span className="text-neutral-600"> ({n.author_role})</span>
                ) : null}
                <span className="font-mono text-neutral-600"> · {formatIST(n.ts)}</span>
                <div>{n.body}</div>
              </li>
            ))}
          </ul>
        </DossierSection>
      ) : null}

      {/* Audit trail */}
      {detail.history.length > 0 ? (
        <DossierSection title="Audit trail">
          <ul className="space-y-0.5">
            {detail.history.map((h) => (
              <li key={h.id} className="break-inside-avoid">
                <span className="font-mono text-neutral-600">{formatIST(h.ts)}</span> ·{' '}
                <span className="font-semibold">{h.actor}</span> · {h.action}
                {h.detail ? <span className="text-neutral-700"> — {h.detail}</span> : null}
              </li>
            ))}
          </ul>
        </DossierSection>
      ) : null}

      {/* Footer */}
      <footer className="mt-5 break-inside-avoid border-t border-black pt-2 text-[9px] text-neutral-700">
        <p>
          Generated <span className="font-mono">{formatIST(generatedAt)}</span> by {operator}
          {role ? ` (${role})` : ''} · Case <span className="font-mono">{detail.case_id}</span> ·{' '}
          <span className="font-mono">{generatedAt}</span>
        </p>
        <p className="mt-0.5">
          This dossier is a point-in-time export and may not reflect subsequent activity. Source of
          record remains the Hawkeye case store and its immutable audit log.
        </p>
      </footer>
    </section>
  )
}

/* ── Print-only primitives (no app chrome) ──────────────────────────────── */

function AlertBlock({ alert }: { alert: Alert }) {
  const score = Math.round(alert.risk_score)
  return (
    <div className="break-inside-avoid border border-neutral-400 p-2">
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-semibold">{alert.title ?? alert.alert_type ?? alert.alert_id}</span>
        <span
          className="font-bold tabular-nums"
          style={{ color: `hsl(${RISK_VAR[riskLevelFromScore(alert.risk_score)]})` }}
        >
          {score}/100
        </span>
      </div>
      <div className="mt-0.5 text-[9px] text-neutral-600">
        <span className="font-mono">{alert.alert_id}</span> · {alert.severity.toUpperCase()} ·{' '}
        {statusLabel(alert.status)} · {formatINRCompact(alert.exposure_inr)} ·{' '}
        {formatIST(alert.created_ts)}
      </div>

      {alert.contributing_layers.length > 0 ? (
        <div className="mt-1 text-[9px] text-neutral-700">
          <span className="font-semibold">Layers: </span>
          {alert.contributing_layers.map((l) => layerLabel(l)).join(', ')}
        </div>
      ) : null}

      {alert.reason_codes.length > 0 ? (
        <div className="mt-1">
          <p className="text-[9px] font-semibold uppercase tracking-wide text-neutral-600">
            Reason codes
          </p>
          <ul className="ml-3 list-disc">
            {alert.reason_codes.map((rc, i) => (
              <li key={i}>
                <span className="font-medium">{reasonSourceLabels[rc.source]}:</span>{' '}
                {reasonCodeText(rc)}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

function DossierSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-4 break-inside-avoid">
      <h2 className="mb-1 border-b border-neutral-400 pb-0.5 text-[10px] font-bold uppercase tracking-wide">
        {title}
      </h2>
      {children}
    </section>
  )
}

function DossierField({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-[8px] uppercase tracking-wide text-neutral-500">{label}</dt>
      <dd className={mono ? 'font-mono' : undefined}>{value}</dd>
    </div>
  )
}
