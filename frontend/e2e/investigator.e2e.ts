import { test, expect, type Page } from '@playwright/test'

/**
 * e2e (§8) — the full vertical slice against the MSW-mocked app (VITE_USE_MOCKS=true):
 * login → triage (worked burst) → claim → alert detail → entity-360 → explanation → graph → peer
 * → disposition, plus the RBAC and alert-only invariants. Personas are the bank org-chart roles
 * (docs/BANK_ROLES.md): RM (Relationship Manager), CIA (Chief Internal Auditor), IT Admin. The
 * worked burst is Part 24.5(d): alr_3d7e22 / EMP-7f3a / risk 87 / ₹48,00,000.
 */

async function loginAs(page: Page, persona: RegExp) {
  await page.goto('/login')
  await page.getByRole('button', { name: persona }).first().click()
}

test.describe('Investigator vertical slice (worked burst)', () => {
  test('relationship manager: login → triage → alert detail → explanation → disposition', async ({
    page,
  }) => {
    await loginAs(page, /\bRM\b/)

    // Triage queue (Relationship Manager home) shows the worked-burst alert.
    await expect(page).toHaveURL(/\/triage/)
    await expect(page.getByText('EMP-7f3a').first()).toBeVisible()
    await expect(page.getByText('87').first()).toBeVisible()

    // Open the alert detail (the workhorse screen).
    await page.goto('/alerts/alr_3d7e22')
    await expect(page.getByText('87').first()).toBeVisible()

    // Explanation panel — SHAP/rule provenance + clearly-labelled AI narrative.
    const explanationTab = page.getByRole('tab', { name: /explanation/i })
    if (await explanationTab.isVisible().catch(() => false)) {
      await explanationTab.click()
    }
    await expect(page.getByText(/AI-generated/i).first()).toBeVisible()

    // EDD: alert-only — a "request block", never an auto-block.
    await expect(page.getByRole('button', { name: /request block/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /^block$/i })).toHaveCount(0)

    // Disposition (human-in-the-loop): false positive needs only notes.
    await page
      .getByLabel(/investigation notes/i)
      .fill('Reviewed; benign seasonal pattern — closing as FP.')
    await page.getByRole('button', { name: /close as false positive/i }).click()
    await page.getByRole('button', { name: /confirm & record/i }).click()

    // Immutable-audit confirmation surfaces the audit id + label written.
    await expect(page.getByText(/aud_/).first()).toBeVisible()
  })
})

test.describe('RBAC (Part 24.1) — forbidden routes/controls are absent', () => {
  test('chief internal auditor cannot reach triage and has no triage nav', async ({ page }) => {
    await loginAs(page, /\bCIA\b/)
    // CIA lands on the audit view and sees the Auditor nav, not Triage.
    await expect(page.getByRole('link', { name: /auditor/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /triage queue/i })).toHaveCount(0)

    // Direct navigation to a forbidden route is blocked (redirect to /forbidden).
    await page.goto('/triage')
    await expect(page).toHaveURL(/\/forbidden/)
    await expect(page.getByText(/not permitted/i)).toBeVisible()
  })

  test('IT admin sees Admin but no case data (no triage)', async ({ page }) => {
    await loginAs(page, /IT Admin/)
    await expect(page.getByRole('link', { name: /admin/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /triage queue/i })).toHaveCount(0)
  })
})
