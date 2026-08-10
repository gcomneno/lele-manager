import { expect, test, type Page } from '@playwright/test'

type Lesson = {
  id: string
  title: string
  text: string
  topic: string
  source: string
  importance: number
  tags: string[]
  date: string
}

const a: Lesson = { id: 'browse/a', title: 'Alpha', text: 'A', topic: 'browse', source: 'note', importance: 3, tags: [], date: '2026-08-10' }
const b: Lesson = { id: 'browse/b', title: 'Bravo', text: 'B', topic: 'browse', source: 'note', importance: 3, tags: [], date: '2026-08-10' }
const c: Lesson = { id: 'browse/c', title: 'Charlie', text: 'C', topic: 'browse', source: 'note', importance: 3, tags: [], date: '2026-08-10' }

async function mockBrowse(page: Page, bulkMode: 'success' | 'mixed' | 'refresh-failed' | 'all-failed' = 'success') {
  let results = [a, b, c]
  const payloads: string[][] = []
  const searches: unknown[] = []

  await page.route('**/lessons/*', async (route) => {
    if (route.request().method() !== 'DELETE') return route.fallback()
    const id = decodeURIComponent(new URL(route.request().url()).pathname.replace(/^\/lessons\//, ''))
    results = results.filter((lesson) => lesson.id !== id)
    return route.fulfill({ json: { lesson_id: id, relative_vault_path: `${id}.md`, canonical_deleted: true, refresh_outcome: { refreshed: true } } })
  })
  await page.route('**/lessons/bulk-delete', async (route) => {
    const lessonIds = (route.request().postDataJSON() as { lesson_ids: string[] }).lesson_ids
    payloads.push(lessonIds)
    if (bulkMode === 'all-failed') {
      return route.fulfill({ json: { requested_count: lessonIds.length, deleted: [], failed: lessonIds.map((lesson_id) => ({ lesson_id, code: 'storage_error' })), refresh_outcome: { attempted: false, refreshed: false } } })
    }
    const deleted = lessonIds.filter((id) => bulkMode === 'success' || id === b.id)
    const failed = lessonIds.filter((id) => !deleted.includes(id)).map((lesson_id) => ({ lesson_id, code: 'storage_error' }))
    results = results.filter((lesson) => !deleted.includes(lesson.id))
    const response = { requested_count: lessonIds.length, deleted: deleted.map((lesson_id) => ({ lesson_id, relative_vault_path: `${lesson_id}.md` })), failed, refresh_outcome: { attempted: true, refreshed: bulkMode !== 'refresh-failed' } }
    if (bulkMode === 'refresh-failed') {
      return route.fulfill({ status: 503, json: { detail: { code: 'bulk_lessons_deleted_refresh_failed', message: 'refresh failed', recovery: response } } })
    }
    return route.fulfill({ json: response })
  })
  await page.route('**/lessons/search', async (route) => {
    searches.push(route.request().postDataJSON())
    const query = (route.request().postDataJSON() as { q?: string | null }).q
    return route.fulfill({ json: query === 'next' ? [b, c] : results })
  })
  await page.route('**/lessons?*', (route) => route.fulfill({ json: results }))
  return { payloads, searches }
}

test('Browse selection is bounded to the current result snapshot', async ({ page }) => {
  await mockBrowse(page)
  await page.goto('/app/#/browse')

  await page.getByLabel(/Select LeLe Alpha/).check()
  await expect(page.getByText('1 LeLe selected')).toBeVisible()
  await page.getByLabel('Query').fill('next')
  await page.getByRole('button', { name: 'Search', exact: true }).click()
  await expect(page.getByText('1 LeLe selected')).toHaveCount(0)

  await page.getByRole('button', { name: 'Select all visible' }).click()
  await expect(page.getByText('2 LeLe selected')).toBeVisible()
  await expect(page.getByLabel(/Select LeLe Bravo/)).toBeChecked()
  await expect(page.getByLabel(/Select LeLe Charlie/)).toBeChecked()
  await expect(page.getByLabel(/Select LeLe Alpha/)).toHaveCount(0)
  await page.getByRole('button', { name: 'Clear selection' }).click()
  await expect(page.getByText(/LeLe selected/)).toHaveCount(0)
})

test('Browse bulk confirmation lists exact selected lessons and sends one ordered request', async ({ page }) => {
  const calls = await mockBrowse(page)
  await page.goto('/app/#/browse')
  await page.getByLabel(/Select LeLe Bravo/).check()
  await page.getByLabel(/Select LeLe Charlie/).check()
  await page.getByRole('button', { name: 'Delete selected' }).click()
  const dialog = page.getByRole('dialog', { name: 'Delete 2 selected LeLe?' })
  await expect(dialog).toContainText(b.title)
  await expect(dialog).toContainText(b.id)
  await expect(dialog).toContainText(c.title)
  await expect(dialog).toContainText(c.id)
  await expect(dialog).not.toContainText(a.id)
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  expect(calls.payloads).toEqual([])

  await page.getByRole('button', { name: 'Delete selected' }).click()
  await page.keyboard.press('Escape')
  expect(calls.payloads).toEqual([])
  await page.getByRole('button', { name: 'Delete selected' }).click()
  await dialog.getByRole('button', { name: 'Delete selected' }).click()
  await expect.poll(() => calls.payloads).toEqual([[b.id, c.id]])
  await expect(page.getByTestId(`lesson-result-${a.id}`)).toBeVisible()
  await expect(page.getByTestId(`lesson-result-${b.id}`)).toHaveCount(0)
  await expect(page.getByTestId(`lesson-result-${c.id}`)).toHaveCount(0)
  await expect(page.getByText('Deleted 2 LeLe.')).toBeVisible()
})

test('mixed and refresh-failure outcomes preserve failed selected targets and canonical truth', async ({ page }) => {
  await mockBrowse(page, 'refresh-failed')
  await page.goto('/app/#/browse')
  await page.getByLabel(/Select LeLe Bravo/).check()
  await page.getByLabel(/Select LeLe Charlie/).check()
  await page.getByRole('button', { name: 'Delete selected' }).click()
  await page.getByRole('dialog', { name: 'Delete 2 selected LeLe?' }).getByRole('button', { name: 'Delete selected' }).click()

  await expect(page.getByTestId(`lesson-result-${b.id}`)).toHaveCount(0)
  await expect(page.getByTestId(`lesson-result-${c.id}`)).toBeVisible()
  await expect(page.getByLabel(/Select LeLe Charlie/)).toBeChecked()
  await expect(page.getByText(/Canonical LeLe were deleted, but derived data could not be refreshed/)).toBeVisible()
  await expect(page.getByText('Search and similarity results may be stale.')).toBeVisible()
  await expect(page.locator('.bulk-failed-targets')).toContainText(c.id)
  await expect(page.getByText(/Bulk delete failed/i)).toHaveCount(0)
})

test('all canonical failures leave visible selections and do not claim a refresh failure', async ({ page }) => {
  await mockBrowse(page, 'all-failed')
  await page.goto('/app/#/browse')
  await page.getByLabel(/Select LeLe Bravo/).check()
  await page.getByRole('button', { name: 'Delete selected' }).click()
  await page.getByRole('dialog', { name: 'Delete 1 selected LeLe?' }).getByRole('button', { name: 'Delete selected' }).click()
  await expect(page.getByTestId(`lesson-result-${b.id}`)).toBeVisible()
  await expect(page.getByLabel(/Select LeLe Bravo/)).toBeChecked()
  await expect(page.getByText('No selected LeLe could be deleted.')).toBeVisible()
  await expect(page.getByText(/derived data could not be refreshed/)).toHaveCount(0)
})

test('single-card deletion removes a selected canonical success from Browse selection', async ({ page }) => {
  await mockBrowse(page)
  await page.goto('/app/#/browse')
  await page.getByLabel(/Select LeLe Bravo/).check()
  await expect(page.getByText('1 LeLe selected')).toBeVisible()
  const target = page.getByTestId(`lesson-result-${b.id}`)
  await target.getByRole('button', { name: 'Delete' }).click()
  await page.getByRole('dialog', { name: 'Delete LeLe?' }).getByRole('button', { name: 'Delete' }).click()
  await expect(target).toHaveCount(0)
  await expect(page.getByText(/LeLe selected/)).toHaveCount(0)
})

test('Italian localizes Browse selection and bulk confirmation', async ({ page }) => {
  await mockBrowse(page)
  await page.goto('/app/#/browse')
  await page.getByLabel('Language').selectOption('it')
  await page.getByLabel(/Seleziona LeLe Bravo/).check()
  await expect(page.getByText('1 LeLe selezionata')).toBeVisible()
  await page.getByRole('button', { name: 'Elimina selezionate' }).click()
  const dialog = page.getByRole('dialog', { name: 'Eliminare 1 LeLe selezionate?' })
  await expect(dialog).toContainText('Le seguenti LeLe Markdown canoniche verranno eliminate definitivamente.')
  await expect(dialog).toContainText(b.id)
  await dialog.getByRole('button', { name: 'Annulla' }).click()
})
