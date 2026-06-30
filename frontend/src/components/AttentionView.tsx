/**
 * Sequence attention (L4 / LAXCAT) — renders each behavioural session as a left-to-right sequence
 * of steps, with each step's bar height + opacity scaled to its attention weight. The highest-weight
 * step(s) are highlighted so an investigator can see *which actions in the sequence the model paid
 * attention to*. Off-hours steps are flagged. (Blueprint Part 11 / Part 24.4 §4.)
 */
import { Activity, Moon } from 'lucide-react'
import { cn } from '@/lib/cn'
import { humanize, formatISTTime, formatPercent } from '@/lib/format'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { EmptyState } from '@/components/ui/empty-state'
import type { AttentionSession, AttentionStep } from '@/lib/types'

function stepLabel(step: AttentionStep): string {
  return step.label ? humanize(step.label) : step.verb ? humanize(step.verb) : 'step'
}

function AttentionStepBar({ step, isPeak }: { step: AttentionStep; isPeak: boolean }) {
  const weight = Math.max(0, Math.min(1, step.weight))
  // Map weight → bar height (16–64px) and opacity (0.25–1) so the peak reads instantly.
  const barHeight = 16 + Math.round(weight * 48)
  const opacity = 0.25 + weight * 0.75

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <li
          className={cn(
            'flex w-[68px] shrink-0 flex-col items-center gap-1 rounded-md border p-1.5 text-center transition-colors',
            isPeak ? 'border-reason-shap/50 bg-reason-shap/10' : 'border-border bg-muted/20',
          )}
        >
          <div className="flex h-16 w-full items-end justify-center">
            <div
              className={cn('w-5 rounded-t-sm', isPeak ? 'bg-reason-shap' : 'bg-primary')}
              style={{ height: `${barHeight}px`, opacity }}
              aria-hidden
            />
          </div>
          <span className="w-full truncate text-[0.65rem] font-medium leading-tight text-foreground">
            {stepLabel(step)}
          </span>
          <span className="tabular-nums text-[0.6rem] text-muted-foreground">
            {formatPercent(weight)}
          </span>
          {step.is_off_hours ? (
            <Moon className="size-3 text-severity-medium" aria-label="off-hours" />
          ) : null}
        </li>
      </TooltipTrigger>
      <TooltipContent>
        <div className="space-y-0.5">
          <div className="font-medium">{stepLabel(step)}</div>
          <div className="text-muted-foreground">{formatISTTime(step.ts)} IST</div>
          <div className="tabular-nums">attention {formatPercent(weight, 1)}</div>
          {step.channel ? (
            <div className="text-muted-foreground">channel · {step.channel}</div>
          ) : null}
          {step.is_off_hours ? <div className="text-severity-medium">off-hours</div> : null}
        </div>
      </TooltipContent>
    </Tooltip>
  )
}

function SessionRow({ session }: { session: AttentionSession }) {
  const peak = session.steps.reduce((m, s) => Math.max(m, s.weight), 0)
  // Treat near-max steps as "peak" so ties both highlight.
  const peakThreshold = peak > 0 ? peak - 1e-6 : Infinity

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="font-mono text-muted-foreground">{session.session_id}</span>
        <span className="rounded bg-secondary px-1.5 py-0.5 font-medium text-secondary-foreground">
          {session.model ?? 'LAXCAT'}
        </span>
      </div>
      {session.steps.length === 0 ? (
        <p className="text-xs text-muted-foreground">No steps in this session.</p>
      ) : (
        <ol className="flex items-end gap-1.5 overflow-x-auto pb-1">
          {session.steps.map((step, i) => (
            <AttentionStepBar
              key={step.event_id ?? `${session.session_id}-${i}`}
              step={step}
              isPeak={step.weight >= peakThreshold && peak > 0}
            />
          ))}
        </ol>
      )}
    </div>
  )
}

export function AttentionView({ sessions }: { sessions: AttentionSession[] }) {
  const withSteps = sessions.filter((s) => s.steps.length > 0)

  if (withSteps.length === 0) {
    return (
      <EmptyState
        icon={Activity}
        title="No sequence attention"
        description="The sequence model (L4) did not contribute attributable steps for this alert."
      />
    )
  }

  return (
    <div className="space-y-4">
      {withSteps.map((session) => (
        <SessionRow key={session.session_id} session={session} />
      ))}
      <p className="text-[0.7rem] text-muted-foreground">
        Bar height &amp; opacity scale with the sequence model&apos;s attention weight; highlighted
        steps are the actions it weighed most.
      </p>
    </div>
  )
}
