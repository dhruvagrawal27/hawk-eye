/**
 * Service Map (Admin) — every platform service, WHAT it's for, WHERE it's used in the app, whether
 * it's required, and its live status. Answers "which services are we actually using, and where?".
 * Polls GET /services/status every 10s.
 */
import { useQuery } from '@tanstack/react-query'
import { Boxes, RefreshCw } from 'lucide-react'
import { apiClient } from '@/lib/apiClient'
import { cn } from '@/lib/cn'
import type { ServiceStatus } from '@/lib/types'
import { Surface } from '@/components/ui/surface'
import { Eyebrow } from '@/components/ui/eyebrow'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

const STATUS_META: Record<
  ServiceStatus['status'],
  { label: string; dot: string; text: string }
> = {
  up: { label: 'Running', dot: 'bg-[hsl(var(--sla-ok))]', text: 'text-[hsl(var(--sla-ok))]' },
  in_process: { label: 'In-process', dot: 'bg-primary', text: 'text-primary' },
  optional: { label: 'Optional · not running', dot: 'bg-muted-foreground/50', text: 'text-muted-foreground' },
  down: { label: 'Down', dot: 'bg-destructive', text: 'text-destructive' },
  unknown: { label: 'Unknown', dot: 'bg-muted-foreground/40', text: 'text-muted-foreground' },
}

// used/running first, optional/down last
const ORDER: Record<ServiceStatus['status'], number> = {
  up: 0,
  in_process: 1,
  down: 2,
  optional: 3,
  unknown: 4,
}

export function ServiceMap() {
  const query = useQuery({
    queryKey: ['services', 'status'],
    queryFn: () => apiClient.getServiceStatus(),
    refetchInterval: 10_000,
  })

  const services = [...(query.data?.services ?? [])].sort((a, b) => {
    if (a.required !== b.required) return a.required ? -1 : 1
    return ORDER[a.status] - ORDER[b.status]
  })
  const up = services.filter((s) => s.status === 'up' || s.status === 'in_process').length

  return (
    <Surface tone="operational" pad="md" className="space-y-3">
      <div className="flex items-center justify-between">
        <Eyebrow className="flex items-center gap-1.5">
          <Boxes className="size-3.5" />
          Service map · what&apos;s running and where it&apos;s used
        </Eyebrow>
        <span className="flex items-center gap-1.5 font-mono text-2xs text-muted-foreground">
          {query.isFetching ? <RefreshCw className="size-3 animate-spin" /> : null}
          {services.length ? `${up}/${services.length} up` : '—'}
        </span>
      </div>

      <div className="divide-y divide-border/60">
        {services.map((s) => {
          const st = STATUS_META[s.status]
          return (
            <div key={s.key} className="grid grid-cols-[1fr_auto] items-start gap-3 py-2">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className={cn('size-2 shrink-0 rounded-full', st.dot)} aria-hidden />
                  <span className="text-sm font-medium">{s.name}</span>
                  {s.required ? (
                    <Badge variant="outline" className="text-3xs uppercase tracking-wide">
                      required
                    </Badge>
                  ) : (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Badge variant="muted" className="cursor-help text-3xs uppercase tracking-wide">
                          optional
                        </Badge>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        {s.why || 'Optional service.'}
                      </TooltipContent>
                    </Tooltip>
                  )}
                </div>
                <p className="mt-0.5 truncate text-xs text-muted-foreground">{s.purpose}</p>
                <p className="truncate text-2xs text-muted-foreground/80">
                  <span className="uppercase tracking-wide">used by</span> · {s.used_by}
                </p>
              </div>
              <span className={cn('shrink-0 font-mono text-2xs', st.text)}>{st.label}</span>
            </div>
          )
        })}
        {!services.length && query.isLoading ? (
          <p className="py-4 text-center text-xs text-muted-foreground">Probing services…</p>
        ) : null}
      </div>
    </Surface>
  )
}
