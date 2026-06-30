import { useId } from 'react'
import {
  CheckSquare,
  FileSearch,
  GitBranch,
  Moon,
  Paperclip,
  ShieldCheck,
  UserCheck,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/cn'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'

/**
 * Structured Enhanced-Due-Diligence checklist (FRONTEND-11; Blueprint Part 11 l.392 + Part 24.4
 * §24.4 + natural justice). These are the diligence steps an investigator works through *before*
 * disposing — verifying the beneficiary, the maker-checker approval trail, the peer baseline, the
 * off-hours justification, and that evidence is attached. The list is advisory (it documents the
 * investigation), controlled by the parent which owns the `Record<stepKey, boolean>` value.
 */
export interface EddStep {
  key: string
  label: string
  description: string
  icon: LucideIcon
}

/** Canonical EDD steps. Exported so a parent can compute completeness / show counts. */
export const EDD_STEPS: EddStep[] = [
  {
    key: 'verified_beneficiary',
    label: 'Verified beneficiary',
    description: 'Confirmed the beneficiary / counterparty is legitimate and not a known mule.',
    icon: UserCheck,
  },
  {
    key: 'reviewed_approval_trail',
    label: 'Reviewed approval trail',
    description: 'Checked the maker-checker chain for self-approval or four-eyes bypass.',
    icon: ShieldCheck,
  },
  {
    key: 'checked_peer_baseline',
    label: 'Checked peer baseline',
    description:
      'Compared the actor against their peer-group distribution for the flagged behaviour.',
    icon: GitBranch,
  },
  {
    key: 'confirmed_offhours',
    label: 'Confirmed off-hours justification',
    description: 'Established whether off-hours / unusual-channel activity has a business reason.',
    icon: Moon,
  },
  {
    key: 'reviewed_explanation',
    label: 'Reviewed model explanation',
    description: 'Read the SHAP / rule / graph evidence so the decision is informed, not deferred.',
    icon: FileSearch,
  },
  {
    key: 'attached_evidence',
    label: 'Attached evidence',
    description: 'Linked the supporting event ids that substantiate the disposition.',
    icon: Paperclip,
  },
]

export function EddChecklist({
  value,
  onChange,
  steps = EDD_STEPS,
  className,
}: {
  value: Record<string, boolean>
  onChange: (v: Record<string, boolean>) => void
  steps?: EddStep[]
  className?: string
}) {
  const baseId = useId()
  const done = steps.reduce((n, s) => n + (value[s.key] ? 1 : 0), 0)

  function toggle(key: string, checked: boolean) {
    onChange({ ...value, [key]: checked })
  }

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-center justify-between">
        <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <CheckSquare className="size-3.5" aria-hidden />
          Due-diligence checklist
        </p>
        <span className="text-xs tabular-nums text-muted-foreground" aria-live="polite">
          {done}/{steps.length} complete
        </span>
      </div>

      <ul className="space-y-1">
        {steps.map((step) => {
          const id = `${baseId}-${step.key}`
          const checked = Boolean(value[step.key])
          const Icon = step.icon
          return (
            <li key={step.key}>
              <Label
                htmlFor={id}
                className={cn(
                  'flex cursor-pointer items-start gap-2.5 rounded-md border p-2.5 font-normal transition-colors',
                  checked
                    ? 'border-sla-ok/30 bg-sla-ok/5'
                    : 'border-border hover:border-input hover:bg-accent/40',
                )}
              >
                <Checkbox
                  id={id}
                  checked={checked}
                  onCheckedChange={(c) => toggle(step.key, c === true)}
                  className="mt-0.5"
                />
                <div className="min-w-0 flex-1 space-y-0.5">
                  <span className="flex items-center gap-1.5 text-sm font-medium leading-tight">
                    <Icon
                      className={cn(
                        'size-3.5 shrink-0',
                        checked ? 'text-sla-ok' : 'text-muted-foreground',
                      )}
                      aria-hidden
                    />
                    {step.label}
                  </span>
                  <span className="block text-xs leading-snug text-muted-foreground">
                    {step.description}
                  </span>
                </div>
              </Label>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
