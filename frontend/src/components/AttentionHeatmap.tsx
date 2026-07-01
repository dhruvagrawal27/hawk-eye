/**
 * L4 attention **heatmap** (LAXCAT variable × temporal) — the full attention matrix, not a single
 * bar. Rows are the variables the sequence model attends to (amount, off-hours, verb, velocity …);
 * columns are the ordered steps of the behavioural session. Each cell's intensity is the variable's
 * attention weight at that step; the column header bar is the step's temporal attention. This
 * surfaces *which variable, at which moment* drove the sequence flag — the LAXCAT explanation that
 * the old single-bar view collapsed away. (Blueprint Part 11 / Part 20.4 — LAXCAT explainer.)
 */
import { Moon } from 'lucide-react'
import { cn } from '@/lib/cn'
import { humanize, formatISTTime, formatPercent } from '@/lib/format'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import type { AttentionSession, AttentionStep } from '@/lib/types'

function stepLabel(step: AttentionStep): string {
  return step.label ? humanize(step.label) : step.verb ? humanize(step.verb) : 'step'
}

/** Union of variable names across a session's steps, ordered by total attention (most salient first). */
function orderedVariables(session: AttentionSession): string[] {
  const totals = new Map<string, number>()
  for (const step of session.steps) {
    for (const v of step.variables ?? []) {
      totals.set(v.name, (totals.get(v.name) ?? 0) + v.weight)
    }
  }
  return [...totals.entries()].sort((a, b) => b[1] - a[1]).map(([name]) => name)
}

function variableWeight(step: AttentionStep, name: string): number {
  return step.variables?.find((v) => v.name === name)?.weight ?? 0
}

/** True when at least one step carries per-variable attention (so the heatmap has data to draw). */
export function hasVariableAttention(sessions: AttentionSession[]): boolean {
  return sessions.some((s) => s.steps.some((st) => (st.variables?.length ?? 0) > 0))
}

function HeatCell({
  step,
  variable,
  peak,
}: {
  step: AttentionStep
  variable: string
  peak: number
}) {
  const w = variableWeight(step, variable)
  // Combined salience = variable-attention × temporal-attention, normalised to the session peak.
  const salience = peak > 0 ? (w * step.weight) / peak : 0
  const opacity = w > 0 ? 0.12 + salience * 0.88 : 0
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <td className="p-0.5">
          <div
            className={cn(
              'flex h-6 w-full min-w-[34px] items-center justify-center rounded-sm text-[0.6rem] tabular-nums',
              w > 0 ? 'text-background' : 'text-transparent',
            )}
            style={{ backgroundColor: `hsl(var(--ai) / ${opacity.toFixed(3)})` }}
          >
            {w > 0 ? Math.round(w * 100) : '·'}
          </div>
        </td>
      </TooltipTrigger>
      <TooltipContent>
        <div className="space-y-0.5">
          <div className="font-medium">{humanize(variable)}</div>
          <div className="text-muted-foreground">{stepLabel(step)}</div>
          <div className="tabular-nums">variable attention {formatPercent(w, 1)}</div>
          <div className="tabular-nums text-muted-foreground">
            step (temporal) {formatPercent(step.weight, 1)}
          </div>
        </div>
      </TooltipContent>
    </Tooltip>
  )
}

function SessionHeatmap({ session }: { session: AttentionSession }) {
  const variables = orderedVariables(session)
  const peak = session.steps.reduce(
    (m, s) => Math.max(m, ...(s.variables ?? []).map((v) => v.weight * s.weight), 0),
    0,
  )
  if (variables.length === 0) return null

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="font-mono text-muted-foreground">{session.session_id}</span>
        <span className="rounded bg-secondary px-1.5 py-0.5 font-medium text-secondary-foreground">
          {session.model ?? 'LAXCAT'}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="border-separate border-spacing-0.5">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-background" />
              {session.steps.map((step, i) => (
                <th key={step.event_id ?? i} className="p-0.5 align-bottom">
                  <div className="flex flex-col items-center gap-0.5">
                    {step.is_off_hours ? (
                      <Moon className="size-2.5 text-severity-medium" aria-label="off-hours" />
                    ) : (
                      <span className="h-2.5" />
                    )}
                    {/* temporal-attention header bar */}
                    <div className="flex h-8 w-full items-end justify-center">
                      <div
                        className="w-2 rounded-t-sm bg-ai"
                        style={{ height: `${16 + Math.round(step.weight * 16)}px`, opacity: 0.3 + step.weight * 0.7 }}
                        aria-hidden
                      />
                    </div>
                    <span className="max-w-[52px] truncate text-[0.55rem] leading-tight text-muted-foreground">
                      {stepLabel(step)}
                    </span>
                    <span className="text-[0.5rem] tabular-nums text-muted-foreground">
                      {formatISTTime(step.ts)}
                    </span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {variables.map((variable) => (
              <tr key={variable}>
                <th
                  scope="row"
                  className="sticky left-0 z-10 whitespace-nowrap bg-background pr-2 text-right text-[0.65rem] font-medium text-foreground"
                >
                  {humanize(variable)}
                </th>
                {session.steps.map((step, i) => (
                  <HeatCell
                    key={step.event_id ?? i}
                    step={step}
                    variable={variable}
                    peak={peak}
                  />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function AttentionHeatmap({ sessions }: { sessions: AttentionSession[] }) {
  const withVars = sessions.filter((s) => s.steps.some((st) => (st.variables?.length ?? 0) > 0))
  if (withVars.length === 0) return null
  return (
    <div className="space-y-4">
      {withVars.map((s) => (
        <SessionHeatmap key={s.session_id} session={s} />
      ))}
      <p className="text-[0.7rem] text-muted-foreground">
        Rows = variables the sequence model (L4 · LAXCAT) attends to; columns = ordered session
        steps. Cell intensity is the variable&apos;s attention at that step; the header bar is the
        step&apos;s temporal attention. Bright cells are the <em>variable-at-moment</em> that drove
        the sequence signal.
      </p>
    </div>
  )
}
