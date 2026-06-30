import { setupServer } from 'msw/node'
import { handlers } from './handlers'

/** Node MSW server for Vitest unit/contract tests (src/test/setup.ts wires the lifecycle). */
export const server = setupServer(...handlers)
