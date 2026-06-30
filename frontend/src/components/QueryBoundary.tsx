import { AlertTriangle } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { ApiError } from '@/lib/http'

/** Standard loading/error wrapper for a TanStack Query result so every panel degrades the same way. */
export function QueryBoundary({
  isLoading,
  isError,
  error,
  onRetry,
  skeleton,
  children,
}: {
  isLoading: boolean
  isError?: boolean
  error?: unknown
  onRetry?: () => void
  skeleton?: React.ReactNode
  children: React.ReactNode
}) {
  if (isLoading) {
    return (
      <>
        {skeleton ?? (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        )}
      </>
    )
  }
  if (isError) {
    const message =
      error instanceof ApiError ? error.message : 'Something went wrong loading this panel.'
    return (
      <div className="flex flex-col items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center">
        <AlertTriangle className="size-6 text-destructive" />
        <p className="text-sm font-medium text-destructive">{message}</p>
        {onRetry ? (
          <Button variant="outline" size="sm" onClick={onRetry}>
            Retry
          </Button>
        ) : null}
      </div>
    )
  }
  return <>{children}</>
}
