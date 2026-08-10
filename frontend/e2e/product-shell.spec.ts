import { expect, test, type Page } from '@playwright/test'

const navigationGroupsStorageKey = 'lele-manager.navigation-groups.v1'
const sidebarStorageKey = 'lele-manager.sidebar-visible.v1'

async function clearSidebarPreference(page: Page) {
  await page.goto('/app/#/')
  await page.evaluate((key) => window.localStorage.removeItem(key), sidebarStorageKey)
  await page.reload()
}

test.describe('global application header', () => {
  test('keeps New LeLe contextual and does not expose false global actions', async ({ page }) => {
    await page.goto('/app/#/')

    const header = page.locator('header')
    const navigation = page.getByRole('navigation', { name: 'Primary' })

    await expect(navigation.getByRole('link', { name: 'New LeLe', exact: true })).toHaveAttribute('href', '#/editor')
    await expect(page.getByTestId('new-lesson-cta')).toHaveCount(0)
    await expect(header.locator('a[href="#/editor"]')).toHaveCount(0)

    for (const label of ['Save', 'Delete', 'Refresh model', 'Logout', 'Sign out']) {
      await expect(header.getByRole('button', { name: label, exact: true })).toHaveCount(0)
      await expect(header.getByRole('link', { name: label, exact: true })).toHaveCount(0)
    }
  })

  test('shows bounded workspace context and compact runtime health in the header', async ({ page }) => {
    await page.goto('/app/#/')

    const workspace = page.getByTestId('header-workspace')
    await expect(workspace).toBeVisible()
    await expect(workspace.getByText('Workspace', { exact: true })).toBeVisible()
    await expect(page.getByTestId('shell-workspace')).toHaveText(/\S+/)
    expect(await page.getByTestId('shell-workspace').textContent()).not.toMatch(/[\\/]/)
    await expect(page.locator('header .health-bar')).toBeVisible()
  })

  test('defaults to a visible sidebar and persists whole-sidebar visibility independently', async ({ page }) => {
    await clearSidebarPreference(page)

    const toggle = page.getByTestId('sidebar-toggle')
    await expect(toggle).toHaveAccessibleName('Hide navigation')
    await expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await expect(page.locator('#primary-sidebar')).toBeVisible()

    await toggle.click()
    await expect(toggle).toHaveAccessibleName('Show navigation')
    await expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await expect(page.locator('#primary-sidebar')).toHaveCount(0)
    await expect.poll(() => page.evaluate((key) => localStorage.getItem(key), sidebarStorageKey)).toBe('false')

    await page.reload()
    await expect(page.locator('#primary-sidebar')).toHaveCount(0)
    await page.getByTestId('sidebar-toggle').click()
    await expect(page.locator('#primary-sidebar')).toBeVisible()
    await expect.poll(() => page.evaluate((key) => localStorage.getItem(key), sidebarStorageKey)).toBe('true')

    await page.getByTestId('sidebar-toggle').focus()
    await page.keyboard.press('Enter')
    await expect(page.locator('#primary-sidebar')).toHaveCount(0)
    await page.keyboard.press('Space')
    await expect(page.locator('#primary-sidebar')).toBeVisible()
  })

  test('safely defaults from malformed visibility storage and retains it across locale changes', async ({ page }) => {
    await page.addInitScript((key) => window.localStorage.setItem(key, '{invalid'), sidebarStorageKey)
    await page.goto('/app/#/')
    await expect(page.locator('#primary-sidebar')).toBeVisible()

    await page.getByTestId('sidebar-toggle').click()
    await page.getByLabel('Language').selectOption('it')
    await expect(page.getByTestId('sidebar-toggle')).toHaveAccessibleName('Mostra navigazione')
    await expect(page.locator('#primary-sidebar')).toHaveCount(0)
  })

  test('preserves #180 disclosure state and current-route semantics through hide and restore', async ({ page }) => {
    await page.addInitScript((key) => window.localStorage.setItem(key, JSON.stringify({
      knowledge: false,
      capture: true,
      manage: true,
    })), navigationGroupsStorageKey)
    await page.goto('/app/#/settings')

    const navigation = page.getByRole('navigation', { name: 'Primary' })
    await expect(navigation.getByRole('button', { name: 'Knowledge', exact: true })).toHaveAttribute('aria-expanded', 'false')
    await expect(navigation.getByRole('link', { name: 'Diagnostics', exact: true })).toHaveAttribute('aria-current', 'page')

    await page.getByTestId('sidebar-toggle').click()
    await expect(page.locator('#primary-sidebar a')).toHaveCount(0)
    await page.getByTestId('sidebar-toggle').click()

    await expect(navigation.getByRole('button', { name: 'Knowledge', exact: true })).toHaveAttribute('aria-expanded', 'false')
    await expect(navigation.getByRole('link', { name: 'Diagnostics', exact: true })).toHaveAttribute('aria-current', 'page')
    await expect(navigation.locator('a[aria-current="page"]')).toHaveCount(1)
  })

  test('preserves #180 groups and #181 semantic navigation icons', async ({ page }) => {
    await clearSidebarPreference(page)
    const navigation = page.getByRole('navigation', { name: 'Primary' })
    await expect(navigation.getByRole('region', { name: 'Knowledge' })).toBeVisible()
    await expect(navigation.getByRole('region', { name: 'Capture' })).toBeVisible()
    await expect(navigation.getByRole('region', { name: 'Manage' })).toBeVisible()
    await expect(navigation.locator('svg[data-icon]')).toHaveCount(11)

    const expectedIcons = [
      ['Dashboard', 'dashboard'], ['Browse', 'browse'], ['Timeline', 'timeline'],
      ['Statistics', 'stats'], ['New LeLe', 'new'], ['Collection', 'collection'],
      ['Vault', 'vault'], ['Duplicates', 'duplicates'], ['System', 'system'],
      ['Diagnostics', 'diagnostics'], ['About', 'about'],
    ] as const
    for (const [label, icon] of expectedIcons) {
      await expect(navigation.getByRole('link', { name: label, exact: true }).locator('svg'))
        .toHaveAttribute('data-icon', icon)
    }
  })

  test('opens, filters, navigates, and restores focus through the command palette', async ({ page }) => {
    await page.goto('/app/#/')
    const trigger = page.getByTestId('command-palette-trigger')

    await trigger.click()
    const dialog = page.getByRole('dialog', { name: 'Search or commands' })
    await expect(dialog).toBeVisible()
    await expect(page).toHaveURL(/#\/$/)
    const input = dialog.getByPlaceholder('Filter commands…')
    await expect(input).toBeFocused()
    await input.fill('Diagnostics')
    await expect(dialog.getByRole('button', { name: 'Diagnostics', exact: true })).toBeVisible()
    await input.press('Enter')
    await expect(page).toHaveURL(/#\/settings$/)
    await expect(dialog).not.toBeVisible()
    await expect(trigger).toBeFocused()

    await page.keyboard.press('Control+k')
    await expect(dialog).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dialog).not.toBeVisible()
    await expect(trigger).toBeFocused()

    await page.keyboard.press('Meta+k')
    await expect(dialog).toBeVisible()
    await page.keyboard.press('Escape')
  })

  test('offers New LeLe as a command without restoring a permanent CTA', async ({ page }) => {
    await page.goto('/app/#/')
    await page.keyboard.press('Control+k')
    const dialog = page.getByRole('dialog', { name: 'Search or commands' })
    await dialog.getByPlaceholder('Filter commands…').fill('New LeLe')
    await dialog.getByRole('button', { name: 'New LeLe', exact: true }).click()
    await expect(page).toHaveURL(/#\/editor$/)
    await expect(page.getByTestId('new-lesson-cta')).toHaveCount(0)
  })

  test('maps Search LeLe to the maintained Browse route', async ({ page }) => {
    await page.goto('/app/#/')
    await page.keyboard.press('Control+k')
    const dialog = page.getByRole('dialog', { name: 'Search or commands' })
    await dialog.getByPlaceholder('Filter commands…').fill('Search LeLe')
    await dialog.getByRole('button', { name: 'Search LeLe', exact: true }).click()
    await expect(page).toHaveURL(/#\/browse$/)
  })

  test('keeps Help destinations bounded and internally routes Diagnostics and About', async ({ page }) => {
    await page.goto('/app/#/')
    await page.getByTestId('header-help-trigger').click()
    const help = page.locator('#header-help-menu')

    await expect(help.getByRole('link', { name: 'User guide' })).toHaveAttribute(
      'href',
      'https://github.com/gcomneno/lele-manager/blob/main/docs/gui-user-guide.md',
    )
    await expect(help.getByRole('link', { name: 'Report a problem' })).toHaveAttribute(
      'href',
      'https://github.com/gcomneno/lele-manager/issues/new?template=bug_report.yml',
    )
    await expect(help).toContainText('Ctrl K')

    await help.getByRole('button', { name: 'Diagnostics', exact: true }).click()
    await expect(page).toHaveURL(/#\/settings$/)

    await page.getByTestId('header-help-trigger').click()
    await page.locator('#header-help-menu').getByRole('button', { name: 'About', exact: true }).click()
    await expect(page).toHaveURL(/#\/about$/)
  })

  test('keeps palette commands and Help localized without changing route identities', async ({ page }) => {
    await page.goto('/app/#/')
    await page.getByLabel('Language').selectOption('it')
    await page.getByTestId('command-palette-trigger').click()
    const dialog = page.getByRole('dialog', { name: 'Cerca o comandi' })
    await dialog.getByPlaceholder('Filtra comandi…').fill('Nuova LeLe')
    await dialog.getByRole('button', { name: 'Nuova LeLe', exact: true }).click()
    await expect(page).toHaveURL(/#\/editor$/)

    await page.getByTestId('header-help-trigger').click()
    await expect(page.locator('#header-help-menu').getByRole('button', { name: 'Diagnostica', exact: true })).toBeVisible()
  })
})

test.describe('responsive shell recovery', () => {
  test('keeps the header toggle reachable and navigation recoverable without horizontal overflow on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await clearSidebarPreference(page)

    const toggle = page.getByTestId('sidebar-toggle')
    await expect(toggle).toBeVisible()
    await toggle.click()
    await expect(page.locator('#primary-sidebar')).toHaveCount(0)
    await expect(page.locator('#primary-sidebar a, #primary-sidebar button')).toHaveCount(0)
    await toggle.click()
    await expect(page.getByRole('navigation', { name: 'Primary' })).toBeVisible()

    const widths = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
    }))
    expect(widths.scroll).toBeLessThanOrEqual(widths.viewport)
  })
})
