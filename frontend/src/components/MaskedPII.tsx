import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Eye, EyeOff, Loader2, Lock, ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/cn'
import { apiClient } from '@/lib/apiClient'
import { useAuth } from '@/auth/rbac'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { toast } from '@/components/ui/toaster'
import type { UnmaskResponse } from '@/lib/types'

/**
 * Tokenized-PII renderer with an **audited unmask** control (FRONTEND-3; Part 25.3). Shows the token
 * by default; the unmask action calls `POST /entities/{id}/unmask` and is shown only for roles with
 * the `unmask_pii` capability (Senior+, case-scoped+logged for Analyst). The reveal surfaces that the
 * action was logged server-side ("watch-the-watchers") with the returned audit_id.
 *
 * `entityId` is the unmask target (entity tokens). Without it (or without permission) it renders the
 * token read-only — every other PII token still defaults to masked.
 */
export function MaskedPII({
  value,
  entityId,
  alertId,
  className,
  iconOnly = false,
}: {
  value: string
  entityId?: string
  alertId?: string
  className?: string
  iconOnly?: boolean
}) {
  const { can, constraintFor } = useAuth()
  const [revealed, setRevealed] = useState<UnmaskResponse | null>(null)
  const allowed = can('unmask_pii') && Boolean(entityId)
  const constraint = constraintFor('unmask_pii')

  const unmask = useMutation({
    mutationFn: () => apiClient.unmaskEntity(entityId as string, { alert_id: alertId }),
    onSuccess: (res) => {
      setRevealed(res)
      toast.success('PII unmasked', {
        description: `Re-identification logged server-side · ${res.audit_id}`,
      })
    },
    onError: () => toast.error('Unmask failed'),
  })

  if (revealed) {
    return (
      <span className={cn('inline-flex items-center gap-1.5', className)}>
        <span className="font-medium">{revealed.value}</span>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-flex items-center gap-0.5 text-tee">
              <ShieldCheck className="size-3.5" />
              <span className="text-[0.7rem]">logged</span>
            </span>
          </TooltipTrigger>
          <TooltipContent>Re-identification audited · {revealed.audit_id}</TooltipContent>
        </Tooltip>
        <button
          type="button"
          onClick={() => setRevealed(null)}
          className="text-muted-foreground hover:text-foreground focus-ring"
          aria-label="Re-mask"
        >
          <EyeOff className="size-3.5" />
        </button>
      </span>
    )
  }

  return (
    <span className={cn('inline-flex items-center gap-1', className)}>
      <span className="tok">{value}</span>
      {allowed ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              onClick={() => unmask.mutate()}
              disabled={unmask.isPending}
              className="text-muted-foreground hover:text-primary focus-ring disabled:opacity-50"
              aria-label={`Unmask ${value} (audited)`}
            >
              {unmask.isPending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Eye className="size-3.5" />
              )}
            </button>
          </TooltipTrigger>
          <TooltipContent>
            Unmask PII — audited{constraint ? ` (${constraint})` : ''}.
            {alertId ? ' Case-scoped to this alert.' : ''}
          </TooltipContent>
        </Tooltip>
      ) : !iconOnly ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <Lock className="size-3 text-muted-foreground" aria-label="Unmask not permitted" />
          </TooltipTrigger>
          <TooltipContent>Tokenized PII. Unmask is not permitted for your role.</TooltipContent>
        </Tooltip>
      ) : null}
    </span>
  )
}
