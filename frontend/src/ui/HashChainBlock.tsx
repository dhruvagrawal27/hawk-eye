/**
 * HashChainBlock — one WORM / tamper-evident audit-chain block (docs/ui/UI_UPLIFT.md §3).
 *
 * "Watch the watchers": every privileged action (esp. PII unmask) is written to an append-only,
 * hash-chained audit log. The auditor screen assembles a vertical chain of these; each block shows its
 * index, this block's hash, and the `prev` link, with a verified/broken seal. Hashes are **evidence** →
 * always monospace, always truncated with the full value in a title/aria for copy. Presentational only.
 */
import { cn } from '@/lib/cn'

export interface HashChainBlockProps {
  /** Position in the chain (0 = genesis). */
  index: number
  /** This block's content hash (hex). */
  hash: string
  /** The previous block's hash this one commits to. */
  prevHash?: string
  /** Seal state: verified links vs a detected break. Defaults to verified. */
  ok?: boolean
  /** ISO timestamp of the entry. */
  ts?: string
  /** Short action label (e.g. "PII unmask", "override"). */
  action?: string
  /** Draw the connector to the next block below. */
  connector?: boolean
  className?: string
}

function short(hash: string, head = 10, tail = 6): string {
  if (hash.length <= head + tail + 1) return hash
  return `${hash.slice(0, head)}…${hash.slice(-tail)}`
}

export function HashChainBlock({
  index,
  hash,
  prevHash,
  ok = true,
  ts,
  action,
  connector = true,
  className,
}: HashChainBlockProps) {
  const seal = ok ? 'hsl(var(--tee))' : 'hsl(var(--severity-critical))'

  return (
    <div className={cn('relative', className)}>
      <div
        className={cn(
          'rounded-md border bg-card p-3 shadow-dossier',
          ok ? 'border-border' : 'border-severity-critical/60',
        )}
        role="group"
        aria-label={
          `Audit block ${index}${action ? `, ${action}` : ''}, ` +
          `${ok ? 'chain verified' : 'chain broken'}. Hash ${hash}` +
          (prevHash ? `, previous ${prevHash}` : '')
        }
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-5 min-w-5 items-center justify-center rounded bg-muted px-1 font-mono text-2xs font-semibold tabular-nums text-muted-foreground">
              #{index}
            </span>
            {action ? <span className="text-xs font-medium text-foreground">{action}</span> : null}
          </div>
          <span
            className="inline-flex items-center gap-1 font-mono text-2xs font-medium uppercase tracking-widest"
            style={{ color: seal }}
          >
            <span
              className="inline-block h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: seal }}
              aria-hidden
            />
            {ok ? 'sealed' : 'broken'}
          </span>
        </div>

        <dl className="mt-2 space-y-1">
          <div className="flex items-baseline gap-2">
            <dt className="w-10 shrink-0 text-3xs uppercase tracking-widest text-muted-foreground">
              hash
            </dt>
            <dd className="truncate font-mono text-xs text-foreground" title={hash}>
              {short(hash)}
            </dd>
          </div>
          {prevHash ? (
            <div className="flex items-baseline gap-2">
              <dt className="w-10 shrink-0 text-3xs uppercase tracking-widest text-muted-foreground">
                prev
              </dt>
              <dd className="truncate font-mono text-xs text-muted-foreground" title={prevHash}>
                {short(prevHash)}
              </dd>
            </div>
          ) : null}
          {ts ? (
            <div className="flex items-baseline gap-2">
              <dt className="w-10 shrink-0 text-3xs uppercase tracking-widest text-muted-foreground">
                ts
              </dt>
              <dd className="font-mono text-2xs tabular-nums text-muted-foreground">{ts}</dd>
            </div>
          ) : null}
        </dl>
      </div>

      {connector ? (
        <div className="ml-4 flex flex-col items-center" aria-hidden>
          <span className="h-3 w-px" style={{ backgroundColor: seal }} />
        </div>
      ) : null}
    </div>
  )
}
