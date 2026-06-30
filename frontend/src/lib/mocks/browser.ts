import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'

/** Browser MSW worker (dev / e2e). Started by enable.ts when VITE_USE_MOCKS=true. */
export const worker = setupWorker(...handlers)
