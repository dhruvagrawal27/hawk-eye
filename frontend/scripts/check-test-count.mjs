#!/usr/bin/env node
/**
 * Test-count floor gate (Agent C · hawk-eye/ui-integrity).
 *
 * The UI uplift must never *drop* test coverage to go green (invariant #8). This gate runs Vitest,
 * asserts zero failures, and asserts the passing-test count stays at or above the contractual floor
 * (≥112 unit tests, per GETTING_STARTED §8 / HAWK-EYE_UI_UPLIFT_PROMPTS.md). It also asserts the
 * durable invariant-guard suite is still present, so nobody can quietly delete the safety tests.
 *
 * Usage:
 *   node scripts/check-test-count.mjs [existing-vitest-report.json]
 * With no argument it runs Vitest itself (json reporter → temp file) and parses the result.
 */
import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

/** Contractual minimum unit-test count (the uplift may only ever raise this). */
const MIN_TESTS = 112
/** The safety-invariant guard suite that must never disappear. */
const REQUIRED_GUARDS = [
  'src/__invariants__/alert-only.invariant.test.ts',
  'src/__invariants__/contestability.invariant.test.tsx',
  'src/__invariants__/audited-unmask.invariant.test.tsx',
  'src/__invariants__/rbac-routes.invariant.test.ts',
  'src/__invariants__/no-secrets.invariant.test.ts',
  'src/__invariants__/contract-routes.invariant.test.ts',
  'src/__invariants__/reduced-motion.invariant.test.tsx',
  'src/__invariants__/mocks-intact.invariant.test.ts',
]

function fail(msg) {
  console.error(`\n✗ test-count gate FAILED: ${msg}\n`)
  process.exit(1)
}

// 1) The guard files must exist (durable protection can't be silently removed).
const missingGuards = REQUIRED_GUARDS.filter((p) => !existsSync(p))
if (missingGuards.length > 0) {
  fail(`missing safety-invariant guard(s):\n  - ${missingGuards.join('\n  - ')}`)
}

// 2) Obtain a Vitest JSON report — reuse one if given, else produce one.
let reportPath = process.argv[2]
if (!reportPath || !existsSync(reportPath)) {
  reportPath = join(mkdtempSync(join(tmpdir(), 'vitest-')), 'report.json')
  // Shell string (quoted path) so `npx`/its `.cmd` shim resolves and a spaced temp path survives.
  const res = spawnSync(`npx vitest run --reporter=json --outputFile="${reportPath}"`, {
    stdio: ['ignore', 'inherit', 'inherit'],
    shell: true,
  })
  if (res.status !== 0 && !existsSync(reportPath)) {
    fail('vitest run did not complete (no report produced)')
  }
}

let report
try {
  report = JSON.parse(readFileSync(reportPath, 'utf8'))
} catch (err) {
  fail(`could not parse vitest report at ${reportPath}: ${err.message}`)
}

const passed = report.numPassedTests ?? 0
const failed = report.numFailedTests ?? 0
const total = report.numTotalTests ?? passed + failed

if (failed > 0) {
  const failedNames = (report.testResults ?? [])
    .flatMap((f) => f.assertionResults ?? [])
    .filter((a) => a.status === 'failed')
    .map((a) => `  - ${a.fullName ?? a.title}`)
  fail(`${failed} test(s) failed:\n${failedNames.join('\n')}`)
}

if (passed < MIN_TESTS) {
  fail(`unit test count ${passed} is below the ≥${MIN_TESTS} floor (coverage must not shrink)`)
}

console.log(
  `✓ test-count gate: ${passed} passed / ${total} total (floor ≥${MIN_TESTS}) · ${REQUIRED_GUARDS.length} invariant guards present`,
)
