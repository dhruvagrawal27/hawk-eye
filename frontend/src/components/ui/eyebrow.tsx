import * as React from 'react'
import { cn } from '@/lib/cn'

/**
 * Bloomberg-style mono-uppercase eyebrow — the little label above a panel/stat/section.
 * One of the cheapest "terminal, not dashboard" tells (study S1).
 */
export const Eyebrow = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn(
      'font-mono text-2xs font-medium uppercase tracking-widest text-muted-foreground',
      className,
    )}
    {...props}
  />
))
Eyebrow.displayName = 'Eyebrow'
