import { RouterProvider } from 'react-router-dom'
import { Providers } from '@/app/Providers'
import { ErrorBoundary } from '@/app/ErrorBoundary'
import { router } from '@/app/router'

export function App() {
  return (
    <ErrorBoundary>
      <Providers>
        <RouterProvider router={router} />
      </Providers>
    </ErrorBoundary>
  )
}
