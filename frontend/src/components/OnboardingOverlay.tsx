/**
 * First-run guided tour (Agent C). A role-aware Radix Dialog shown once per browser
 * (localStorage flag `hawkeye:onboarded`). It greets the signed-in persona, walks the nav surfaces
 * that role can actually reach (from `navItemsForRole`), and offers a "Load demo scenario" CTA that
 * front-loads a high-risk burst onto the realtime seam (`realtime.injectBurst()`) so the demo lights
 * up within seconds. Mounted once in AppLayout — it self-suppresses after the first dismissal.
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Compass, PlayCircle, Sparkles } from 'lucide-react'
import { useAuth } from '@/auth/rbac'
import { ROLE_META } from '@/auth/capabilities'
import { navItemsForRole } from '@/app/nav-config'
import { realtime } from '@/lib/realtime'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Eyebrow } from '@/components/ui/eyebrow'
import { toast } from '@/components/ui/toaster'

const ONBOARDED_KEY = 'hawkeye:onboarded'

/** Read the flag defensively — private-mode / blocked storage must never crash the shell. */
function alreadyOnboarded(): boolean {
  try {
    return localStorage.getItem(ONBOARDED_KEY) === '1'
  } catch {
    return true // storage unavailable → don't nag on every load
  }
}

function markOnboarded(): void {
  try {
    localStorage.setItem(ONBOARDED_KEY, '1')
  } catch {
    /* storage unavailable — best-effort only */
  }
}

export function OnboardingOverlay() {
  const navigate = useNavigate()
  const { user, role } = useAuth()
  const [open, setOpen] = useState(false)

  // Defer the first-run check until we actually have a role (post-auth), so the tour is role-aware.
  useEffect(() => {
    if (user && role && !alreadyOnboarded()) setOpen(true)
  }, [user, role])

  if (!user || !role) return null

  const meta = ROLE_META[role]
  const navItems = navItemsForRole(role).slice(0, 5)

  function dismiss() {
    markOnboarded()
    setOpen(false)
  }

  function goTo(to: string) {
    dismiss()
    navigate(to)
  }

  function loadDemo() {
    realtime.injectBurst()
    markOnboarded()
    setOpen(false)
    toast.success('Demo scenario loaded', {
      description: 'A high-risk mule burst is streaming into the live tape and queue.',
    })
  }

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? setOpen(true) : dismiss())}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <Eyebrow className="mb-1 flex items-center gap-1.5">
            <Sparkles className="size-3" /> Welcome to Hawkeye
          </Eyebrow>
          <DialogTitle className="text-lg">
            Hi {user.name.split(' ')[0]} — you&apos;re in
          </DialogTitle>
          <DialogDescription>
            You&apos;re signed in as{' '}
            <span className="font-medium text-foreground">{meta.label}</span> ({meta.tier} ·{' '}
            {meta.line} line of defense). {meta.description}
          </DialogDescription>
        </DialogHeader>

        <div className="rounded-lg border border-border bg-card/40 p-3">
          <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <Compass className="size-3.5" /> Your workspaces
          </div>
          <ul className="grid gap-1">
            {navItems.map((item) => (
              <li key={item.to}>
                <button
                  type="button"
                  onClick={() => goTo(item.to)}
                  className="group flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-muted/60 focus-ring"
                >
                  <item.icon className="size-4 text-muted-foreground" />
                  <span className="flex-1 font-medium">{item.label}</span>
                  <ArrowRight className="size-3.5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="flex items-start gap-2 rounded-lg border border-primary/30 bg-primary/[0.06] p-3">
          <PlayCircle className="mt-0.5 size-4 shrink-0 text-primary" />
          <div className="min-w-0 text-xs text-muted-foreground">
            <p className="font-medium text-foreground">New here? Load a demo scenario.</p>
            <p>
              Injects a synthetic high-risk mule burst so alerts fire within seconds — nothing
              auto-blocks or auto-closes.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={dismiss}>
            Skip for now
          </Button>
          <Button onClick={loadDemo} className="gap-1.5">
            <Sparkles className="size-4" /> Load demo scenario
          </Button>
        </DialogFooter>

        <div className="flex items-center justify-center">
          <Badge variant="muted" className="text-2xs">
            You can reopen this anytime by clearing site data · alert-only, human-in-the-loop
          </Badge>
        </div>
      </DialogContent>
    </Dialog>
  )
}
