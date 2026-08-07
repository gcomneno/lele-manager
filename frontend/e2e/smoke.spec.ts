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
    await expect(page.getByRole('heading', { name: 'Why is it similar?', exact: true })).toBeVisible()
  })

  test('editor: similarity check is explicit and invalidated by edits', async ({ page }) => {
    let suggestRequests = 0

    page.on('request', (request) => {
      if (
        request.method() === 'POST' &&
        new URL(request.url()).pathname === '/editor/suggest'
      ) {
        suggestRequests += 1
      }
    })

    await page.goto('/app/#/editor')

    const editorPanel = page.getByRole('region', {
      name: 'New LeLe',
      exact: true,
    })

    await expect(editorPanel).toBeVisible()

    // L'ID della nuova LeLe è governato dal sistema.
    await expect(
      editorPanel.getByLabel('ID'),
    ).toHaveCount(0)

    const checkButton = editorPanel.getByRole('button', {
      name: 'Check similarity',
      exact: true,
    })

    await expect(checkButton).toBeDisabled()

    // Prima della richiesta esplicita il widget non esiste.
    await expect(
      page.locator('.similar-panel'),
    ).toHaveCount(0)

    await page.waitForTimeout(700)
    expect(suggestRequests).toBe(0)

    const body = page.getByPlaceholder(
      'Write the lesson learned…',
    )

    await body.fill(
      'python pytest workflow con abbastanza testo per verificare le similitudini',
    )

    await expect(checkButton).toBeEnabled()

    // Scrivere non deve più avviare richieste.
    await page.waitForTimeout(700)
    expect(suggestRequests).toBe(0)

    await expect(
      page.locator('.similar-panel'),
    ).toHaveCount(0)

    // Solo il click esplicito avvia il motore.
    await checkButton.click()

    await expect
      .poll(
        () => suggestRequests,
        { timeout: 15_000 },
      )
      .toBe(1)

    const similarPanel = page.locator('.similar-panel')

    await expect(similarPanel).toBeVisible()

    await expect(
      similarPanel.getByRole('heading', {
        name: 'Why is it similar?',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      similarPanel.getByText('Loading…'),
    ).toHaveCount(0, {
      timeout: 15_000,
    })

    await expect(
      similarPanel.locator('.error'),
    ).toHaveCount(0)

    // Il widget rimane sotto l'editor.
    const editorBox = await editorPanel.boundingBox()
    const similarBox = await similarPanel.boundingBox()

    expect(editorBox).not.toBeNull()
    expect(similarBox).not.toBeNull()

    expect(similarBox!.y).toBeGreaterThanOrEqual(
      editorBox!.y + editorBox!.height - 1,
    )

    // Una modifica invalida il confronto e lo nasconde.
    await body.fill(
      'python pytest workflow modificato dopo la prima verifica delle similitudini',
    )

    await expect(
      page.locator('.similar-panel'),
    ).toHaveCount(0)

    await page.waitForTimeout(700)
    expect(suggestRequests).toBe(1)

    // Una nuova verifica è ancora esplicita.
    await checkButton.click()

    await expect
      .poll(
        () => suggestRequests,
        { timeout: 15_000 },
      )
      .toBe(2)
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
    await expect(page.getByRole('heading', { name: 'Status and maintenance' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Refresh from vault' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Update search model' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Refresh all' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Run check' })).toBeVisible()
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
