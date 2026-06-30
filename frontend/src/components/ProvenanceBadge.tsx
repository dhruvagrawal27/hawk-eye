/**
 * Provenance / trust panel (Part 25) — expands the TEE badge into a collapsible attestation panel so
 * a reviewer can see *exactly* how the AI narrative was produced and verify it independently.
 *
 * Honest degradation is the whole point:
 *   • tee_attested  → lazily fetch the per-request attestation (only when expanded) and show a mono
 *                     KeyValueGrid: provider · gateway · model · signing address/algo · TDX quote
 *                     hash · attestation id. This is the cryptographic trail an auditor checks.
 *   • not attested  → a quiet "standard cloud inference" line. No alarm, no fake attestation — the
 *                     degradation is deliberate and logged, and PII was tokenized regardless.
 *
 * Built as an accessible disclosure (button + aria-expanded/aria-controls) rather than pulling in a
 * new Radix Collapsible dependency — same keyboard/SR semantics, zero new deps.
 */
import { useId, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronRight, ShieldCheck, Loader2, Cpu, Lock } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { queryKeys } from '@/lib/queryKeys'
import { cn } from '@/lib/cn'
import { formatIST, humanize } from '@/lib/format'
import type { AttestationDetail } from '@/lib/types'

/* ── Mono key/value grid for the attestation fields ───────────────────────── */
function KeyValueGrid({ rows }: { rows: { label: string; value: string; mono?: boolean }[] }) {
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-[auto_minmax(0,1fr)]">
      {rows.map((r) => (
        <div key={r.label} className="flex items-baseline justify-between gap-3 sm:contents">
          <dt className="shrink-0 text-[0.7rem] uppercase tracking-wide text-muted-foreground">
            {r.label}
          </dt>
          <dd
            className={cn(
              'min-w-0 truncate text-right text-xs text-foreground sm:text-left',
              r.mono !== false && 'font-mono tabular-nums',
            )}
            title={r.value}
          >
            {r.value}
          </dd>
        </div>
      ))}
    </dl>
  )
}

function AttestationBody({ alertId }: { alertId: string }) {
  // Lazy: this query is only mounted once the panel is open (parent gates the render), and the
  // network call only fires here.
  const query = useQuery({
    queryKey: queryKeys.attestation(alertId),
    queryFn: () => apiClient.getAttestation(alertId),
  })

  if (query.isLoading) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="size-3.5 animate-spin" />
        Fetching attestation…
      </div>
    )
  }
  if (query.isError || !query.data) {
    return (
      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>Attestation detail unavailable.</span>
        <button
          type="button"
          onClick={() => void query.refetch()}
          className="font-medium text-primary underline-offset-4 hover:underline focus-ring"
        >
          Retry
        </button>
      </div>
    )
  }

  const a: AttestationDetail = query.data
  const rows: { label: string; value: string; mono?: boolean }[] = [
    { label: 'Provider', value: humanize(String(a.provider)), mono: false },
    ...(a.gateway ? [{ label: 'Gateway', value: a.gateway, mono: false }] : []),
    { label: 'Model', value: a.model },
    ...(a.signing_address ? [{ label: 'Signing addr', value: a.signing_address }] : []),
    ...(a.signing_algo ? [{ label: 'Signing algo', value: a.signing_algo }] : []),
    ...(a.intel_quote_sha256 ? [{ label: 'TDX quote', value: a.intel_quote_sha256 }] : []),
    ...(a.attestation_id ? [{ label: 'Attestation', value: a.attestation_id }] : []),
    ...(a.verified_ts ? [{ label: 'Verified', value: formatIST(a.verified_ts), mono: false }] : []),
    ...(a.extra ?? []).map((e) => ({ label: e.label, value: e.value })),
  ]

  return (
    <div className="space-y-2">
      <KeyValueGrid rows={rows} />
      <p className="flex items-center gap-1.5 text-[0.7rem] italic text-muted-foreground">
        <Lock className="size-3 text-tee" />
        Generated inside a TEE; this per-request attestation is stored immutably for audit.
      </p>
    </div>
  )
}

export function ProvenanceBadge({
  alertId,
  attested,
  className,
}: {
  alertId: string
  attested: boolean
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const panelId = useId()

  // Not attested → honest, quiet degradation. No disclosure, no fake trust signal.
  if (!attested) {
    return (
      <div
        className={cn(
          'flex items-start gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground',
          className,
        )}
      >
        <Cpu className="mt-0.5 size-4 shrink-0" />
        <p className="leading-relaxed">
          <span className="font-medium text-foreground">Standard cloud inference</span> — this
          narrative was not generated inside a TEE, a deliberate and logged degradation. No
          per-request attestation is available; PII was tokenized regardless.
        </p>
      </div>
    )
  }

  return (
    <div className={cn('rounded-lg border border-tee/30 bg-tee/5', className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs focus-ring"
      >
        <ShieldCheck className="size-4 shrink-0 text-tee" />
        <span className="font-medium text-tee">TEE-attested inference</span>
        <span className="hidden text-muted-foreground sm:inline">
          · verifiable per-request attestation
        </span>
        <ChevronRight
          className={cn(
            'ml-auto size-4 shrink-0 text-muted-foreground transition-transform',
            open && 'rotate-90',
          )}
          aria-hidden
        />
      </button>
      {open ? (
        <div id={panelId} className="border-t border-tee/20 px-3 py-2.5">
          <AttestationBody alertId={alertId} />
        </div>
      ) : null}
    </div>
  )
}
