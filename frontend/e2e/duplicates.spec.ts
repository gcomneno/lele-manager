import { test, expect } from '@playwright/test'
import { readFile, rm, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const repositoryRoot = fileURLToPath(new URL('../..', import.meta.url))
const modelPath = join(repositoryRoot, '.e2e-fixture', 'cache', 'topic_model.joblib')

const repeatedIdReport = {
  lessons_analyzed: 2,
  total_pairs: 1,
  exact_pairs: 1,
  near_pairs: 0,
  min_score: 0.85,
  exact_only: true,
  pairs: [
    {
      left_id: 'same-id',
      right_id: 'same-id',
      left_position: 4,
      right_position: 9,
      left_path: 'first.md',
      right_path: 'second.md',
      kind: 'exact',
      score: 1,
      reasons: ['duplicate_id'],
      shared_tags: [],
      left_lesson: { id: 'same-id', text: 'First record with the repeated ID.', title: 'First' },
      right_lesson: { id: 'same-id', text: 'Second record with the repeated ID.', title: 'Second' },
    },
  ],
}

test.describe('duplicate review', () => {
  test('reviews an exact duplicate with both lessons visible', async ({ page }) => {
    await page.goto('/app/#/duplicates')
    await expect(page.getByRole('heading', { name: 'Revisione duplicati' })).toBeVisible()
    await page.getByRole('button', { name: 'Avvia controllo' }).click()

    const exactPair = page.locator('.duplicate-pair').filter({ hasText: 'duplicato esatto' }).first()
    await expect(exactPair).toBeVisible({ timeout: 15_000 })
    await expect(exactPair.getByText('exact_text', { exact: false })).toBeVisible()
    await expect(exactPair.getByText('git branching merge rebase strategies')).toHaveCount(2)
    await expect(page.getByText('Coppie totali prima del limite')).toBeVisible()
    await expect(page.getByText('Coppie esatte prima del limite')).toBeVisible()
    await expect(page.getByText('Somiglianze prima del limite')).toBeVisible()
    await expect(page.getByText('Numero massimo impostato')).toBeVisible()
    await expect(page.locator('.summary').getByText('100', { exact: true })).toBeVisible()
  })

  test('reviews near duplicates from the real fixture API', async ({ page }) => {
    await page.goto('/app/#/duplicates')
    await page.getByLabel('Soglia minima').fill('0')
    await page.getByRole('button', { name: 'Avvia controllo' }).click()

    const nearPair = page.locator('.duplicate-pair').filter({ hasText: 'possibile somiglianza' }).first()
    await expect(nearPair).toBeVisible({ timeout: 15_000 })
    await expect(nearPair.getByText(/Punteggio 0\./)).toBeVisible()
  })

  test('keeps records with a repeated ID independently inspectable by position', async ({ page }) => {
    await page.route('**/duplicates?*', async (route) => {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(repeatedIdReport) })
    })
    await page.goto('/app/#/duplicates')
    await page.getByRole('button', { name: 'Avvia controllo' }).click()

    const pair = page.locator('.duplicate-pair')
    await expect(pair.getByText('First record with the repeated ID.')).toBeVisible()
    await expect(pair.getByText('Second record with the repeated ID.')).toBeVisible()
    await expect(pair.getByText('4', { exact: true })).toBeVisible()
    await expect(pair.getByText('9', { exact: true })).toBeVisible()
    await expect(pair.getByText('same-id', { exact: true })).toHaveCount(2)
  })

  test('runs exact-only review while the model is unavailable', async ({ page }) => {
    const model = await readFile(modelPath)
    await rm(modelPath)
    try {
      await page.goto('/app/#/duplicates')
      await page.getByLabel('Solo duplicati esatti').check()
      await page.getByRole('button', { name: 'Avvia controllo' }).click()

      await expect(page.getByText('Riepilogo del controllo')).toBeVisible({ timeout: 15_000 })
      await expect(page.locator('.summary').getByText('Sì', { exact: true })).toBeVisible()
      await expect(page.locator('.error-state')).toHaveCount(0)
    } finally {
      await writeFile(modelPath, model)
    }
  })

  test('shows an empty review result', async ({ page }) => {
    await page.route('**/duplicates?*', async (route) => {
      await route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({
          lessons_analyzed: 3,
          total_pairs: 0,
          exact_pairs: 0,
          near_pairs: 0,
          min_score: 0.85,
          exact_only: false,
          pairs: [],
        }),
      })
    })
    await page.goto('/app/#/duplicates')
    await page.getByRole('button', { name: 'Avvia controllo' }).click()

    await expect(page.getByRole('heading', { name: 'Nessun duplicato trovato' })).toBeVisible()
    await expect(page.getByText('Coppie mostrate')).toBeVisible()
  })

  test('rejects an invalid minimum score without requesting duplicates or keeping a stale report', async ({ page }) => {
    let duplicateRequests = 0
    await page.route('**/duplicates?*', async (route) => {
      duplicateRequests += 1
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(repeatedIdReport) })
    })
    await page.goto('/app/#/duplicates')
    await page.getByRole('button', { name: 'Avvia controllo' }).click()
    await expect(page.getByText('Riepilogo del controllo')).toBeVisible()

    await page.getByLabel('Soglia minima').fill('1.1')
    await page.getByRole('button', { name: 'Aggiorna controllo' }).click()

    await expect(page.getByText('La soglia minima deve essere un numero compreso tra 0 e 1.')).toBeVisible()
    await expect(page.getByText('Riepilogo del controllo')).toHaveCount(0)
    await expect(page.getByText('Numero massimo impostato')).toHaveCount(0)
    expect(duplicateRequests).toBe(1)
  })

  test('presents a model-unavailable error for a near-duplicate review', async ({ page }) => {
    const model = await readFile(modelPath)
    await rm(modelPath)
    try {
      await page.goto('/app/#/duplicates')
      await page.getByRole('button', { name: 'Avvia controllo' }).click()

      await expect(page.getByRole('heading', { name: 'Modello di somiglianza non disponibile' })).toBeVisible({ timeout: 15_000 })
      await expect(page.getByText('Controlla solo i duplicati esatti', { exact: false })).toBeVisible()
    } finally {
      await writeFile(modelPath, model)
    }
  })
})
