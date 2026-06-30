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
        {icon ? <div className="mt-0.5 text-primary">{icon}</div> : null}
        <div>
          <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
          {description ? (
            <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>
          ) : null}
        </div>
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  )
}
