import { test, expect } from '@playwright/test'

test.describe('GUI smoke', () => {
  test('browse → click risultato → detail', async ({ page }) => {
    await page.goto('/app/#/')
    await expect(page.getByRole('heading', { name: 'Browse' })).toBeVisible()

    const firstCard = page.locator('.lesson-card').first()
    await expect(firstCard).toBeVisible({ timeout: 15_000 })
    const lessonId = (await firstCard.locator('strong').textContent())?.trim()
    expect(lessonId).toBeTruthy()

    await firstCard.click()
    await expect(page.getByRole('heading', { level: 2 })).toContainText(lessonId!)
    await expect(page.getByRole('heading', { name: 'Perché simile?' })).toBeVisible()
  })

  test('editor: suggest panel risponde', async ({ page }) => {
    await page.goto('/app/#/editor')
    await page.getByPlaceholder('Scrivi la lesson learned…').fill(
      'python pytest workflow con abbastanza testo per attivare il debounce del suggest live',
    )
    await page.waitForTimeout(800)

    const panel = page.locator('.similar-panel')
    await expect(panel).toBeVisible()
    await expect(panel.getByRole('heading', { name: 'Perché simile?' })).toBeVisible()
    await expect(panel.locator('.error')).toHaveCount(0)
    await expect(panel.getByText('Caricamento…')).toHaveCount(0, { timeout: 15_000 })
  })

  test('stats e timeline caricano senza errori', async ({ page }) => {
    await page.goto('/app/#/stats')
    await expect(page.getByRole('heading', { name: 'Statistiche' })).toBeVisible()
    await expect(page.locator('.stats .error')).toHaveCount(0, { timeout: 15_000 })
    await expect(page.locator('.kpi').first()).toBeVisible()

    await page.getByRole('link', { name: 'Timeline' }).click()
    await expect(page.getByRole('heading', { name: 'Timeline' })).toBeVisible()
    await expect(page.locator('.timeline .error')).toHaveCount(0, { timeout: 15_000 })
    await expect(page.locator('.bucket').first()).toBeVisible()
  })
})
