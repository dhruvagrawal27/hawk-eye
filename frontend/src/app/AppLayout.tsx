import { Suspense } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { Spinner } from '@/components/ui/spinner'
import { TopStatusBar } from '@/components/layout/TopStatusBar'
import { CommandPalette } from '@/components/command/CommandPalette'
import { OnboardingOverlay } from '@/components/OnboardingOverlay'

/** Authenticated shell: a Bloomberg-style status strip, left nav + top bar, the routed view
 * (lazy-loaded, Suspense-wrapped), and the global Cmd-K command palette. */
export function AppLayout() {
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TopStatusBar />
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar />
          <main className="flex-1 overflow-y-auto">
            <div className="mx-auto w-full max-w-[1480px] p-4 md:p-6">
              <Suspense
                fallback={
                  <div className="flex h-64 items-center justify-center">
                    <Spinner className="size-6" />
                  </div>
                }
              >
                <Outlet />
              </Suspense>
            </div>
          </main>
        </div>
      </div>
      <CommandPalette />
      <OnboardingOverlay />
    </div>
  )
}
