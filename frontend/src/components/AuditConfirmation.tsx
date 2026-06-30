import { CheckCircle2, FileClock, RefreshCcw, ScrollText } from 'lucide-react'
import { cn } from '@/lib/cn'

/**
 * Post-disposition receipt (FRONTEND-11; Blueprint Part 10 + Part 24.5c). Every disposition is two
 * things at once and an investigator must be able to *see* both:
 *  1. an entry written to the **immutable WORM audit log** (`audit_id` — watch-the-watchers), and
 *  2. a **label that feeds the L3/L4 relabeling loop** (active learning — Part 10).
 *
 * This is a pure receipt component — it renders the returned `audit_id` and the two server flags
 * (`label_written`, `feedback_queued_for_retraining`). It performs no mutation itself.
 */
export function AuditConfirmation({
  auditId,
  labelWritten = false,
  feedbackQueued = false,
  title = 'Disposition recorded',
  className,
}: {
  auditId: string
  labelWritten?: boolean
  feedbackQueued?: boolean
  title?: string
  className?: string
}) {
  return (
    <div
      className={cn('rounded-lg border border-sla-ok/30 bg-sla-ok/5 p-3 text-sm', className)}
      role="status"
      aria-live="polite"
    >
      <div className="flex items-start gap-2">
        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-sla-ok" aria-hidden />
        <div className="min-w-0 flex-1 space-y-2">
          <p className="font-medium leading-tight">{title}</p>

          <ul className="space-y-1.5 text-xs text-muted-foreground">
            <li className="flex items-center gap-1.5">
              <ScrollText className="size-3.5 shrink-0 text-tee" aria-hidden />
              <span>
                Written to the immutable audit log ·{' '}
                <span className="tok font-mono text-foreground">{auditId}</span>
              </span>
            </li>
            <li
              className={cn(
                'flex items-center gap-1.5',
                labelWritten ? 'text-foreground' : 'text-muted-foreground/70',
              )}
            >
              <FileClock
                className={cn(
                  'size-3.5 shrink-0',
                  labelWritten ? 'text-reason-shap' : 'opacity-60',
                )}
                aria-hidden
              />
              <span>
                {labelWritten ? 'Ground-truth label written for this alert.' : 'No label written.'}
              </span>
            </li>
            <li
              className={cn(
                'flex items-center gap-1.5',
                feedbackQueued ? 'text-foreground' : 'text-muted-foreground/70',
              )}
            >
              <RefreshCcw
                className={cn(
                  'size-3.5 shrink-0',
                  feedbackQueued ? 'text-reason-shap' : 'opacity-60',
                )}
                aria-hidden
              />
              <span>
                {feedbackQueued
                  ? 'Queued for the L3/L4 relabeling loop (active learning · Part 10).'
                  : 'Not queued for retraining.'}
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}
