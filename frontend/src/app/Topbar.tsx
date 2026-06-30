import { ChevronDown, LogOut, UserCog } from 'lucide-react'
import { useAuth } from '@/auth/rbac'
import { HUMAN_ROLES, ROLE_META } from '@/auth/capabilities'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { DensityToggle } from '@/components/ui/density-toggle'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { IstClock } from './IstClock'

function initials(name: string): string {
  return name
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

/** Top bar: IST clock, demo role switcher (mock mode), and the user menu (logout). */
export function Topbar() {
  const { user, role, roles, isMock, setActiveRole, logout } = useAuth()
  if (!user || !role) return null

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border bg-background/80 px-4 backdrop-blur">
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="font-normal">
          {ROLE_META[role].short}
        </Badge>
      </div>

      <div className="flex items-center gap-3">
        <IstClock />
        <DensityToggle />

        {/* Demo role switcher (mock SSO) — swap persona to inspect RBAC end-to-end. */}
        {isMock ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="gap-1.5">
                <UserCog className="size-4" />
                Switch role
                <ChevronDown className="size-3.5 opacity-60" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>Demo persona</DropdownMenuLabel>
              {HUMAN_ROLES.map((r) => (
                <DropdownMenuItem key={r} onClick={() => setActiveRole(r)}>
                  <span className={r === role ? 'font-semibold text-primary' : ''}>
                    {ROLE_META[r].label}
                  </span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              className="flex items-center gap-2 rounded-full focus-ring"
              aria-label="User menu"
            >
              <Avatar>
                <AvatarFallback>{initials(user.name)}</AvatarFallback>
              </Avatar>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-60">
            <DropdownMenuLabel>
              <div className="leading-tight">
                <p className="text-sm font-medium text-foreground">{user.name}</p>
                <p className="text-xs font-normal text-muted-foreground">{user.username}</p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <div className="px-2 py-1 text-[0.7rem] text-muted-foreground">
              Roles: {roles.map((r) => ROLE_META[r].short).join(', ')}
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              onClick={() => void logout()}
              className="text-destructive focus:text-destructive"
            >
              <LogOut className="size-4" /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
