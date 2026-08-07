import { test, expect } from '@playwright/test'

test.describe('GUI smoke', () => {
  test('browse → click risultato → detail', async ({ page }) => {
    await page.goto('/app/#/')
    await expect(page.getByRole('heading', { name: 'Browse', exact: true })).toBeVisible()

    const firstCard = page.locator('.lesson-card').first()
    await expect(firstCard).toBeVisible({ timeout: 15_000 })
    const lessonId = (await firstCard.locator('strong').textContent())?.trim()
    expect(lessonId).toBeTruthy()

    await firstCard.click()
    await expect(page.getByRole('heading', { level: 2 })).toContainText(lessonId!)
    await expect(page.getByRole('heading', { name: 'Why similar?', exact: true })).toBeVisible()
  })

  test('editor: suggest panel risponde', async ({ page }) => {
    await page.goto('/app/#/editor')
    await page.getByPlaceholder('Write the lesson learned…').fill(
      'python pytest workflow con abbastanza testo per attivare il debounce del suggest live',
    )
    await page.waitForTimeout(800)

    const panel = page.locator('.similar-panel')
    await expect(panel).toBeVisible()
    await expect(panel.getByRole('heading', { name: 'Why similar?', exact: true })).toBeVisible()
    await expect(panel.locator('.error')).toHaveCount(0)
    await expect(panel.getByText('Loading…')).toHaveCount(0, { timeout: 15_000 })
  })

  test('stats e timeline caricano senza errori', async ({ page }) => {
    await page.goto('/app/#/stats')
    const statsPanel = page.getByRole('region', {
      name: 'Statistics',
      exact: true,
    })
    await expect(statsPanel).toBeVisible()
    await expect(statsPanel.getByRole('alert')).toHaveCount(0, {
      timeout: 15_000,
    })
    await expect(statsPanel.locator('.kpi').first()).toBeVisible()

    await page.getByRole('link', {
      name: 'Timeline',
      exact: true,
    }).click()
    await expect(
      page.getByRole('heading', {
        name: 'Timeline',
        exact: true,
      }),
    ).toBeVisible()
    await expect(page.locator('.timeline .error')).toHaveCount(0, { timeout: 15_000 })
    await expect(page.locator('.bucket').first()).toBeVisible()
  })

  test('Sistema e Vault caricano sulla fixture isolata', async ({ page }) => {
    await page.goto('/app/#/ops')
    await expect(page.getByRole('heading', { name: 'Stato e manutenzione' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Aggiorna dal vault' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Aggiorna il modello di ricerca' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Aggiorna tutto' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Esegui controllo' })).toBeVisible()
    await expect(page.locator('.ops .error')).toHaveCount(0, { timeout: 15_000 })

    await page.getByRole('link', { name: 'Vault' }).click()

    const vaultPanel = page.getByRole('region', {
      name: 'Vault',
      exact: true,
    })

    await expect(vaultPanel).toBeVisible()
    await expect(vaultPanel.getByRole('alert')).toHaveCount(0, {
      timeout: 15_000,
    })
  })
})
