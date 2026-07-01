import { test, expect, type Page } from '@playwright/test'

/**
 * Regression (production freeze): the first-run onboarding tour must NEVER block the app. It was a
 * modal Radix Dialog whose full-screen backdrop captured every click — on login the RM lands on
 * /triage, the tour popped, and the whole screen read as frozen ("can't click any tab or anything").
 * The fix makes the tour non-blocking (modal={false}, no overlay, docked card). These tests prove the
 * app stays interactive while the tour is open, and that navigation/back still work.
 */

function trap(page: Page) {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))
  page.on('console', (m) => {
    if (m.type() === 'error') errors.push(`console.error: ${m.text()}`)
  })
  return errors
}

test('first-run tour is shown but does NOT block triage interaction', async ({ page }) => {
  const errors = trap(page)
  await page.goto('/login')
  await page
    .getByRole('button', { name: /\bRM\b/ })
    .first()
    .click()
  await expect(page).toHaveURL(/\/triage/)

  // The welcome tour is visible…
  await expect(page.getByText(/you're in/i)).toBeVisible()

  // …but the nav TABS behind it are fully clickable WITHOUT dismissing the tour first — this is
  // exactly the freeze the modal backdrop caused ("can't click any tab"). Click a sidebar tab.
  await page.getByRole('link', { name: /cases/i }).first().click({ timeout: 4000 })
  await expect(page).toHaveURL(/\/cases/)

  // The tour is still present (non-blocking, not auto-dismissed) and the app kept working.
  await expect(page.getByText(/you're in/i)).toBeVisible()

  expect(errors, errors.join('\n')).toEqual([])
})

test('tour dismisses and stays dismissed on reload', async ({ page }) => {
  await page.goto('/login')
  await page
    .getByRole('button', { name: /\bRM\b/ })
    .first()
    .click()
  await expect(page.getByText(/you're in/i)).toBeVisible()

  // Dismiss via Escape (a valid, geometry-independent close for a non-modal Radix dialog).
  await page.keyboard.press('Escape')
  await expect(page.getByText(/you're in/i)).toHaveCount(0)

  await page.reload()
  await expect(page).toHaveURL(/\/triage/)
  // Persisted: the tour must not reappear after reload.
  await expect(page.getByText(/you're in/i)).toHaveCount(0)
})
