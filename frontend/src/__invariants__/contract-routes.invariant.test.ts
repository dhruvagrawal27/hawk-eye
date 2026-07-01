import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { listSourceFiles, REPO_ROOT } from './sourceFiles'

/**
 * INVARIANT #6 — DON'T BREAK THE DATA CONTRACT (durable guard).
 *
 * "Do not invent API fields or change response shapes; respect `backend/openapi.json`. Anything net-new
 *  stays flagged `[FE-proposed]`." (HAWK-EYE_UI_UPLIFT_PROMPTS.md)
 *
 * Components never call `fetch`; every request goes through the typed `apiClient` seam. This guard
 * extracts every route the client calls and asserts each one is EITHER published in the backend OpenAPI
 * contract OR on the explicit `[FE-proposed]` allowlist below (each flagged in CONTEXT.md, per TODO §7).
 * A new route that is neither trips the gate — catching contract drift the moment it lands.
 */

/** Routes the frontend calls that are NOT (yet) in `backend/openapi.json` — flagged [FE-proposed] in
 * CONTEXT.md (2026-06-30 [FRONTEND]) and bound to MSW until BACKEND finalises them. Canonical form:
 * leading `/`, `{}` for every path parameter, no query string. */
const FE_PROPOSED: ReadonlySet<string> = new Set([
  '/entities/{}/score-history',
  '/graph',
  '/narratives/{}/attestation',
  '/services/status',
  '/explanations/{}/report',
  '/reports/ews-coverage',
  '/reports/kris',
  '/cases',
  '/cases/{}',
  '/cases/{}/status',
  '/cases/{}/assign',
  '/cases/{}/notes',
  // Newer main endpoints (insider-10x + L6.5 interdiction) the apiClient calls but that are not yet in
  // the committed main-API openapi.json (the action-gate service is a separate :8096 surface). Bound to
  // MSW; flagged [FE-proposed] in CONTEXT.md until BACKEND folds them into openapi.json.
  '/alerts/stats',
  '/entities/{}/risk-index',
  '/entities/{}/layer-scores',
  '/analytics/typologies',
  '/activity/sub-threshold?limit={}',
  '/action-gate/holds',
  '/action-gate/holds/{}/decision',
  '/action-gate/policies',
  // Root ops readiness probe (served at the server ROOT like /health) — reports live NEAR AI + Intel
  // TDX TEE status; newer than the committed openapi.json snapshot, folded in on next regen.
  '/readyz',
])

/** Normalise any route to canonical form: strip an `/api/v1` prefix, collapse `{param}` and `${expr}`
 * template segments to `{}`, and drop a trailing slash. */
function canonical(route: string): string {
  return route
    .replace(/^\/api\/v1/, '')
    .replace(/\$\{[^}]*\}/g, '{}') // template literal interpolation → {}
    .replace(/\{[^}]*\}/g, '{}') // OpenAPI {param} → {}
    .replace(/\/$/, '')
}

/** Every route literal the apiClient passes to `request('…')`. */
function apiClientRoutes(): string[] {
  const src = listSourceFiles({ includeMocks: false }).find((f) => f.rel === 'lib/apiClient.ts')
  expect(src, 'lib/apiClient.ts must exist').toBeTruthy()
  const re = /request(?:<[^>]*>)?\(\s*[`'"]([^`'"]+)[`'"]/g
  const out = new Set<string>()
  let m: RegExpExecArray | null
  while ((m = re.exec(src!.text)) !== null) out.add(canonical(m[1]))
  return [...out]
}

function openApiRoutes(): Set<string> {
  const raw = readFileSync(join(REPO_ROOT, 'backend', 'openapi.json'), 'utf8')
  const spec = JSON.parse(raw) as { paths?: Record<string, unknown> }
  const out = new Set<string>()
  for (const p of Object.keys(spec.paths ?? {})) out.add(canonical(p))
  return out
}

describe('data contract · apiClient routes ⊆ openapi ∪ [FE-proposed]', () => {
  const openapi = openApiRoutes()
  const routes = apiClientRoutes()

  it('reads a non-trivial OpenAPI contract', () => {
    expect(openapi.size).toBeGreaterThan(10)
  })

  it('extracts the apiClient route surface', () => {
    expect(routes.length).toBeGreaterThan(20)
  })

  it('invents no route: every client call is published or explicitly [FE-proposed]', () => {
    const invented = routes.filter((r) => !openapi.has(r) && !FE_PROPOSED.has(r))
    expect(
      invented,
      `routes neither in backend/openapi.json nor flagged [FE-proposed] in CONTEXT.md:\n  ${invented.join('\n  ')}`,
    ).toEqual([])
  })

  it('keeps the [FE-proposed] allowlist honest (warns when BACKEND has since published one)', () => {
    // Not a hard failure (a BACKEND change shouldn't red the FE gate), but a loud drift signal so C
    // can promote the route out of the allowlist and off the [FE-proposed] flag.
    const promoted = [...FE_PROPOSED].filter((r) => openapi.has(r))
    if (promoted.length > 0) {
      console.warn(
        `[contract-drift] BACKEND now publishes these once-[FE-proposed] routes — remove from allowlist + CONTEXT.md: ${promoted.join(', ')}`,
      )
    }
    expect(true).toBe(true)
  })
})
