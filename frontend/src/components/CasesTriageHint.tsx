/**
 * A plain-language explainer of the Triage-vs-Cases distinction — the single most common "what am I
 * even looking at?" question for new console users. Rendered as a collapsible note so it's available
 * on both the Triage queue and Case management screens without taking permanent space.
 */
import { Inbox, FolderKanban } from 'lucide-react'
import { cn } from '@/lib/cn'

export function CasesTriageHint({ className }: { className?: string }) {
  return (
    <details className={cn('group rounded-lg border border-border bg-muted/30 text-sm', className)}>
      <summary className="flex cursor-pointer select-none items-center gap-2 px-3 py-2 font-medium text-muted-foreground hover:text-foreground">
        <span className="text-xs">Triage vs Cases — what’s the difference?</span>
      </summary>
      <div className="grid gap-3 px-3 pb-3 sm:grid-cols-2">
        <div className="rounded-md border border-border/70 bg-card p-3">
          <div className="mb-1 flex items-center gap-1.5 font-medium">
            <Inbox className="size-4 text-primary" aria-hidden />
            Triage queue
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            The live <span className="text-foreground">inbox of individual alerts</span>, ranked by
            fused risk × exposure × confidence. You claim an alert, investigate it, and disposition
            it (true / false positive).{' '}
            <span className="text-foreground">One row = one alert.</span> Use it to react to what is
            firing right now.
          </p>
        </div>
        <div className="rounded-md border border-border/70 bg-card p-3">
          <div className="mb-1 flex items-center gap-1.5 font-medium">
            <FolderKanban className="size-4 text-reason-graph" aria-hidden />
            Cases
          </div>
          <p className="text-xs leading-relaxed text-muted-foreground">
            An <span className="text-foreground">investigation folder</span> that groups related
            alerts (same entity / ring / typology) so they are worked together — with an assignee, a
            workflow (open → in progress → escalated → closed), notes, and a SAR/FMR dossier.{' '}
            <span className="text-foreground">One row = one case (many alerts).</span>
          </p>
        </div>
      </div>
      <p className="px-3 pb-3 text-xs text-muted-foreground">
        Rule of thumb: start in <span className="text-foreground">Triage</span> to react to what’s
        firing; open a <span className="text-foreground">Case</span> when something needs a tracked,
        multi-alert investigation with an owner and an audit trail.
      </p>
    </details>
  )
}
