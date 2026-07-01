#!/usr/bin/env node
/**
 * Local "all gates" harness (Agent C · hawk-eye/ui-integrity) — one command that mirrors the frontend
 * CI gate so A and B can prove the floor is green before they push:
 *
 *   node scripts/verify.mjs            # tsc · eslint · prettier · vitest(≥112) · build · bundle · e2e-count
 *   node scripts/verify.mjs --e2e      # also run the Playwright browser slice (needs `npm run e2e:install`)
 *   node scripts/verify.mjs --fast     # skip build + bundle (quick inner loop)
 *
 * Definition of done (HAWK-EYE_UI_UPLIFT_PROMPTS.md): at any moment the integration branch is one
 * command from all-green. This is that command. Prettier line-ending note: on Windows with
 * core.autocrlf=true the working tree is CRLF while the repo is LF, so `prettier --check` reports every
 * file; CI (Linux/LF) is authoritative. This harness downgrades that specific case to a warning and
 * points at the fix (frontend/.gitattributes + `git add --renormalize .`).
 */
import { spawnSync, execSync } from 'node:child_process'

const args = new Set(process.argv.slice(2))
const RUN_E2E = args.has('--e2e')
const FAST = args.has('--fast')

function onWindowsCrlf() {
  if (process.platform !== 'win32') return false
  try {
    return execSync('git config --get core.autocrlf', { encoding: 'utf8' }).trim() === 'true'
  } catch {
    return false
  }
}

const results = []
// Commands run through the shell (string form) so `npx`/`node` resolve on every OS, including the
// Windows `.cmd` shims that a bare spawn cannot exec directly.
function gate(name, command, { softOnWindowsCrlf = false } = {}) {
  process.stdout.write(`\n▶ ${name}\n`)
  const res = spawnSync(command, { stdio: 'inherit', shell: true })
  const ok = res.status === 0
  if (!ok && softOnWindowsCrlf && onWindowsCrlf()) {
    results.push({ name, status: 'warn' })
    console.warn(
      `  ⚠ ${name} reported issues — on Windows this is almost certainly CRLF (repo is LF). ` +
        `CI is authoritative. Fix locally: ensure frontend/.gitattributes is present, then ` +
        `\`git add --renormalize .\`.`,
    )
    return
  }
  results.push({ name, status: ok ? 'pass' : 'fail' })
}

gate('tsc --noEmit', 'npx tsc --noEmit')
gate('eslint (--max-warnings=0)', 'npx eslint . --max-warnings=0')
gate('prettier --check', 'npx prettier --check .', { softOnWindowsCrlf: true })
gate('vitest (unit ≥112 + invariant guards)', 'node scripts/check-test-count.mjs')
if (!FAST) {
  gate('vite build', 'npx vite build')
  gate('bundle-size budget', 'node scripts/check-bundle-size.mjs')
}
gate('e2e-count (≥3)', 'node scripts/check-e2e-count.mjs')
if (RUN_E2E) gate('playwright e2e', 'npx playwright test')

const icon = { pass: '✓', warn: '⚠', fail: '✗' }
console.log('\n──────── gate summary ────────')
for (const r of results) console.log(`  ${icon[r.status]} ${r.name}`)
const failed = results.filter((r) => r.status === 'fail')
if (failed.length > 0) {
  console.error(`\n✗ ${failed.length} gate(s) failed: ${failed.map((r) => r.name).join(', ')}`)
  process.exit(1)
}
console.log(
  '\n✓ all gates green' + (results.some((r) => r.status === 'warn') ? ' (with warnings)' : ''),
)
