import { expect, test, type Page } from '@playwright/test'

const left = { id: 'alpha/very-similar-left', title: 'Very similar left', text: 'Left reference knowledge.', topic: 'alpha', source: 'note', importance: 3, tags: ['one'], date: '2026-08-10' }
const right = { id: 'alpha/very-similar-right', title: 'Very similar right', text: 'Right reference knowledge.', topic: 'alpha', source: 'note', importance: 4, tags: ['two'], date: '2026-08-10' }

function duplicateReport(pairs = true, suppressed = 0) {
  return {
    lessons_analyzed: 2, total_pairs: pairs ? 1 : 0, exact_pairs: pairs ? 1 : 0, near_pairs: 0,
    suppressed_pairs: suppressed, min_score: 0.85, exact_only: false,
    pairs: pairs ? [{
      left_id: left.id, right_id: right.id, left_position: 0, right_position: 1,
      left_path: 'alpha/left.md', right_path: 'alpha/right.md', kind: 'exact', score: 1,
      reasons: ['exact_text'], shared_tags: [], left_fingerprint: 'left-fingerprint', right_fingerprint: 'right-fingerprint',
      resolution_available: true, left_lesson: left, right_lesson: right,
    }] : [],
  }
}

async function mockReview(page: Page, report: () => object) {
  await page.route('**/duplicates?*', route => route.fulfill({ json: report() }))
  await page.route('**/editor/metadata-options', route => route.fulfill({ json: { topics: [], tags: [], sources: [] } }))
}

async function runInitialReview(page: Page) {
  await page.goto('/app/#/duplicates')
  await page.getByRole('button', { name: 'Run review' }).click()
  await expect(page.locator('.duplicate-pair')).toBeVisible()
}

test('exposes actions and routes each edit to its stable ID', async ({ page }) => {
  await mockReview(page, () => duplicateReport())
  await runInitialReview(page)
  const pair = page.locator('.duplicate-pair')
  for (const name of ['Edit left', 'Edit right', 'Keep left / delete right', 'Keep right / delete left', 'Not duplicates', 'Merge…']) await expect(pair.getByRole('button', { name })).toBeVisible()
  await pair.getByRole('button', { name: 'Edit left' }).click()
  await expect(page).toHaveURL(new RegExp(encodeURIComponent(left.id)))
  await page.goto('/app/#/duplicates')
  await page.getByRole('button', { name: 'Run review' }).click()
  await page.locator('.duplicate-pair').getByRole('button', { name: 'Edit right' }).click()
  await expect(page).toHaveURL(new RegExp(encodeURIComponent(right.id)))
})

test('keep left deletes exactly right and cancellation never mutates', async ({ page }) => {
  const deletes: string[] = []
  await mockReview(page, () => duplicateReport())
  await page.route('**/lessons/**', async route => {
    if (route.request().method() === 'DELETE') deletes.push(decodeURIComponent(new URL(route.request().url()).pathname.replace('/lessons/', '')))
    await route.fulfill({ json: { lesson_id: right.id, relative_vault_path: 'alpha/right.md', canonical_deleted: true, refresh_outcome: { refreshed: true } } })
  })
  await runInitialReview(page)
  const action = page.locator('.duplicate-pair').getByRole('button', { name: 'Keep left / delete right' })
  await action.click()
  const dialog = page.getByRole('dialog', { name: 'Resolve duplicate by deleting?' })
  await expect(dialog).toContainText(`Keep${left.title}`)
  await expect(dialog).toContainText(right.id)
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  expect(deletes).toEqual([])
  await action.click()
  await page.keyboard.press('Escape')
  expect(deletes).toEqual([])
  await action.click()
  await dialog.getByRole('button', { name: 'Delete permanently' }).click()
  await expect.poll(() => deletes).toEqual([right.id])
  expect(deletes).not.toContain(left.id)
})

test('keep right deletes exactly left', async ({ page }) => {
  const deletes: string[] = []
  await mockReview(page, () => duplicateReport())
  await page.route('**/lessons/**', async route => {
    if (route.request().method() === 'DELETE') deletes.push(decodeURIComponent(new URL(route.request().url()).pathname.replace('/lessons/', '')))
    await route.fulfill({ json: { lesson_id: left.id, relative_vault_path: 'alpha/left.md', canonical_deleted: true, refresh_outcome: { refreshed: true } } })
  })
  await runInitialReview(page)
  await page.locator('.duplicate-pair').getByRole('button', { name: 'Keep right / delete left' }).click()
  await page.getByRole('dialog', { name: 'Resolve duplicate by deleting?' }).getByRole('button', { name: 'Delete permanently' }).click()
  await expect.poll(() => deletes).toEqual([left.id])
  expect(deletes).not.toContain(right.id)
})

