import { describe, expect, it } from 'vitest'
import { apiClient } from '@/lib/apiClient'
import { listSourceFiles } from './sourceFiles'

/**
 * INVARIANT #1 — ALERT-ONLY (durable guard).
 *
 * "The UI must *never* offer an auto-block or auto-classify affordance. The only money action is a
 *  human-raised block-request and a lead approve (still not auto-block)." (HAWK-EYE_UI_UPLIFT_PROMPTS.md)
 *
 * The existing render test (`__contract__/render.contract.test.tsx`) proves the EDD panel shows a
 * *request*-block and no bare `block` button. This guard is the structural backstop that survives the
 * uplift: it inspects the API seam and statically scans the whole `src/` tree, so if Agent A or B ever
 * wires an auto-block / auto-classify control the frontend gate goes red immediately — not in review.
 */

/** Extract every route literal passed to `request('…')` / `request(`…`)` in a source file. */
function requestPaths(text: string): string[] {
  const out: string[] = []
  const re = /request(?:<[^>]*>)?\(\s*[`'"]([^`'"]+)[`'"]/g
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) out.push(m[1])
  return out
}

describe('alert-only · API seam', () => {
  const methods = Object.keys(apiClient)

  it('exposes the human block-*request* method and no auto-block/classify method', () => {
    expect(methods).toContain('blockRequest')
    // No method may *be* a direct block/classify action or an "auto*" affordance.
    const forbidden = methods.filter((m) =>
      /^(block|autoblock|auto_block|classify|autoclassify|auto_classify|autodisposition|autoclose)$/i.test(
        m,
      ),
    )
    expect(
      forbidden,
      `forbidden money/classify methods on apiClient: ${forbidden.join(', ')}`,
    ).toEqual([])
    expect(methods.filter((m) => /^auto/i.test(m))).toEqual([])
  })

  it('routes no money path except the human block-request (never a bare /block)', () => {
    const apiClientSrc = listSourceFiles({ includeMocks: false }).find(
      (f) => f.rel === 'lib/apiClient.ts',
    )
    expect(apiClientSrc, 'lib/apiClient.ts must exist').toBeTruthy()
    const paths = requestPaths(apiClientSrc!.text)
    const blockish = paths.filter((p) => /block/i.test(p))
    // Every block-related route must be the human request (…/block-request[/approve]).
    for (const p of blockish) {
      expect(p, `unexpected block route: ${p}`).toMatch(/block-request/)
    }
  })
})

describe('alert-only · static source scan', () => {
  // Mocks included: an auto-block affordance hidden in a handler would be just as bad.
  const files = listSourceFiles({ includeTests: false, includeMocks: true })

  it('contains no auto-block / auto-classify code identifier', () => {
    // Identifier form (no hyphen) — this is only ever code, never reassurance prose like
    // "never auto-blocks". Matches autoBlock / AUTO_BLOCK / auto_classify, not "auto-block".
    const idRe = /\bauto_?(block|classif(?:y|ication))\b/i
    const hits = files.filter((f) => idRe.test(f.text)).map((f) => f.rel)
    expect(hits, `auto-block/classify identifiers found in: ${hits.join(', ')}`).toEqual([])
  })

  it('contains no capitalized auto-block / auto-classify UI action label', () => {
    // Case-sensitive on the leading capital so lowercase reassurance prose ("never auto-blocks")
    // is allowed, but an action label ("Auto-block", "Automatically classify") is not.
    const labelRe = /Auto[- ]?(Block|Classif)|Automatically (block|classif)/
    const hits: string[] = []
    for (const f of files) {
      const line = f.text.split('\n').find((l) => labelRe.test(l))
      if (line) hits.push(`${f.rel}: ${line.trim().slice(0, 80)}`)
    }
    expect(hits, `auto-block/classify action labels found:\n${hits.join('\n')}`).toEqual([])
  })
})
