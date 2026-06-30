import * as React from 'react'
import { cn } from '@/lib/cn'
import { Eyebrow } from '@/components/ui/eyebrow'

/**
 * Compact L1-style stat block: mono-uppercase eyebrow over a big tabular number, with an
 * optional delta / hint line. Numbers render in JetBrains Mono with tabular-nums so columns
 * of figures line up (study S1).
 */
export interface StatProps extends React.HTMLAttributes<HTMLDivElement> {
  label: React.ReactNode
  value: React.ReactNode
  icon?: React.ReactNode
  hint?: React.ReactNode
  /** Optional accent colour for the value (e.g. a risk hsl()). */
  valueClassName?: string
}

export function Stat({ label, value, icon, hint, valueClassName, className, ...props }: StatProps) {
  return (
    <div className={cn('flex flex-col gap-0.5', className)} {...props}>
      <Eyebrow className="flex items-center gap-1.5">
        {icon}
        {label}
      </Eyebrow>
      <span
        className={cn('font-mono text-2xl font-semibold leading-tight tabular-nums', valueClassName)}
      >
        {value}
      </span>
      {hint ? <span className="text-2xs text-muted-foreground">{hint}</span> : null}
    </div>
  )
}
