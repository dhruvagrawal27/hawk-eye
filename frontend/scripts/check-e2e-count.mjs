#!/usr/bin/env node
/**
 * Playwright e2e-count floor gate (Agent C · hawk-eye/ui-integrity).
 *
 * The MSW-mocked vertical slice must keep at least the contractual ≥3 browser e2e (GETTING_STARTED §8 /
 * HAWK-EYE_UI_UPLIFT_PROMPTS.md). This is a static count (no browser needed) so it can run everywhere,
 * including on machines without a Playwright browser installed.
 */
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const E2E_DIR = 'e2e'
const MIN_E2E = 3

function fail(msg) {
  console.error(`\n✗ e2e-count gate FAILED: ${msg}\n`)
  process.exit(1)
}

let count = 0
const perFile = []
for (const f of readdirSync(E2E_DIR)) {
  if (!f.endsWith('.e2e.ts')) continue
  const text = readFileSync(join(E2E_DIR, f), 'utf8')
  // Count `test(` / `test.only(` / `test.fixme(...)` declarations, not `test.describe(`/`test.step(`.
  const n = (text.match(/(?<![.\w])test(?:\.(?:only|fixme|skip))?\s*\(/g) ?? []).length
  perFile.push(`  ${f}: ${n}`)
  count += n
}

console.log(`Playwright e2e tests:\n${perFile.join('\n')}\n  total: ${count} (floor ≥${MIN_E2E})`)
if (count < MIN_E2E) fail(`only ${count} e2e test(s); floor is ≥${MIN_E2E}`)
console.log('✓ e2e-count gate: OK')
