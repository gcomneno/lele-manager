import { expect, test } from '@playwright/test'

const left = {
  id: 'alpha/very-similar-left', title: 'Very similar left', text: 'Left reference knowledge.',
  topic: 'alpha', source: 'note', importance: 3, tags: ['one'], date: '2026-08-10',
}
const right = {
  id: 'alpha/very-similar-right', title: 'Very similar right', text: 'Right reference knowledge.',
  topic: 'alpha', source: 'note', importance: 4, tags: ['two'], date: '2026-08-10',
}

function report() {
  return {
    lessons_analyzed: 2, total_pairs: 1, exact_pairs: 1, near_pairs: 0,
    suppressed_pairs: 0, min_score: 0.85, exact_only: true,
    pairs: [{
      left_id: left.id, right_id: right.id, left_position: 0, right_position: 1,
      left_path: 'alpha/left.md', right_path: 'alpha/right.md', kind: 'exact', score: 1,
      reasons: ['exact_text'], shared_tags: [], left_fingerprint: 'left-fingerprint',
      right_fingerprint: 'right-fingerprint', resolution_available: true,
      left_lesson: left, right_lesson: right,
    }],
  }
}

test('duplicate resolution actions target exact sides and wait for confirmation', async ({ page }) => {
  const deletes: string[] = []
  const merges: unknown[] = []
  const decisions: unknown[] = []
  await page.route('**/duplicates?*', route => route.fulfill({ json: report() }))
  await page.route('**/duplicates/not-duplicates', async route => {
    decisions.push(route.request().postDataJSON())
    await route.fulfill({ json: { left_id: left.id, right_id: right.id, left_fingerprint: 'left-fingerprint', right_fingerprint: 'right-fingerprint', decided_at: '2026-08-10T00:00:00Z' } })
  })
  await page.route('**/duplicates/merge', async route => {
    merges.push(route.request().postDataJSON())
    await route.fulfill({ json: { completed: true, survivor_id: right.id, survivor_written: true, superseded_id: left.id, superseded_deleted: true, refresh_outcome: { attempted: true, refreshed: true } } })
  })
  await page.route('**/editor/metadata-options', route => route.fulfill({ json: { topics: [], tags: [], sources: [] } }))
  await page.route('**/lessons/**', async route => {
    const request = route.request()
    const id = decodeURIComponent(new URL(request.url()).pathname.replace(/^\/lessons\//, ''))
    if (request.method() === 'DELETE') {
      deletes.push(id)
      return route.fulfill({ json: { lesson_id: id, relative_vault_path: 'alpha/item.md', canonical_deleted: true, refresh_outcome: { refreshed: true } } })
    }
    return route.fulfill({ json: id === left.id ? left : right })
  })

  await page.goto('/app/#/duplicates')
  await page.getByRole('button', { name: 'Run review' }).click()
  const pair = page.locator('.duplicate-pair')
  for (const name of ['Edit left', 'Edit right', 'Keep left / delete right', 'Keep right / delete left', 'Not duplicates', 'Merge…']) {
    await expect(pair.getByRole('button', { name })).toBeVisible()
  }

  await pair.getByRole('button', { name: 'Edit left' }).click()
  await expect(page).toHaveURL(new RegExp(encodeURIComponent(left.id)))
  await page.goto('/app/#/duplicates')
  await page.getByRole('button', { name: 'Run review' }).click()
  await pair.getByRole('button', { name: 'Edit right' }).click()
  await expect(page).toHaveURL(new RegExp(encodeURIComponent(right.id)))

  await page.goto('/app/#/duplicates')
  await page.getByRole('button', { name: 'Run review' }).click()
  await pair.getByRole('button', { name: 'Keep left / delete right' }).click()
  const deleteDialog = page.getByRole('dialog', { name: 'Resolve duplicate by deleting?' })
  await expect(deleteDialog).toContainText(left.id)
  await expect(deleteDialog).toContainText(right.id)
  await page.keyboard.press('Escape')
  expect(deletes).toEqual([])
  await pair.getByRole('button', { name: 'Keep right / delete left' }).click()
  await deleteDialog.getByRole('button', { name: 'Delete permanently' }).click()
  await expect.poll(() => deletes).toEqual([left.id])

  await page.getByRole('button', { name: 'Run review' }).click()
  await pair.getByRole('button', { name: 'Not duplicates' }).click()
  const decisionDialog = page.getByRole('dialog', { name: 'Mark as not duplicates?' })
  await expect(decisionDialog).toContainText(left.id)
  await expect(decisionDialog).toContainText(right.id)
  await decisionDialog.getByRole('button', { name: 'Mark not duplicates' }).click()
  await expect.poll(() => decisions).toEqual([{ left_id: left.id, right_id: right.id, left_fingerprint: 'left-fingerprint', right_fingerprint: 'right-fingerprint' }])

  await page.getByRole('button', { name: 'Run review' }).click()
  await pair.getByRole('button', { name: 'Merge…' }).click()
  const mergeDialog = page.getByRole('dialog', { name: 'Merge LeLe' })
  await expect(mergeDialog).toContainText(left.text)
  await expect(mergeDialog).toContainText(right.text)
  expect(merges).toEqual([])
  await mergeDialog.getByRole('radio', { name: /Use right as result/ }).check()
  await mergeDialog.getByLabel('Resulting LeLe').fill('Manually reviewed merge.')
  await mergeDialog.getByRole('button', { name: 'Save merged LeLe and delete other' }).click()
  await expect(mergeDialog).toContainText(`Surviving LeLe: ${right.id}`)
  await mergeDialog.getByRole('button', { name: 'Save merged LeLe and delete other' }).click()
  await expect.poll(() => merges).toHaveLength(1)
  expect(merges[0]).toMatchObject({ survivor_id: right.id, superseded_id: left.id, result: { text: 'Manually reviewed merge.' } })
})
