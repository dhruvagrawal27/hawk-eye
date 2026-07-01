import { test, expect, type Page } from '@playwright/test'

/**
 * Accessibility / reduced-motion audit (Agent C · hawk-eye/ui-integrity) — invariant #7.
 *
 * "A reduced-motion user gets a fully static, high-contrast, fully-usable UI… full keyboard nav."
 * (HAWK-EYE_UI_UPLIFT_PROMPTS.md). This spec drives the MSW-mocked app with the OS reduced-motion
 * preference forced ON and asserts the worked-burst surface is fully usable and keyboard-reachable. It
 * mirrors the proven investigator login→triage flow so it stays robust as A re-skins and B rebuilds
 * the screens, and it depends on nothing that is not already on `main`.
 *
 * DELIBERATELY NOT ASSERTED HERE (yet): the strict "no perpetual animation runs under reduce" check.
 * `main` today has no global reduced-motion floor and renders un-gated infinite animations (e.g.
 * SlaTimer's `animate-pulse-urgent`), so that assertion would red this gate on `main`. Agent A's uplift
 * adds the global `@media (prefers-reduced-motion: reduce)` floor that fixes it; the ready-to-enable
 * assertion + this invariant risk are tracked in docs/ui/INTEGRITY.md and flip on once A's floor lands.
 * axe-core contrast/ARIA sweeps are the following increment (need the `@axe-core/playwright` dev-dep,
 * an A-owned package.json change — also tracked in INTEGRITY.md).
 */
test.use({ reducedMotion: 'reduce' })

async function loginAs(page: Page, persona: RegExp) {
  await page.goto('/login')
  await page.getByRole('button', { name: persona }).first().click()
}

test.describe('reduced-motion a11y audit (worked burst)', () => {
  test('the console is fully usable with reduced motion on', async ({ page }) => {
    await loginAs(page, /\bRM\b/)

    // Relationship Manager lands on triage; the worked-burst alert is present as real content
    // (not trapped behind a motion-only reveal).
    await expect(page).toHaveURL(/\/triage/)
    await expect(page.getByText('EMP-7f3a').first()).toBeVisible()
    await expect(page.getByText('87').first()).toBeVisible()

    // The browser reports the reduced-motion preference to the app.
    const prefersReduced = await page.evaluate(
      () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    )
    expect(prefersReduced).toBe(true)
  })

  test('the primary surface is keyboard reachable', async ({ page }) => {
    await loginAs(page, /\bRM\b/)
    await expect(page).toHaveURL(/\/triage/)
    // Tab moves focus off <body> onto a real interactive control (keyboard nav works).
    await page.keyboard.press('Tab')
    const focusedTag = await page.evaluate(() => document.activeElement?.tagName ?? 'BODY')
    expect(focusedTag).not.toBe('BODY')
  })
})
