import { expect, test } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const captureEnabled = process.env.CAPTURE_GUI_DOCS === '1'
const outputDir = fileURLToPath(
  new URL('../../docs/images/gui/', import.meta.url),
)

async function prepareDocumentationScreenshot(
  page: import('@playwright/test').Page,
) {
  await page.evaluate(() => {
    const activeElement = document.activeElement

    if (activeElement instanceof HTMLElement) {
      activeElement.blur()
    }

    for (const logElement of document.querySelectorAll('.ops pre')) {
      logElement.textContent = (logElement.textContent ?? '').replace(
        /^\[[^\]]+\]/gm,
        '[00:00:00]',
      )
    }


    // The isolated E2E copies live under different temporary paths.
    // Keep the documented Vault view independent from the runner path.
    const vaultHeading = Array.from(
      document.querySelectorAll('h2'),
    ).find((heading) => heading.textContent?.trim() === 'Vault')
    const vaultCard = vaultHeading?.closest('section.card')
    const vaultPath = vaultCard?.querySelector(':scope > p.meta')

    if (vaultPath instanceof HTMLElement) {
      vaultPath.textContent = '/vault'
    }
  })

  // Keep the pointer over a neutral viewport corner so route changes
  // cannot leave an unrelated control in its hover state.
  await page.mouse.move(1439, 999)

  // Let focus, hover and layout changes settle before capturing.
  await page.evaluate(
    () =>
      new Promise<void>((resolve) => {
        requestAnimationFrame(() => {
          requestAnimationFrame(() => resolve())
        })
      }),
  )
}

test.describe('GUI documentation screenshots', () => {
  test.skip(
    !captureEnabled,
    'Set CAPTURE_GUI_DOCS=1 to update documentation screenshots.',
  )

  test.beforeAll(async () => {
    await mkdir(outputDir, { recursive: true })
  })

  test('capture released views from the isolated fixture', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 })

    await page.goto('/app/#/')
    await expect(page.getByRole('heading', { name: 'Esplora' })).toBeVisible()
    await expect(page.locator('.lesson-card').first()).toBeVisible()
    await prepareDocumentationScreenshot(page)
    await page.screenshot({
      animations: 'disabled',
      caret: 'hide',
      path: `${outputDir}/browse.png`,
      fullPage: true,
    })

    await page.locator('.lesson-card').first().click()
    await expect(
      page.getByRole('heading', { name: 'Perché simile?' }),
    ).toBeVisible()
    await prepareDocumentationScreenshot(page)
    await page.screenshot({
      animations: 'disabled',
      caret: 'hide',
      path: `${outputDir}/detail.png`,
      fullPage: true,
    })

    await page.goto('/app/#/editor')
    await expect(
      page.getByRole('heading', { name: 'Nuova LeLe' }),
    ).toBeVisible()
    await page.getByPlaceholder('Scrivi la lesson learned…').fill(
      'python pytest fixtures and deterministic tests',
    )
    await page.waitForTimeout(800)

    const editorSimilarPanel = page.locator('.similar-panel')
    await expect(editorSimilarPanel).toBeVisible()
    await expect(
      editorSimilarPanel.getByRole('heading', { name: 'Perché simile?' }),
    ).toBeVisible()
    await expect(editorSimilarPanel.locator('.error')).toHaveCount(0)
    await expect(
      editorSimilarPanel.getByText('Caricamento…'),
    ).toHaveCount(0, { timeout: 15_000 })
    await prepareDocumentationScreenshot(page)
    await page.screenshot({
      animations: 'disabled',
      caret: 'hide',
      path: `${outputDir}/editor.png`,
      fullPage: true,
    })

    await page.goto('/app/#/stats')
    await expect(
      page.getByRole('heading', { name: 'Statistiche' }),
    ).toBeVisible()
    await expect(page.locator('.kpi').first()).toBeVisible()
    await prepareDocumentationScreenshot(page)
    await page.screenshot({
      animations: 'disabled',
      caret: 'hide',
      path: `${outputDir}/stats.png`,
      fullPage: true,
    })

    await page.goto('/app/#/timeline')
    await expect(
      page.getByRole('heading', { name: 'Cronologia' }),
    ).toBeVisible()
    await expect(page.locator('.bucket').first()).toBeVisible()
    await prepareDocumentationScreenshot(page)
    await page.screenshot({
      animations: 'disabled',
      caret: 'hide',
      path: `${outputDir}/timeline.png`,
      fullPage: true,
    })

    await page.goto('/app/#/vault')
    await expect(
      page.getByRole('heading', { name: 'Vault' }),
    ).toBeVisible()
    await expect(
      page.getByRole('button', { name: 'Refresh' }),
    ).toBeEnabled()
    await expect(
      page.getByText('Caricamento…'),
    ).toHaveCount(0)
    await expect(
      page.locator('details.dir').first(),
    ).toBeVisible()
    await prepareDocumentationScreenshot(page)
    await page.screenshot({
      animations: 'disabled',
      caret: 'hide',
      path: `${outputDir}/vault.png`,
      fullPage: true,
    })

    await page.goto('/app/#/duplicates')
    await page.getByRole('button', { name: 'Avvia controllo' }).click()
    await expect(page.getByText('Riepilogo del controllo')).toBeVisible()
    await prepareDocumentationScreenshot(page)
    await page.screenshot({
      animations: 'disabled',
      caret: 'hide',
      path: `${outputDir}/duplicates.png`,
      fullPage: true,
    })

    await page.goto('/app/#/ops')
    await expect(
      page.getByRole('heading', { name: 'Stato e manutenzione' }),
    ).toBeVisible()
    await expect(
      page.locator('.health-grid strong').first(),
    ).toHaveText('ok')
    await expect(
      page.getByRole('button', { name: 'Aggiorna stato' }),
    ).toBeEnabled()
    await page.getByRole('button', { name: 'Esegui controllo' }).click()
    await expect(page.getByText('Vault healthy')).toBeVisible()
    await expect(
      page.getByRole('button', { name: 'Esegui controllo' }),
    ).toBeEnabled()
    await prepareDocumentationScreenshot(page)
    await page.screenshot({
      animations: 'disabled',
      caret: 'hide',
      path: `${outputDir}/ops.png`,
      fullPage: true,
    })

    await page.goto('/app/#/tritalele')
    await expect(
      page.getByRole('heading', { name: 'Raccogli nuove LeLe' }),
    ).toBeVisible()
    await page
      .getByLabel('Nome della fonte')
      .fill('documentation-example.txt')
    await page
      .getByLabel('Testo sorgente')
      .fill(
        'Deterministic documentation example for the TritaLeLe preview.',
      )
    await page
      .getByRole('button', { name: 'Crea anteprima' })
      .click()
    await expect(
      page.getByTestId('ingestion-preview'),
    ).toBeVisible()
    await prepareDocumentationScreenshot(page)
    await page.screenshot({
      animations: 'disabled',
      caret: 'hide',
      path: `${outputDir}/tritalele.png`,
      fullPage: true,
    })
  })
})
