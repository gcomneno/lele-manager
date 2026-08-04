import { expect, test } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const captureEnabled = process.env.CAPTURE_GUI_DOCS === '1'
const outputDir = fileURLToPath(
  new URL('../../docs/images/gui/', import.meta.url),
)

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
    await expect(page.getByRole('heading', { name: 'Browse' })).toBeVisible()
    await expect(page.locator('.lesson-card').first()).toBeVisible()
    await page.screenshot({
      path: `${outputDir}/browse.png`,
      fullPage: true,
    })

    await page.locator('.lesson-card').first().click()
    await expect(
      page.getByRole('heading', { name: 'Perché simile?' }),
    ).toBeVisible()
    await page.screenshot({
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
    await page.screenshot({
      path: `${outputDir}/editor.png`,
      fullPage: true,
    })

    await page.goto('/app/#/stats')
    await expect(
      page.getByRole('heading', { name: 'Statistiche' }),
    ).toBeVisible()
    await expect(page.locator('.kpi').first()).toBeVisible()
    await page.screenshot({
      path: `${outputDir}/stats.png`,
      fullPage: true,
    })

    await page.goto('/app/#/timeline')
    await expect(
      page.getByRole('heading', { name: 'Timeline' }),
    ).toBeVisible()
    await expect(page.locator('.bucket').first()).toBeVisible()
    await page.screenshot({
      path: `${outputDir}/timeline.png`,
      fullPage: true,
    })

    await page.goto('/app/#/vault')
    await expect(
      page.getByRole('heading', { name: 'Vault' }),
    ).toBeVisible()
    await page.screenshot({
      path: `${outputDir}/vault.png`,
      fullPage: true,
    })

    await page.goto('/app/#/duplicates')
    await page.getByRole('button', { name: 'Run review' }).click()
    await expect(page.getByText('Review summary')).toBeVisible()
    await page.screenshot({
      path: `${outputDir}/duplicates.png`,
      fullPage: true,
    })

    await page.goto('/app/#/ops')
    await expect(
      page.getByRole('heading', { name: 'Ops / Admin' }),
    ).toBeVisible()
    await page.getByRole('button', { name: 'Run Doctor' }).click()
    await expect(page.getByText('Vault healthy')).toBeVisible()
    await page.screenshot({
      path: `${outputDir}/ops.png`,
      fullPage: true,
    })

    await page.goto('/app/#/tritalele')
    await expect(
      page.getByRole('heading', { name: 'TritaLeLe' }),
    ).toBeVisible()
    await page
      .getByLabel('Nome logico')
      .fill('documentation-example.txt')
    await page
      .getByLabel('Testo sorgente')
      .fill(
        'Deterministic documentation example for the TritaLeLe preview.',
      )
    await page
      .getByRole('button', { name: 'Genera anteprima' })
      .click()
    await expect(
      page.getByTestId('ingestion-preview'),
    ).toBeVisible()
    await page.screenshot({
      path: `${outputDir}/tritalele.png`,
      fullPage: true,
    })
  })
})
