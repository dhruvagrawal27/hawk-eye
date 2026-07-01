import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Eye, Fingerprint, KeyRound, Loader2, ShieldCheck } from 'lucide-react'
import { useAuth } from './rbac'
import { HUMAN_ROLES, ROLE_META } from './capabilities'
import { LOCAL_PASSWORD, LOCAL_PERSONAS } from './localAuth'
import type { Role } from '@/lib/types'
import { env } from '@/lib/env'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/cn'

/**
 * Screen 1 — Login / SSO (Part 24.4 l.946; FRONTEND-2). Real mode redirects to Keycloak (OIDC
 * Authorization-Code + PKCE); MFA is enforced by the IdP and surfaced as the redirect step. In
 * mock/dev (VITE_USE_MOCKS) a persona picker simulates SSO+MFA so the console runs with no IdP —
 * the same `login()` seam drives both.
 */
export function LoginPage() {
  const { status, login, isMock, role } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [pending, setPending] = useState<Role | 'oidc' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const isLocal = env.authMode === 'local'
  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname

  useEffect(() => {
    if (status === 'authenticated' && role) {
      navigate(from ?? ROLE_META[role].defaultRoute, { replace: true })
    }
  }, [status, role, from, navigate])

  const signIn = async (r?: Role) => {
    setPending(r ?? 'oidc')
    setError(null)
    try {
      await login(r)
    } catch {
      setError('Sign-in failed. Check that the backend is running and try again.')
    } finally {
      setPending(null)
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      {/* Brand / hero */}
      <div className="relative hidden flex-col justify-between overflow-hidden bg-sidebar p-10 text-sidebar-foreground lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.18]"
          style={{
            background:
              'radial-gradient(60% 50% at 30% 20%, hsl(var(--primary)/0.5), transparent), radial-gradient(40% 40% at 80% 80%, hsl(var(--ai)/0.4), transparent)',
          }}
        />
        <div className="relative flex items-center gap-2.5">
          <div className="flex size-9 items-center justify-center rounded-lg bg-primary/15 text-primary">
            <Eye className="size-5" />
          </div>
          <span className="text-lg font-semibold tracking-tight">Hawk-Eye</span>
        </div>
        <div className="relative space-y-4">
          <h1 className="text-3xl font-semibold leading-tight tracking-tight">
            Insider &amp; privileged-user
            <br />
            fraud detection
          </h1>
          <p className="max-w-md text-sm text-sidebar-foreground/70">
            Triage, investigate, explain and act on insider-fraud alerts. Every view is RBAC-gated
            and every action is audited. The system scores and explains —{' '}
            <strong>a human always decides.</strong>
          </p>
          <ul className="space-y-1.5 text-sm text-sidebar-foreground/70">
            <li className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-tee" /> Alert-only — never auto-blocks money
            </li>
            <li className="flex items-center gap-2">
              <KeyRound className="size-4 text-primary" /> Tokenized PII by default; unmask is
              audited
            </li>
            <li className="flex items-center gap-2">
              <Fingerprint className="size-4 text-ai" /> OIDC SSO with MFA; short-lived in-memory
              JWTs
            </li>
          </ul>
        </div>
        <p className="relative text-xs text-sidebar-foreground/50">
          On-prem · synthetic data only · blueprint Part 11 / 24
        </p>
      </div>

      {/* Sign-in */}
      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm space-y-6">
          <div className="space-y-1.5 lg:hidden">
            <div className="flex items-center gap-2">
              <Eye className="size-5 text-primary" />
              <span className="text-lg font-semibold">Hawk-Eye</span>
            </div>
          </div>

          <div>
            <h2 className="text-xl font-semibold tracking-tight">Sign in</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              {isLocal
                ? 'Local sign-in — pick a persona to authenticate against the backend directory.'
                : 'Authenticate via your bank SSO. Multi-factor is enforced by the identity provider.'}
            </p>
          </div>

          {!isLocal ? (
            <Button
              className="w-full"
              size="lg"
              onClick={() => signIn()}
              disabled={pending !== null}
            >
              {pending === 'oidc' ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <KeyRound className="size-4" />
              )}
              Sign in with Keycloak (OIDC)
            </Button>
          ) : null}

          {error ? (
            <p className="text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : null}

          {isLocal ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                {LOCAL_PERSONAS.map((p) => (
                  <Card
                    key={p.role}
                    role="button"
                    tabIndex={0}
                    onClick={() => signIn(p.role)}
                    onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && signIn(p.role)}
                    className={cn(
                      'cursor-pointer p-3 transition-colors hover:border-primary/60 hover:bg-accent focus-ring',
                      pending === p.role && 'border-primary',
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{ROLE_META[p.role].short}</span>
                      {pending === p.role ? (
                        <Loader2 className="size-3.5 animate-spin text-primary" />
                      ) : null}
                    </div>
                    <p className="mt-0.5 text-[0.7rem] text-muted-foreground">
                      {p.name} · {p.username}
                    </p>
                  </Card>
                ))}
              </div>
              <p className="text-center text-xs text-muted-foreground">
                Local auth mode — POSTs {`{username, password: "${LOCAL_PASSWORD}"}`} to the
                backend. No Keycloak required.
              </p>
            </div>
          ) : null}

          {isMock ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <div className="h-px flex-1 bg-border" />
                demo personas (mock SSO + MFA)
                <div className="h-px flex-1 bg-border" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                {HUMAN_ROLES.map((r) => (
                  <Card
                    key={r}
                    role="button"
                    tabIndex={0}
                    onClick={() => signIn(r)}
                    onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && signIn(r)}
                    className={cn(
                      'cursor-pointer p-3 transition-colors hover:border-primary/60 hover:bg-accent focus-ring',
                      pending === r && 'border-primary',
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{ROLE_META[r].short}</span>
                      {pending === r ? (
                        <Loader2 className="size-3.5 animate-spin text-primary" />
                      ) : null}
                    </div>
                    <p className="mt-1 line-clamp-2 text-[0.7rem] leading-snug text-muted-foreground">
                      {ROLE_META[r].description}
                    </p>
                  </Card>
                ))}
              </div>
              <p className="text-center text-xs text-muted-foreground">
                Mock mode (VITE_USE_MOCKS) — no real IdP, no real PII.
              </p>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