test('canonical delete with refresh failure prunes locally without rerunning a stale review', async ({ page }) => {
  let reviewCalls = 0
  await mockReview(page, () => { reviewCalls++; return duplicateReport() })
  await page.route('**/lessons/**', route => route.fulfill({ status: 503, json: { detail: { code: 'lesson_deleted_refresh_failed', message: 'refresh failed', recovery: { canonical_deleted: true, lesson_id: right.id, relative_vault_path: 'alpha/right.md' } } } }))
  await runInitialReview(page)
  await page.locator('.duplicate-pair').getByRole('button', { name: 'Keep left / delete right' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Delete permanently' }).click()
  await expect(page.getByText('The canonical LeLe was deleted; derived duplicate and search data may be stale.')).toBeVisible()
  await expect(page.locator('.duplicate-pair')).toHaveCount(0)
  expect(reviewCalls).toBe(1)
})

test('canonical delete failure leaves the current pair usable', async ({ page }) => {
  await mockReview(page, () => duplicateReport())
  await page.route('**/lessons/**', route => route.fulfill({ status: 503, json: { detail: { code: 'lesson_delete_storage_failed', message: 'No delete' } } }))
  await runInitialReview(page)
  await page.locator('.duplicate-pair').getByRole('button', { name: 'Keep right / delete left' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Delete permanently' }).click()
  await expect(page.getByText('The canonical LeLe could not be deleted.')).toBeVisible()
  await expect(page.locator('.duplicate-pair')).toBeVisible()
})

test('not duplicates saves exact fingerprints and shows the suppressed result', async ({ page }) => {
  const decisions: unknown[] = []
  const otherMutations: string[] = []
  let suppressed = false
  await mockReview(page, () => duplicateReport(!suppressed, suppressed ? 1 : 0))
  await page.route('**/duplicates/merge', route => { otherMutations.push(route.request().method()); return route.abort() })
  await page.route('**/lessons/**', route => {
    if (route.request().method() === 'DELETE' || route.request().method() === 'PUT') otherMutations.push(route.request().method())
    return route.continue()
  })
  await page.route('**/duplicates/not-duplicates', async route => {
    decisions.push(route.request().postDataJSON()); suppressed = true
    await route.fulfill({ json: { left_id: left.id, right_id: right.id, left_fingerprint: 'left-fingerprint', right_fingerprint: 'right-fingerprint', decided_at: '2026-08-10T00:00:00Z' } })
  })
  await runInitialReview(page)
  await page.locator('.duplicate-pair').getByRole('button', { name: 'Not duplicates' }).click()
  await page.getByRole('dialog', { name: 'Mark as not duplicates?' }).getByRole('button', { name: 'Mark not duplicates' }).click()
  await expect.poll(() => decisions[0]).toMatchObject({ left_id: left.id, right_id: right.id, left_fingerprint: 'left-fingerprint', right_fingerprint: 'right-fingerprint' })
  await expect(page.locator('.duplicate-pair')).toHaveCount(0)
  await expect(page.getByText('Suppressed pairs').locator('..')).toContainText('1')
  expect(otherMutations).toEqual([])
})

test('stale not-duplicates decision keeps the pair visible and reruns review', async ({ page }) => {
  let reviews = 0
  await mockReview(page, () => { reviews++; return duplicateReport() })
  await page.route('**/duplicates/not-duplicates', route => route.fulfill({ status: 409, json: { detail: { code: 'duplicate_pair_stale', message: 'stale' } } }))
  await runInitialReview(page)
  await page.locator('.duplicate-pair').getByRole('button', { name: 'Not duplicates' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Mark not duplicates' }).click()
  await expect(page.getByText('One or both LeLe changed. Refresh the duplicate review.')).toBeVisible()
  await expect(page.locator('.duplicate-pair')).toBeVisible()
  expect(reviews).toBe(2)
})

test('merge requires an explicit survivor and starts from the first selected source', async ({ page }) => {
  await mockReview(page, () => duplicateReport())
  await runInitialReview(page)
  await page.locator('.duplicate-pair').getByRole('button', { name: 'Merge…' }).click()
  const dialog = page.getByRole('dialog', { name: 'Merge LeLe' })
  await expect(dialog.getByRole('radio', { name: /Use left as result/ })).not.toBeChecked()
  await expect(dialog.getByRole('radio', { name: /Use right as result/ })).not.toBeChecked()
  await expect(dialog.getByRole('button', { name: 'Save merged LeLe and delete other' })).toBeDisabled()
  await dialog.getByRole('radio', { name: /Use right as result/ }).check()
  await expect(dialog.getByLabel('Resulting LeLe')).toHaveValue(right.text)
  await expect(dialog.getByLabel('Title')).toHaveValue(right.title)
})

test('merge left starts from left and preserves an edited draft while survivor changes', async ({ page }) => {
  await mockReview(page, () => duplicateReport())
  await runInitialReview(page)
  await page.locator('.duplicate-pair').getByRole('button', { name: 'Merge…' }).click()
  const dialog = page.getByRole('dialog', { name: 'Merge LeLe' })
  await dialog.getByRole('radio', { name: /Use left as result/ }).check()
  await expect(dialog.getByLabel('Resulting LeLe')).toHaveValue(left.text)
  await dialog.getByLabel('Resulting LeLe').fill('Human reviewed draft')
  await dialog.getByRole('radio', { name: /Use right as result/ }).check()
  await expect(dialog.getByLabel('Resulting LeLe')).toHaveValue('Human reviewed draft')
})

test('merge partial refresh truth does not hide an undeleted source', async ({ page }) => {
  await mockReview(page, () => duplicateReport())
  await page.route('**/duplicates/merge', route => route.fulfill({ status: 503, json: { detail: { code: 'duplicate_merge_refresh_failed', message: 'refresh failed', recovery: { survivor_id: right.id, survivor_written: true, superseded_id: left.id, superseded_deleted: false, failure: { code: 'duplicate_merge_superseded_delete_failed' }, refresh_outcome: { attempted: true, refreshed: false } } } } }))
  await runInitialReview(page)
  await page.locator('.duplicate-pair').getByRole('button', { name: 'Merge…' }).click()
  const dialog = page.getByRole('dialog', { name: 'Merge LeLe' })
  await dialog.getByRole('radio', { name: /Use right as result/ }).check()
  await dialog.getByRole('button', { name: 'Save merged LeLe and delete other' }).click()
  await dialog.getByRole('button', { name: 'Save merged LeLe and delete other' }).click()
  await expect(page.getByText('The resulting canonical LeLe was saved. The superseded LeLe could not be deleted, and derived data could not be refreshed. Duplicate review may be stale.')).toBeVisible()
  await expect(page.locator('.duplicate-pair')).toBeVisible()
})

test('merge full canonical success with refresh failure prunes only the deleted source locally', async ({ page }) => {
  let reviews = 0
  await mockReview(page, () => { reviews++; return duplicateReport() })
  await page.route('**/duplicates/merge', route => route.fulfill({ status: 503, json: { detail: { code: 'duplicate_merge_refresh_failed', message: 'refresh failed', recovery: { survivor_id: right.id, survivor_written: true, superseded_id: left.id, superseded_deleted: true, refresh_outcome: { attempted: true, refreshed: false } } } } }))
  await runInitialReview(page)
  await page.locator('.duplicate-pair').getByRole('button', { name: 'Merge…' }).click()
  const dialog = page.getByRole('dialog', { name: 'Merge LeLe' })
  await dialog.getByRole('radio', { name: /Use right as result/ }).check()
  await dialog.getByRole('button', { name: 'Save merged LeLe and delete other' }).click()
  await dialog.getByRole('button', { name: 'Save merged LeLe and delete other' }).click()
  await expect(page.getByText('Canonical merge changes succeeded, but derived data could not be refreshed. Duplicate review may be stale.')).toBeVisible()
  await expect(page.locator('.duplicate-pair')).toHaveCount(0)
  expect(reviews).toBe(1)
})

test('native destructive dialog contains focus and restores its trigger after Escape', async ({ page }) => {
  await mockReview(page, () => duplicateReport())
  await runInitialReview(page)
  const trigger = page.locator('.duplicate-pair').getByRole('button', { name: 'Keep left / delete right' })
  await trigger.focus()
  await trigger.click()
  const dialog = page.getByRole('dialog', { name: 'Resolve duplicate by deleting?' })
  await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused()
  await expect(page.locator('.duplicate-pair').getByRole('button', { name: 'Merge…' })).not.toBeFocused()
  await page.keyboard.press('Escape')
  await expect(trigger).toBeFocused()
})

test('Italian localizes duplicate actions and keeps resolution IDs and fingerprints stable', async ({ page }) => {
  const decisions: unknown[] = []
  await page.addInitScript(() => localStorage.setItem('lele-manager.locale', 'it'))
  await mockReview(page, () => duplicateReport())
  await page.route('**/duplicates/not-duplicates', async route => {
    decisions.push(route.request().postDataJSON())
    await route.fulfill({ json: { left_id: left.id, right_id: right.id, left_fingerprint: 'left-fingerprint', right_fingerprint: 'right-fingerprint', decided_at: '2026-08-10T00:00:00Z' } })
  })
  await page.goto('/app/#/duplicates')
  await page.getByRole('button', { name: 'Avvia controllo' }).click()
  const pair = page.locator('.duplicate-pair')
  for (const name of ['Modifica sinistra', 'Modifica destra', 'Mantieni sinistra / elimina destra', 'Mantieni destra / elimina sinistra', 'Non sono duplicati', 'Accorpa…']) await expect(pair.getByRole('button', { name })).toBeVisible()
  await pair.getByRole('button', { name: 'Mantieni sinistra / elimina destra' }).click()
  await expect(page.getByRole('dialog', { name: 'Risolvere il duplicato eliminando?' })).toContainText(right.id)
  await page.keyboard.press('Escape')
  await pair.getByRole('button', { name: 'Non sono duplicati' }).click()
  await page.getByRole('dialog', { name: 'Segnare come non duplicati?' }).getByRole('button', { name: 'Segna non duplicati' }).click()
  await expect.poll(() => decisions[0]).toMatchObject({ left_id: left.id, right_id: right.id, left_fingerprint: 'left-fingerprint', right_fingerprint: 'right-fingerprint' })
})
