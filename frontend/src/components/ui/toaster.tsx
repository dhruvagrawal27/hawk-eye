import { Toaster as SonnerToaster } from 'sonner'

/** App-wide toast surface (sonner), themed to the console. `toast()` is re-exported for callers. */
export function Toaster() {
  return (
    <SonnerToaster
      theme="dark"
      position="bottom-right"
      richColors
      closeButton
      toastOptions={{
        classNames: {
          toast: 'border border-border bg-card text-card-foreground text-sm',
          description: 'text-muted-foreground',
        },
      }}
    />
  )
}

export { toast } from 'sonner'
