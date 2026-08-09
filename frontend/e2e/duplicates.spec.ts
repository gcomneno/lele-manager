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

const unevenIdentityReport = {
  lessons_analyzed: 2,
  total_pairs: 1,
  exact_pairs: 1,
  near_pairs: 0,
  min_score: 0.85,
  exact_only: true,
  pairs: [
    {
      left_id: 'short-id',
      right_id: 'a-significantly-longer-lesson-identifier-that-needs-more-than-two-lines-to-render',
      left_position: 1,
      right_position: 2,
      left_path: 'short.md',
      right_path: 'a/significantly/longer/path/to/a/lesson/that-needs-more-than-two-lines-to-render.md',
      kind: 'exact',
      score: 1,
      reasons: ['duplicate_id'],
      shared_tags: [],
      left_lesson: { id: 'short-id', text: 'Short identity lesson text.', title: 'Short' },
      right_lesson: { id: 'a-significantly-longer-lesson-identifier-that-needs-more-than-two-lines-to-render', text: 'Long identity lesson text.', title: 'Long' },
    },
  ],
}

test.describe('duplicate review', () => {
  test('reviews an exact duplicate with both lessons visible', async ({ page }) => {
    await page.goto('/app/#/duplicates')
    await expect(page.getByRole('heading', { name: 'Duplicate review' })).toBeVisible()
    await page.getByRole('button', { name: 'Run review' }).click()

    const exactPair = page.locator('.duplicate-pair').filter({ hasText: 'exact duplicate' }).first()
    await expect(exactPair).toBeVisible({ timeout: 15_000 })
    await expect(exactPair.getByText('exact_text', { exact: false })).toBeVisible()
    await expect(exactPair.getByText('git branching merge rebase strategies')).toHaveCount(2)
    await expect(page.getByText('Total pairs before limit')).toBeVisible()
    await expect(page.getByText('Exact pairs before limit')).toBeVisible()
    await expect(page.getByText('Similarities before limit')).toBeVisible()
    await expect(page.getByText('Applied maximum count')).toBeVisible()
    await expect(page.locator('.summary').getByText('100', { exact: true })).toBeVisible()
  })

  test('reviews near duplicates from the real fixture API', async ({ page }) => {
    await page.goto('/app/#/duplicates')
    await page.getByLabel('Minimum score').fill('0')
    await page.getByRole('button', { name: 'Run review' }).click()

    const nearPair = page.locator('.duplicate-pair').filter({ hasText: 'possible similarity' }).first()
    await expect(nearPair).toBeVisible({ timeout: 15_000 })
    await expect(nearPair.getByText(/Score 0\./)).toBeVisible()
  })

  test('keeps records with a repeated ID independently inspectable by position', async ({ page }) => {
    await page.route('**/duplicates?*', async (route) => {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(repeatedIdReport) })
    })
    await page.goto('/app/#/duplicates')
    await page.getByRole('button', { name: 'Run review' }).click()

    const pair = page.locator('.duplicate-pair')
    await expect(pair.getByText('First record with the repeated ID.')).toBeVisible()
    await expect(pair.getByText('Second record with the repeated ID.')).toBeVisible()
    await expect(pair.getByText('4', { exact: true })).toBeVisible()
    await expect(pair.getByText('9', { exact: true })).toBeVisible()
    await expect(pair.getByText('same-id', { exact: true })).toHaveCount(2)
  })

  test('aligns lesson text after clamped identity values while retaining full values', async ({ page }) => {
    await page.route('**/duplicates?*', async (route) => {
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(unevenIdentityReport) })
    })
    await page.goto('/app/#/duplicates')
    await page.getByRole('button', { name: 'Run review' }).click()

    const pair = page.locator('.duplicate-pair')
    const lessons = pair.locator('.lesson')
    const identityValues = pair.locator('.identity-value')
    const longId = unevenIdentityReport.pairs[0].right_id
    const longPath = unevenIdentityReport.pairs[0].right_path

    await expect(identityValues).toHaveCount(4)
    await expect(identityValues.nth(2)).toHaveText(longId)
    await expect(identityValues.nth(2)).toHaveAttribute('title', longId)
    await expect(identityValues.nth(3)).toHaveText(longPath)
    await expect(identityValues.nth(3)).toHaveAttribute('title', longPath)
    await expect(lessons.nth(0).getByRole('heading', { name: 'Text' })).toHaveJSProperty('offsetTop', await lessons.nth(1).getByRole('heading', { name: 'Text' }).evaluate((element) => element.offsetTop))
    await expect(identityValues.nth(2)).toHaveCSS('-webkit-line-clamp', '2')
    await expect(identityValues.nth(3)).toHaveCSS('-webkit-line-clamp', '2')
  })

  test('runs exact-only review while the model is unavailable', async ({ page }) => {
    const model = await readFile(modelPath)
    await rm(modelPath)
    try {
      await page.goto('/app/#/duplicates')
      await page.getByLabel('Exact duplicates only').check()
      await page.getByRole('button', { name: 'Run review' }).click()

      await expect(page.getByText('Review summary')).toBeVisible({ timeout: 15_000 })
      await expect(page.locator('.summary').getByText('Yes', { exact: true })).toBeVisible()
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
    await page.getByRole('button', { name: 'Run review' }).click()

    await expect(page.getByRole('heading', { name: 'No duplicates found' })).toBeVisible()
    await expect(page.getByText('Pairs shown')).toBeVisible()
  })

  test('rejects an invalid minimum score without requesting duplicates or keeping a stale report', async ({ page }) => {
    let duplicateRequests = 0
    await page.route('**/duplicates?*', async (route) => {
      duplicateRequests += 1
      await route.fulfill({ contentType: 'application/json', body: JSON.stringify(repeatedIdReport) })
    })
    await page.goto('/app/#/duplicates')
    await page.getByRole('button', { name: 'Run review' }).click()
    await expect(page.getByText('Review summary')).toBeVisible()

    await page.getByLabel('Minimum score').fill('1.1')
    await page.getByRole('button', { name: 'Refresh review' }).click()

    await expect(page.getByText('Minimum score must be a number between 0 and 1.')).toBeVisible()
    await expect(page.getByText('Review summary')).toHaveCount(0)
    await expect(page.getByText('Applied maximum count')).toHaveCount(0)
    expect(duplicateRequests).toBe(1)
  })

  test('presents a model-unavailable error for a near-duplicate review', async ({ page }) => {
    const model = await readFile(modelPath)
    await rm(modelPath)
    try {
      await page.goto('/app/#/duplicates')
      await page.getByRole('button', { name: 'Run review' }).click()

      await expect(page.getByRole('heading', { name: 'Similarity model unavailable' })).toBeVisible({ timeout: 15_000 })
      await expect(page.getByText('Check exact duplicates only', { exact: false })).toBeVisible()
    } finally {
      await writeFile(modelPath, model)
    }
  })
})
