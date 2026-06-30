import { env } from '../env'

/**
 * Start the MSW browser worker iff `VITE_USE_MOCKS=true` (prompt §3: same components run against the
 * real API when mocks are off — one switch). Imported dynamically in main.tsx before render so the
 * worker is intercepting before the first request fires.
 */
export async function startMocks(): Promise<void> {
  if (!env.useMocks) return
  const { worker } = await import('./browser')
  await worker.start({
    onUnhandledRequest: 'bypass',
    quiet: true,
    serviceWorker: { url: `${import.meta.env.BASE_URL}mockServiceWorker.js` },
  })
}
