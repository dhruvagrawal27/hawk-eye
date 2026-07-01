import { cn } from '@/lib/cn'

export function PageHeader({
  title,
  description,
  actions,
  icon,
  className,
}: {
  title: React.ReactNode
  description?: React.ReactNode
  actions?: React.ReactNode
  icon?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-wrap items-start justify-between gap-3 pb-1', className)}>
      <div className="flex items-start gap-3">
        {icon ? (
          <div className="mt-1 flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary ring-1 ring-inset ring-primary/15">
            {icon}
          </div>
        ) : null}
        <div>
          {/* Editorial display serif (Fraunces) — the Daylight Forensics headline voice. */}
          <h1 className="font-display text-2xl font-semibold leading-tight tracking-[-0.01em] text-foreground">
            {title}
          </h1>
          {description ? (
            <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground">
              {description}
            </p>
          ) : null}
        </div>
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  )
}
