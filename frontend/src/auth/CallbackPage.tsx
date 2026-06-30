import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2, AlertTriangle } from 'lucide-react'
import { useAuth } from './rbac'
import { Button } from '@/components/ui/button'

/** OIDC redirect callback (FRONTEND-2). Completes the PKCE code→token exchange, then lands the user. */
export function CallbackPage() {
  const { completeSignin } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    completeSignin()
      .then(() => {
        if (!cancelled) navigate('/', { replace: true })
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Sign-in could not be completed.')
      })
    return () => {
      cancelled = true
    }
  }, [completeSignin, navigate])

  return (
    <div className="flex h-screen flex-col items-center justify-center gap-3">
      {error ? (
        <>
          <AlertTriangle className="size-6 text-destructive" />
          <p className="text-sm text-destructive">{error}</p>
          <Button asChild variant="outline" size="sm">
            <Link to="/login">Back to sign in</Link>
          </Button>
        </>
      ) : (
        <>
          <Loader2 className="size-6 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Completing sign-in…</p>
        </>
      )}
    </div>
  )
}
