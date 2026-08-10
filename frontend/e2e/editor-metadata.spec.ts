import { expect, test } from '@playwright/test'

const options = {
  topics: [{ value: 'python', count: 4 }, { value: 'linux', count: 2 }],
  tags: [{ value: 'pytest', count: 4 }, { value: 'python', count: 2 }],
  sources: [{ value: 'note', count: 4 }, { value: 'book', count: 1 }],
}

test('metadata suggestions are advisory and tags serialize as user-confirmed chips', async ({ page }) => {
  let writes = 0
  let payload: unknown
  await page.route('**/editor/metadata-options', route => route.fulfill({ json: options }))
  await page.route('**/vault/lessons', async route => {
    writes += 1
    payload = route.request().postDataJSON()
    await route.fulfill({ status: 201, json: { id: 'python/test', ...(payload as object) } })
  })
  await page.goto('/app/#/editor')

  await expect(page.getByLabel('Topic')).toHaveValue('')
  await expect(page.locator('#known-topics option')).toHaveCount(2)
  await expect(page.getByLabel('Importance')).toHaveValue('3')
  await expect(page.getByLabel('Importance').locator('option')).toHaveCount(5)
  expect(writes).toBe(0)

  await page.getByLabel('Topic').fill('linux')
  await page.getByPlaceholder('Add a tag').fill('pytest')
  await page.getByRole('button', { name: 'Add tag' }).click()
  await page.getByPlaceholder('Add a tag').fill('pytest')
  await page.getByRole('button', { name: 'Add tag' }).click()
  await expect(page.getByRole('button', { name: 'Remove tag: pytest' })).toHaveCount(1)
  await page.getByPlaceholder('Add a tag').fill('new-tag')
  await page.keyboard.press('Enter')
  await page.getByPlaceholder('Write the lesson learned…').fill('A sufficiently complete body.')
  await page.getByRole('button', { name: 'Save to vault' }).click()
  await expect.poll(() => writes).toBe(1)
  expect(payload).toMatchObject({ topic: 'linux', source: 'note', importance: 3, tags: ['pytest', 'new-tag'] })
})

test('metadata-options failure does not block manual authoring', async ({ page }) => {
  await page.route('**/editor/metadata-options', route => route.fulfill({ status: 500, body: 'offline' }))
  await page.goto('/app/#/editor')
  await expect(page.getByText('Metadata suggestions are unavailable. You can still enter values manually.')).toBeVisible()
  await page.getByLabel('Topic').fill('handwritten')
  await expect(page.getByText('Use new topic: handwritten')).toBeVisible()
})
