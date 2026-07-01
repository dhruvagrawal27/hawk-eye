import { describe, expect, it } from 'vitest'
import { listSourceFiles } from './sourceFiles'

/**
 * INVARIANT #5 — NO SECRETS IN THE CLIENT (durable guard).
 *
 * "No secrets in the client. Keys are runtime-injected. Don't hardcode anything."
 * (HAWK-EYE_UI_UPLIFT_PROMPTS.md). Two structural rules the uplift must never break:
 *   1. Build-time env (`import.meta.env`) is read ONLY in the env seam (`lib/env.ts`), so configuration
 *      stays centralized and injectable — no screen reaches for raw env, and there is one place to audit.
 *   2. No hardcoded high-entropy secret literals (API keys / JWTs / private keys) anywhere in `src`.
 *
 * The scanner skips this `__invariants__/` dir, so the guard never trips on its own pattern literals.
 */
// The env seam plus one dev-only exception: MSW worker registration needs Vite's PUBLIC `BASE_URL`
// (a base path, not a secret) to locate `mockServiceWorker.js`. No real config/secret reads here.
const ENV_READERS = new Set(['lib/env.ts', 'lib/mocks/enable.ts'])

describe('no secrets in client · env confined to the seam + no hardcoded keys', () => {
  it('reads import.meta.env only in the env seam (lib/env.ts, + MSW worker registration)', () => {
    const offenders = listSourceFiles({ includeTests: false, includeMocks: true })
      .filter((f) => !ENV_READERS.has(f.rel) && /import\.meta\.env/.test(f.text))
      .map((f) => f.rel)
    expect(offenders, `import.meta.env must only be read in: ${[...ENV_READERS].join(', ')}`).toEqual(
      [],
    )
  })

  it('hardcodes no high-entropy secret literals in app code', () => {
    // Real-secret-shaped patterns only — conservative so dev placeholders ('hawk-eye',
    // 'dev-only-change-me') never false-positive.
    const SECRET =
      /(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|-----BEGIN (?:RSA |EC )?PRIVATE KEY-----)/
    const offenders = listSourceFiles({ includeTests: false, includeMocks: false })
      .filter((f) => SECRET.test(f.text))
      .map((f) => f.rel)
    expect(offenders, 'no hardcoded API keys / JWTs / private keys in the client').toEqual([])
  })
})
