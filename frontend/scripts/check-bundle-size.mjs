#!/usr/bin/env node
/**
 * Bundle-size budget gate (Agent C · hawk-eye/ui-integrity).
 *
 * Catches regressions that make the investigator console heavy (invariant #8 / perf budget): a heavy
 * new dependency, a raw over-copied component library, or a motion import that defeats LazyMotion /
 * tree-shaking. Two gzip budgets:
 *   1. INITIAL payload  — the entry script + its eager modulepreloads + stylesheets from index.html.
 *      This is what loads on first paint; the heavy investigation libs (cytoscape, charts) are
 *      route-lazy per vite.config manualChunks and are NOT in here.
 *   2. TOTAL JS         — every emitted JS chunk. A big new dep shows up here even when route-lazy.
 *
 * Budgets are tripwires with generous headroom over the current baseline (initial ≈353 KB, total ≈764
 * KB gz as of 2026-07-01 — the "initial" figure is the entry script + every eager modulepreload +
 * stylesheet from index.html), sized to admit A's Motion + fonts while still catching a ballooning
 * bundle (a raw over-copied component library or a heavy new dep). Tighten once the uplift settles.
 * Run after `vite build`.
 */
import { gzipSync } from 'node:zlib'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

const DIST = 'dist'
const ASSETS = join(DIST, 'assets')
const INITIAL_BUDGET_KB = 500
const TOTAL_JS_BUDGET_KB = 1100

function fail(msg) {
  console.error(`\n✗ bundle-size gate FAILED: ${msg}\n`)
  process.exit(1)
}

if (!existsSync(DIST)) fail(`no build output at ./${DIST} — run \`vite build\` first`)

const gzKb = (buf) => gzipSync(buf).length / 1024
const readAsset = (href) => {
  // href like "/assets/index-abc.js" → dist/assets/index-abc.js
  const rel = href.replace(/^\//, '')
  const path = join(DIST, rel)
  return existsSync(path) ? readFileSync(path) : null
}

// 1) Initial payload = entry <script type=module> + <link rel=modulepreload> + <link rel=stylesheet>.
const html = existsSync(join(DIST, 'index.html'))
  ? readFileSync(join(DIST, 'index.html'), 'utf8')
  : ''
const initialHrefs = new Set()
for (const m of html.matchAll(/<script[^>]+type="module"[^>]+src="([^"]+)"/g))
  initialHrefs.add(m[1])
for (const m of html.matchAll(/<link[^>]+rel="modulepreload"[^>]+href="([^"]+)"/g))
  initialHrefs.add(m[1])
for (const m of html.matchAll(/<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"/g))
  initialHrefs.add(m[1])

let initialKb = 0
for (const href of initialHrefs) {
  const buf = readAsset(href)
  if (buf) initialKb += gzKb(buf)
}

// 2) Total JS across every chunk.
let totalJsKb = 0
let biggest = { name: '', kb: 0 }
for (const f of existsSync(ASSETS) ? readdirSync(ASSETS) : []) {
  if (!f.endsWith('.js')) continue
  const kb = gzKb(readFileSync(join(ASSETS, f)))
  totalJsKb += kb
  if (kb > biggest.kb) biggest = { name: f, kb }
}

const round = (n) => Math.round(n * 10) / 10
console.log('Bundle (gzip):')
console.log(
  `  initial payload : ${round(initialKb)} KB  (budget ${INITIAL_BUDGET_KB} KB, ${initialHrefs.size} assets)`,
)
console.log(`  total JS        : ${round(totalJsKb)} KB  (budget ${TOTAL_JS_BUDGET_KB} KB)`)
console.log(`  biggest chunk   : ${biggest.name} ${round(biggest.kb)} KB`)

const problems = []
if (initialKb === 0) problems.push('could not measure the initial payload from dist/index.html')
if (initialKb > INITIAL_BUDGET_KB)
  problems.push(`initial payload ${round(initialKb)} KB > ${INITIAL_BUDGET_KB} KB budget`)
if (totalJsKb > TOTAL_JS_BUDGET_KB)
  problems.push(`total JS ${round(totalJsKb)} KB > ${TOTAL_JS_BUDGET_KB} KB budget`)

if (problems.length > 0) fail(problems.join('; '))
console.log('✓ bundle-size gate: within budget')
