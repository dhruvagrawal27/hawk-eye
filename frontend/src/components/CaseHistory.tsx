import {
  ArrowRightLeft,
  CircleDot,
  History,
  ShieldCheck,
  UserCheck,
  MessageSquare,
  Flag,
  Lock,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { formatIST, formatRelative, humanize } from '@/lib/format'
import { ROLE_META } from '@/auth/capabilities'
import { EmptyState } from '@/components/ui/empty-state'
import { InfoTip } from '@/components/ui/tooltip'
import { useAutoAnimateList } from '@/ui'
import type { CaseHistoryEvent } from '@/lib/types'

/** Map a history `action` verb to an icon + accent so the feed scans quickly. */
function actionMeta(action: string): { icon: LucideIcon; className: string } {
  const a = action.toLowerCase()
  if (a.includes('status') || a.includes('transition') || a.includes('reopen')) {
    return { icon: ArrowRightLeft, className: 'text-primary' }
  }
  if (a.includes('assign')) return { icon: UserCheck, className: 'text-reason-graph' }
  if (a.includes('note') || a.includes('comment'))
    return { icon: MessageSquare, className: 'text-muted-foreground' }
  if (a.includes('escalat')) return { icon: Flag, className: 'text-severity-high' }
  if (a.includes('close') || a.includes('resolv'))
    return { icon: ShieldCheck, className: 'text-sla-ok' }
  if (a.includes('unmask') || a.includes('pii'))
    return { icon: Lock, className: 'text-severity-medium' }
  return { icon: CircleDot, className: 'text-muted-foreground' }
}

/**
 * Case activity / history feed (FRONTEND-5; blueprint Part 24.4 screen 4) — who did what when, the
 * "watch-the-watchers" trail for a case. Renders newest-first as a vertical timeline.
 */
export function CaseHistory({ history }: { history: CaseHistoryEvent[] }) {
  // Newest-first timeline; AutoAnimate glides new activity in (reduced-motion → instant). Hook runs
  // before the empty-state early return so hook order stays stable across renders.
  const [timelineRef] = useAutoAnimateList<HTMLOListElement>()

  if (history.length === 0) {
    return (
      <EmptyState
        icon={History}
        title="No activity recorded"
        description="Status changes, assignments, and notes will appear here as the case progresses."
      />
    )
  }

  const ordered = [...history].sort((a, b) => +new Date(b.ts) - +new Date(a.ts))

  return (
    <ol ref={timelineRef} className="space-y-0.5">
      {ordered.map((event, i) => {
        const meta = actionMeta(event.action)
        const Icon = meta.icon
        return (
          <li key={event.id} className="flex gap-3">
            <div className="flex flex-col items-center">
              <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-muted/60 ring-1 ring-inset ring-border">
                <Icon className={`size-3.5 ${meta.className}`} />
              </span>
              {i < ordered.length - 1 ? (
                <span className="w-px flex-1 bg-border" aria-hidden />
              ) : null}
            </div>
            <div className="min-w-0 flex-1 pb-3">
              <div className="flex flex-wrap items-baseline gap-x-1.5">
                <span className="text-sm font-medium">{event.actor}</span>
                {event.actor_role ? (
                  <span className="text-[0.7rem] text-muted-foreground">
                    {ROLE_META[event.actor_role]?.short ?? humanize(event.actor_role)}
                  </span>
                ) : null}
                <span className="text-sm text-foreground/80">{humanize(event.action)}</span>
              </div>
              {event.detail ? (
                <p className="mt-0.5 break-words text-xs text-muted-foreground">{event.detail}</p>
              ) : null}
              <InfoTip label={formatIST(event.ts)}>
                <span className="mt-0.5 inline-block font-mono text-[0.7rem] tabular-nums text-muted-foreground">
                  {formatRelative(event.ts)}
                </span>
              </InfoTip>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
