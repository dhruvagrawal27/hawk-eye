/**
 * Source-scanning helper for the safety-invariant guards (Agent C · `hawk-eye/ui-integrity`).
 *
 * The guards in this directory are the *point of the product* (HAWK-EYE_UI_UPLIFT_PROMPTS.md,
 * invariants 1–8): they must keep protecting the app after the Daylight-Forensics uplift, regardless
 * of what Agent A (design system) or Agent B (feature screens) build. Several guards work by statically
 * scanning the real `src/` tree, so a violation (an auto-block affordance, a hardcoded secret, a rogue
 * `import.meta.env` read) fails the build the moment it lands — not when someone notices in review.
 *
 * This helper is deliberately dependency-free (node builtins only) and typed strictly so it passes the
 * production ESLint/TS config (it is not a `*.test` file). It skips this `__invariants__/` directory so
 * the guards never scan their own banned-pattern literals and false-positive on themselves.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
/** Absolute path to `frontend/src`. */
export const SRC_ROOT = join(HERE, '..')
/** Absolute path to the repo root (…/frontend/src → …/). */
export const REPO_ROOT = join(SRC_ROOT, '..', '..')

export interface SourceFile {
  /** Absolute path. */
  path: string
  /** POSIX-style path relative to `frontend/src` (e.g. `lib/apiClient.ts`). */
  rel: string
  /** File contents (utf8). */
  text: string
}

export interface ScanOptions {
  /** Include `*.test.*` / `*.spec.*` files (default: false). */
  includeTests?: boolean
  /** Include `src/lib/mocks/**` (default: false). */
  includeMocks?: boolean
}

const SKIP_DIRS = new Set(['node_modules', 'dist', 'coverage', '__invariants__'])
const TEST_RE = /\.(test|spec)\.(ts|tsx)$/
const SRC_RE = /\.(ts|tsx)$/

/** Recursively list first-party TypeScript source under `frontend/src` (see {@link ScanOptions}). */
export function listSourceFiles(options: ScanOptions = {}): SourceFile[] {
  const { includeTests = false, includeMocks = false } = options
  const out: SourceFile[] = []

  const walk = (dir: string): void => {
    for (const name of readdirSync(dir)) {
      const full = join(dir, name)
      if (statSync(full).isDirectory()) {
        if (SKIP_DIRS.has(name)) continue
        if (!includeMocks && name === 'mocks') continue
        walk(full)
        continue
      }
      if (!SRC_RE.test(name) || name.endsWith('.d.ts')) continue
      if (!includeTests && TEST_RE.test(name)) continue
      out.push({
        path: full,
        rel: relative(SRC_ROOT, full).split('\\').join('/'),
        text: readFileSync(full, 'utf8'),
      })
    }
  }

  walk(SRC_ROOT)
  return out
}
