import { Link } from 'react-router-dom'
import { ShieldX } from 'lucide-react'
import { useAuth } from '@/auth/rbac'
import { ROLE_META } from '@/auth/capabilities'
import { Button } from '@/components/ui/button'

/** 403 surface — a route the active role may not see (RBAC defense-in-depth; server is authoritative). */
export function Forbidden() {
  const { role } = useAuth()
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
      <ShieldX className="size-10 text-destructive" />
      <h1 className="text-xl font-semibold">Not permitted for your role</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        This screen is outside the permissions of {role ? ROLE_META[role].label : 'your role'} (Part
        24.1 RBAC). Every view is gated and every access is audited.
      </p>
      {role ? (
        <Button asChild variant="outline">
          <Link to={ROLE_META[role].defaultRoute}>Go to your home screen</Link>
        </Button>
      ) : null}
    </div>
  )
}
