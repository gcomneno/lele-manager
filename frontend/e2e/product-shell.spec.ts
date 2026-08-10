import { expect, test, type Locator, type Page } from '@playwright/test'

const navigationGroupsStorageKey = 'lele-manager.navigation-groups.v1'
const sidebarStorageKey = 'lele-manager.sidebar-visible.v1'

async function clearSidebarPreference(page: Page) {
  await page.goto('/app/#/')
  await page.evaluate((key) => window.localStorage.removeItem(key), sidebarStorageKey)
  await page.reload()
}

async function tabUntilFocused(
  page: Page,
  target: Locator,
  safetyBound: number,
) {
  for (let step = 0; step < safetyBound; step += 1) {
    if (await target.evaluate((element) => document.activeElement === element)) {
      return
    }

    await page.keyboard.press('Tab')
  }

  await expect(target).toBeFocused()
}

test.describe('product shell hierarchy', () => {
  test('keeps all navigation groups expanded by default with their destinations available', async ({ page }) => {
    await page.goto('/app/#/')

    const navigation = page.getByRole('navigation', { name: 'Primary' })
    for (const label of ['Knowledge', 'Capture', 'Manage']) {
      await expect(navigation.getByRole('region', { name: label })).toBeVisible()
      await expect(navigation.getByRole('button', { name: label, exact: true }))
        .toHaveAttribute('aria-expanded', 'true')
    }

    for (const label of [
      'Dashboard', 'Browse', 'Timeline', 'Statistics', 'New LeLe', 'Collection',
      'Vault', 'Duplicates', 'System', 'Diagnostics', 'About',
    ]) {
      await expect(navigation.getByRole('link', { name: label, exact: true })).toHaveCount(1)
    }
  })

  test('toggles independent inactive groups with native disclosure semantics', async ({ page }) => {
    await page.goto('/app/#/settings')

    const navigation = page.getByRole('navigation', { name: 'Primary' })
    const knowledge = navigation.getByRole('button', { name: 'Knowledge', exact: true })
    const capture = navigation.getByRole('button', { name: 'Capture', exact: true })
    const knowledgeLinks = page.locator('#navigation-group-knowledge')

    await expect(knowledge).toHaveAttribute('aria-controls', 'navigation-group-knowledge')
    await expect(knowledge).toHaveAttribute('aria-expanded', 'true')
    await expect(knowledge.locator('svg')).toHaveAttribute('aria-hidden', 'true')
    await knowledge.click()
    await expect(knowledge).toHaveAttribute('aria-expanded', 'false')
    await expect(knowledgeLinks).toBeHidden()
    await expect(knowledgeLinks.getByRole('link')).toHaveCount(0)
    await expect(capture).toHaveAttribute('aria-expanded', 'true')

    await knowledge.focus()
    await page.keyboard.press('Space')
    await expect(knowledge).toHaveAttribute('aria-expanded', 'true')
    await expect(knowledgeLinks).toBeVisible()
  })

  test('opens the active group for deep links and prevents hiding the current route', async ({ page }) => {
    await page.addInitScript((key) => window.localStorage.setItem(key, JSON.stringify({
      knowledge: true,
      capture: true,
      manage: false,
    })), navigationGroupsStorageKey)
    await page.goto('/app/#/settings')

    const navigation = page.getByRole('navigation', { name: 'Primary' })
    const manage = navigation.getByRole('button', { name: 'Manage', exact: true })
    const diagnostics = navigation.getByRole('link', { name: 'Diagnostics', exact: true })
    await expect(manage).toHaveAttribute('aria-expanded', 'true')
    await expect(diagnostics).toBeVisible()
    await expect(diagnostics).toHaveAttribute('aria-current', 'page')
    await expect(navigation.locator('a[aria-current="page"]')).toHaveCount(1)

    await manage.click()
    await expect(manage).toHaveAttribute('aria-expanded', 'true')
    await expect(diagnostics).toBeVisible()
  })

  test('opens a newly active group without changing unrelated preferences', async ({ page }) => {
    await page.goto('/app/#/browse')
    const navigation = page.getByRole('navigation', { name: 'Primary' })
    const manage = navigation.getByRole('button', { name: 'Manage', exact: true })

    await manage.click()
    await expect(manage).toHaveAttribute('aria-expanded', 'false')
    await navigation.getByRole('link', { name: 'New LeLe', exact: true }).click()

    await expect(navigation.getByRole('button', { name: 'Capture', exact: true }))
      .toHaveAttribute('aria-expanded', 'true')
    await expect(navigation.getByRole('link', { name: 'New LeLe', exact: true }))
      .toHaveAttribute('aria-current', 'page')
    await expect(manage).toHaveAttribute('aria-expanded', 'false')
  })

  test('persists disclosure state and safely falls back from malformed or obsolete group storage', async ({ page }) => {
    await page.goto('/app/#/settings')
    const knowledge = page.getByRole('button', { name: 'Knowledge', exact: true })
    await knowledge.click()
    await expect.poll(() => page.evaluate((key) => localStorage.getItem(key), navigationGroupsStorageKey))
      .toBe(JSON.stringify({ knowledge: false, capture: true, manage: true }))
    await page.reload()
    await expect(knowledge).toHaveAttribute('aria-expanded', 'false')

    await page.evaluate((key) => localStorage.setItem(key, '{not valid json'), navigationGroupsStorageKey)
    await page.reload()
    for (const label of ['Knowledge', 'Capture', 'Manage']) {
      await expect(page.getByRole('button', { name: label, exact: true })).toHaveAttribute('aria-expanded', 'true')
    }

    await page.evaluate((key) => localStorage.setItem(key, JSON.stringify({ obsolete: false })), navigationGroupsStorageKey)
    await page.reload()
    for (const label of ['Knowledge', 'Capture', 'Manage']) {
      await expect(page.getByRole('button', { name: label, exact: true })).toHaveAttribute('aria-expanded', 'true')
    }
  })

  test('keeps disclosure state when the locale changes without changing route identities', async ({ page }) => {
    await page.goto('/app/#/settings')
    await page.getByRole('button', { name: 'Knowledge', exact: true }).click()
    await page.getByLabel('Language').selectOption('it')

    await expect(page.getByRole('button', { name: 'Conoscenza', exact: true }))
      .toHaveAttribute('aria-expanded', 'false')
    await expect(page.getByRole('button', { name: 'Acquisizione', exact: true }))
      .toHaveAttribute('aria-expanded', 'true')
    await expect(page.getByRole('link', { name: 'Sistema', exact: true }))
      .toHaveAttribute('href', '#/ops')
  })
})

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
    await expect(toggle).toHaveAttribute('aria-controls', 'primary-sidebar')
    await expect(page.locator('#primary-sidebar')).toHaveCount(1)
    await expect(page.locator('#primary-sidebar')).toBeHidden()
    await expect(page.getByRole('navigation', { name: 'Primary' })).toHaveCount(0)
    await expect(page.getByRole('link', { name: 'Dashboard', exact: true })).toHaveCount(0)
    expect(await page.locator('#primary-sidebar a, #primary-sidebar button').evaluateAll(
      (elements) => elements.every((element) => (element as HTMLElement).offsetParent === null),
    )).toBe(true)
    await expect.poll(() => page.evaluate((key) => localStorage.getItem(key), sidebarStorageKey)).toBe('false')

    await page.reload()
    await expect(page.locator('#primary-sidebar')).toHaveCount(1)
    await expect(page.locator('#primary-sidebar')).toBeHidden()
    await page.getByTestId('sidebar-toggle').click()
    await expect(page.locator('#primary-sidebar')).toBeVisible()
    await expect.poll(() => page.evaluate((key) => localStorage.getItem(key), sidebarStorageKey)).toBe('true')

    await page.getByTestId('sidebar-toggle').focus()
    await page.keyboard.press('Enter')
    await expect(page.locator('#primary-sidebar')).toBeHidden()
    await page.keyboard.press('Space')
    await expect(page.locator('#primary-sidebar')).toBeVisible()
  })

  test('safely defaults from malformed visibility storage and retains it across locale changes', async ({ page }) => {
    await page.goto('/app/#/')
    await page.evaluate((key) => window.localStorage.setItem(key, '{invalid'), sidebarStorageKey)
    await page.reload()
    await expect(page.locator('#primary-sidebar')).toBeVisible()

    await page.evaluate((key) => window.localStorage.setItem(key, 'unexpected'), sidebarStorageKey)
    await page.reload()
    await expect(page.locator('#primary-sidebar')).toBeVisible()
    await page.evaluate((key) => window.localStorage.setItem(key, 'true'), sidebarStorageKey)
    await page.reload()
    await expect(page.locator('#primary-sidebar')).toBeVisible()
    await page.evaluate((key) => window.localStorage.setItem(key, 'false'), sidebarStorageKey)
    await page.reload()
    await expect(page.locator('#primary-sidebar')).toBeHidden()

    await page.getByLabel('Language').selectOption('it')
    await expect(page.getByTestId('sidebar-toggle')).toHaveAccessibleName('Mostra navigazione')
    await expect(page.locator('#primary-sidebar')).toBeHidden()

    await page.getByTestId('header-help-trigger').click()
    await page.locator('#header-help-menu').getByRole('button', { name: 'Diagnostica', exact: true }).click()
    await expect(page).toHaveURL(/#\/settings$/)
    await expect(page.locator('#primary-sidebar')).toBeHidden()
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
    await expect(page.locator('#primary-sidebar')).toBeHidden()
    await expect(page.getByRole('navigation', { name: 'Primary' })).toHaveCount(0)
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
      const svg = navigation.getByRole('link', { name: label, exact: true }).locator('svg')
      await expect(svg)
        .toHaveAttribute('data-icon', icon)
      await expect(svg).toHaveAttribute('aria-hidden', 'true')
    }
    await expect(navigation.getByRole('link', { name: 'Dashboard', exact: true }))
      .toHaveAttribute('aria-current', 'page')
    await expect(navigation.locator('a[aria-current="page"]')).toHaveCount(1)
  })

  test('uses deterministic local SVG navigation icons without emoji fallbacks', async ({ page }) => {
    await page.goto('/app/#/')
    const navigation = page.getByRole('navigation', { name: 'Primary' })

    await expect(navigation.locator('svg[data-icon]')).toHaveCount(11)
    for (const emoji of ['🏠', '🕒', '📊', '✨', '🗂️', '🧠', '🧪', '⚙️']) {
      await expect(navigation).not.toContainText(emoji)
    }
  })

  test('keeps semantic icon identities stable when localized', async ({ page }) => {
    await page.goto('/app/#/')
    await page.getByLabel('Language').selectOption('it')
    const navigation = page.getByRole('navigation', { name: 'Primary' })

    for (const [label, icon] of [
      ['Sistema', 'system'], ['Diagnostica', 'diagnostics'], ['Informazioni', 'about'],
    ]) {
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
  test('keeps the desktop sidebar pinned alongside the global header and content', async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 600 })
    await clearSidebarPreference(page)

    await expect(page.getByTestId('header-workspace')).toBeVisible()
    await expect(page.getByTestId('giadaware-signature')).toBeVisible()
    const signatureBox = await page.getByTestId('giadaware-signature').boundingBox()
    expect(signatureBox).not.toBeNull()
    if (signatureBox) {
      expect(signatureBox.y).toBeGreaterThanOrEqual(0)
      expect(signatureBox.y + signatureBox.height).toBeLessThanOrEqual(600)
    }
  })

  test('orders header, navigation, and main content on mobile and removes the sidebar reservation when hidden', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await clearSidebarPreference(page)

    const toggle = page.getByTestId('sidebar-toggle')
    const header = page.locator('header.global-header')
    const sidebar = page.locator('#primary-sidebar')
    const navigation = page.getByRole('navigation', { name: 'Primary' })
    const main = page.locator('main.main')
    await expect(toggle).toBeVisible()
    await expect(navigation).toBeVisible()
    for (const group of ['Knowledge', 'Capture', 'Manage']) {
      await expect(navigation.getByRole('region', { name: group })).toBeVisible()
    }
    for (const label of ['Browse', 'Timeline', 'Statistics', 'New LeLe', 'Collection', 'Vault', 'Duplicates', 'System', 'Diagnostics', 'About']) {
      await expect(navigation.getByRole('link', { name: label, exact: true })).toBeVisible()
    }

    const visibleBoxes = await Promise.all([
      header.boundingBox(),
      sidebar.boundingBox(),
      main.boundingBox(),
    ])
    const [headerBox, sidebarBox, mainBox] = visibleBoxes
    expect(headerBox).not.toBeNull()
    expect(sidebarBox).not.toBeNull()
    expect(mainBox).not.toBeNull()
    if (headerBox && sidebarBox && mainBox) {
      expect(headerBox.y + headerBox.height).toBeLessThanOrEqual(sidebarBox.y + 1)
      expect(sidebarBox.y + sidebarBox.height).toBeLessThanOrEqual(mainBox.y + 1)
    }

    await toggle.click()
    await expect(header).toBeVisible()
    await expect(sidebar).toBeHidden()
    await expect(navigation).toHaveCount(0)
    const hiddenBoxes = await Promise.all([header.boundingBox(), main.boundingBox()])
    const [hiddenHeaderBox, hiddenMainBox] = hiddenBoxes
    expect(hiddenHeaderBox).not.toBeNull()
    expect(hiddenMainBox).not.toBeNull()
    if (hiddenHeaderBox && hiddenMainBox) {
      expect(hiddenMainBox.y - (hiddenHeaderBox.y + hiddenHeaderBox.height)).toBeLessThanOrEqual(1)
    }

    const hiddenWidths = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
    }))
    expect(hiddenWidths.scroll).toBeLessThanOrEqual(hiddenWidths.viewport)

    await toggle.click()
    await expect(navigation).toBeVisible()
    await expect(navigation.getByRole('link', { name: 'Dashboard', exact: true }))
      .toHaveAttribute('aria-current', 'page')
    const restoredBoxes = await Promise.all([sidebar.boundingBox(), main.boundingBox()])
    const [restoredSidebarBox, restoredMainBox] = restoredBoxes
    expect(restoredSidebarBox).not.toBeNull()
    expect(restoredMainBox).not.toBeNull()
    if (restoredSidebarBox && restoredMainBox) {
      expect(restoredSidebarBox.y + restoredSidebarBox.height).toBeLessThanOrEqual(restoredMainBox.y + 1)
    }

    const widths = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
    }))
    expect(widths.scroll).toBeLessThanOrEqual(widths.viewport)
  })

  test('keeps grouped navigation keyboard reachable on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await clearSidebarPreference(page)

    const system = page.getByRole('link', { name: 'System', exact: true })
    await tabUntilFocused(page, system, 36)
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/#\/ops$/)
    await expect(page.getByRole('heading', { name: 'Status and maintenance' })).toBeVisible()
  })
})
