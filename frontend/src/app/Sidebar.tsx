import { NavLink } from 'react-router-dom'
import { Eye, ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/cn'
import { useAuth } from '@/auth/rbac'
import { ROLE_META } from '@/auth/capabilities'
import { navItemsForRole } from './nav-config'

/** Left rail navigation, filtered to the active role's permitted screens (Part 24.1). */
export function Sidebar() {
  const { role } = useAuth()
  const items = navItemsForRole(role)

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex">
      <div className="flex h-14 items-center gap-2.5 border-b border-sidebar-border px-4">
        <div className="flex size-7 items-center justify-center rounded-md bg-primary/15 text-primary">
          <Eye className="size-4" />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-semibold tracking-tight">Hawk-Eye</p>
          <p className="text-[0.65rem] text-sidebar-foreground/50">Investigator console</p>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
        {items.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-sidebar-accent text-sidebar-foreground'
                    : 'text-sidebar-foreground/65 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground',
                )
              }
            >
              <Icon className="size-4 shrink-0" />
              {item.label}
            </NavLink>
          )
        })}
      </nav>

      <div className="border-t border-sidebar-border p-3">
        <div className="flex items-center gap-2 rounded-md bg-sidebar-accent/50 px-2.5 py-2 text-xs">
          <ShieldCheck className="size-3.5 text-tee" />
          <div className="leading-tight">
            <p className="font-medium text-sidebar-foreground">Alert-only</p>
            <p className="text-[0.65rem] text-sidebar-foreground/50">A human always decides</p>
          </div>
        </div>
        {role ? (
          <p className="mt-2 px-1 text-[0.65rem] text-sidebar-foreground/40">
            Signed in as {ROLE_META[role].label}
          </p>
        ) : null}
      </div>
    </aside>
  )
}
