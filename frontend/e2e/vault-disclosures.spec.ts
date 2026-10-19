import { expect, test, type Page } from '@playwright/test'
import type { VaultTreeResponse } from '../src/lib/api'

// Includes siblings, an empty directory and directories hidden by closed ancestors.
const tree: VaultTreeResponse = {
  vault_dir: '/fixture/vault',
  tree: { type: 'dir', name: 'vault', children: [
    { type: 'dir', name: 'notes', children: [
      { type: 'dir', name: 'nested', children: [
        { type: 'dir', name: 'deep', children: [
          { type: 'file', name: 'lesson.md', id: 'notes/lesson' },
        ] },
      ] },
    ] },
    { type: 'dir', name: 'empty', children: [] },
    { type: 'dir', name: 'other', children: [
      { type: 'file', name: 'other.md', id: 'other/lesson' },
    ] },
  ] },
}
const initialState = [true, true, false, false, true, true]

async function expectState(page: Page, states: boolean[]) {
  await expect(page.locator('#vault-tree details')).toHaveCount(states.length)
  await expect.poll(() => page.locator('#vault-tree details').evaluateAll(
    (elements) => elements.map((element) => (element as HTMLDetailsElement).open),
  )).toEqual(states)
}

async function expectAll(page: Page, open: boolean) {
  await expectState(page, initialState.map(() => open))
}

function summary(page: Page, name: string) {
  return page.locator('#vault-tree summary').filter({ hasText: new RegExp(`^${name}$`) })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('lele-manager.locale', 'en'))
  await page.route('**/vault/status', (route) => route.fulfill({ json: {
    exists: true, vault_dir: tree.vault_dir, vault_id: 'fixture', display_name: 'Fixture',
  } }))
  await page.route('**/vaults', (route) => route.fulfill({ json: [] }))
  await page.route('**/vault-transfers/sources/*/lessons', (route) => route.fulfill({ json: [] }))
  await page.route('**/vault/tree', (route) => route.fulfill({ json: tree }))
  await page.goto('/app/#/vault')
  await expectState(page, initialState)
})

test('expands and collapses every directory, including hidden descendants and empty directories', async ({ page }) => {
  const mutations: string[] = []
  page.on('request', (request) => {
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())) mutations.push(request.url())
  })
  await page.getByRole('button', { name: 'Expand all', exact: true }).click()
  await expectAll(page, true)
  await expect(page.getByRole('button', { name: 'lesson.md', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Collapse all', exact: true }).click()
  await expectAll(page, false)
  await expect(page.getByRole('button', { name: 'lesson.md', exact: true })).toBeHidden()
  await page.getByRole('button', { name: 'Expand all', exact: true }).click()
  await expectAll(page, true)
  expect(mutations).toEqual([])
})

test('resolves mixed states in both directions and preserves individual toggles after repeated commands', async ({ page }) => {
  await page.getByRole('button', { name: 'Expand all', exact: true }).click()
  await summary(page, 'notes').click()
  await expectState(page, [true, false, true, true, true, true])
  await page.getByRole('button', { name: 'Expand all', exact: true }).click()
  await expectAll(page, true)
  await summary(page, 'nested').click()
  await page.getByRole('button', { name: 'Collapse all', exact: true }).click()
  await expectAll(page, false)
  await summary(page, 'vault').click()
  await summary(page, 'empty').click()
  await expectState(page, [true, false, false, false, true, false])
  await page.getByRole('button', { name: 'Collapse all', exact: true }).click()
  await expectAll(page, false)
  await summary(page, 'vault').click()
  await expectState(page, [true, false, false, false, false, false])
})

test('restores the initial layout on route re-entry, reload and tree refresh', async ({ page }) => {
  await page.getByRole('button', { name: 'Expand all', exact: true }).click()
  await expectAll(page, true)
  await page.evaluate(() => { window.location.hash = '#/' })
  await expect(page.locator('#vault-tree')).toHaveCount(0)
  await page.evaluate(() => { window.location.hash = '#/vault' })
  await expectState(page, initialState)
  await page.getByRole('button', { name: 'Collapse all', exact: true }).click()
  await page.reload()
  await expectState(page, initialState)
  await page.getByRole('button', { name: 'Expand all', exact: true }).click()
  await page.getByRole('button', { name: 'Refresh', exact: true }).click()
  await expectState(page, initialState)
})

test('keeps localized labels, keyboard operation, focus and controls usable at a narrow viewport', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  const expand = page.getByRole('button', { name: 'Expand all', exact: true })
  const collapse = page.getByRole('button', { name: 'Collapse all', exact: true })
  await expect(expand).toHaveAttribute('aria-controls', 'vault-tree')
  await expect(collapse).toHaveAttribute('aria-controls', 'vault-tree')
  await expand.focus()
  await page.keyboard.press('Enter')
  await expectAll(page, true)
  await expect(expand).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(collapse).toBeFocused()
  await page.keyboard.press('Space')
  await expectAll(page, false)
  await expect(collapse).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(summary(page, 'vault')).toBeFocused()
  await page.keyboard.press('Enter')
  await expectState(page, [true, false, false, false, false, false])
  await expect(summary(page, 'vault')).toBeFocused()

  await page.getByLabel('Language', { exact: true }).selectOption('it')
  const expandIt = page.getByRole('button', { name: 'Espandi tutto', exact: true })
  const collapseIt = page.getByRole('button', { name: 'Comprimi tutto', exact: true })
  for (const control of [expandIt, collapseIt]) {
    await control.scrollIntoViewIfNeeded()
    await expect(control).toBeInViewport()
    const box = await control.boundingBox()
    expect(box).not.toBeNull()
    expect(box!.x).toBeGreaterThanOrEqual(0)
    expect(box!.x + box!.width).toBeLessThanOrEqual(375)
  }
  await expandIt.click()
  await expectAll(page, true)
  await collapseIt.click()
  await expectAll(page, false)
})
