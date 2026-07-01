/**
 * PaperField — opt-in textured surface for empty regions / hero rails (docs/ui/UI_UPLIFT.md §1.8).
 *
 * Wraps the `.bg-paper-grain` (micro-noise) and `.bg-blueprint` (hairline graph grid) utilities behind
 * a component so B applies texture consistently — and only where it belongs (empty states, section
 * headers, hero rails). **Never** put texture behind dense data; that's an explicit house rule.
 */
import type { ElementType, ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface PaperFieldProps {
  as?: ElementType
  /** Micro paper-grain noise. */
  grain?: boolean
  /** Hairline blueprint / graph-paper grid. */
  grid?: boolean
  className?: string
  children?: ReactNode
}

export function PaperField({
  as,
  grain = true,
  grid = false,
  className,
  children,
}: PaperFieldProps) {
  const Comp = (as ?? 'div') as ElementType
  return (
    <Comp
      className={cn(
        'relative bg-background',
        grain && 'bg-paper-grain',
        grid && 'bg-blueprint',
        className,
      )}
    >
      {children}
    </Comp>
  )
}
