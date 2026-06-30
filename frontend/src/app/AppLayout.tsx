import { Suspense } from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'
import { Spinner } from '@/components/ui/spinner'

/** Authenticated shell: left nav + top bar + the routed view (lazy-loaded, Suspense-wrapped). */
export function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden">
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
  )
}
