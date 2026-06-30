import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/cn'

/**
 * Three-tier surface system (study §2) — instant depth via inset-highlight + colored-shadow
 * *tokens* (not @apply soup). Pick a tone by intent, not by colour:
 *   operational  dense, dark, the default working surface
 *   reference    lighter "paper" for docs / settings / mission text
 *   actionable   cooler accent for pending / approval / call-to-action panels
 */
const surfaceVariants = cva('rounded-lg border', {
  variants: {
    tone: {
      operational:
        'border-border bg-card/80 shadow-[inset_0_1px_0_0_hsl(0_0%_100%/0.04),0_4px_20px_-8px_hsl(0_0%_0%/0.5)]',
      reference:
        'border-[hsl(var(--ai)/0.18)] bg-gradient-to-br from-foreground/[0.04] via-card/90 to-card/95 shadow-[inset_0_1px_0_0_hsl(0_0%_100%/0.06),0_8px_30px_-12px_hsl(var(--ai)/0.18)]',
      actionable:
        'border-primary/30 bg-gradient-to-br from-primary/[0.07] via-card/90 to-card/95 shadow-[inset_0_1px_0_0_hsl(0_0%_100%/0.06),0_8px_30px_-12px_hsl(var(--primary)/0.25)]',
      flat: 'border-border bg-card/60',
    },
    pad: { none: 'p-0', sm: 'p-3', md: 'p-4', lg: 'p-6' },
  },
  defaultVariants: { tone: 'operational', pad: 'md' },
})

export interface SurfaceProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof surfaceVariants> {}

export const Surface = React.forwardRef<HTMLDivElement, SurfaceProps>(
  ({ className, tone, pad, ...props }, ref) => (
    <div ref={ref} className={cn(surfaceVariants({ tone, pad }), className)} {...props} />
  ),
)
Surface.displayName = 'Surface'

export { surfaceVariants }
