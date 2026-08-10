import { expect, test } from '@playwright/test'

const navigationGroupsStorageKey =
  'lele-manager.navigation-groups.v1'

test.describe('product shell hierarchy', () => {
  test('groups navigation into Knowledge, Capture, and Manage', async ({
    page,
  }) => {
    await page.goto('/app/#/')

    const navigation = page.getByRole('navigation', {
      name: 'Primary',
    })

    await expect(
      navigation.getByRole('region', { name: 'Knowledge' }),
    ).toBeVisible()
    await expect(
      navigation.getByRole('region', { name: 'Capture' }),
    ).toBeVisible()
    await expect(
      navigation.getByRole('region', { name: 'Manage' }),
    ).toBeVisible()

    for (const label of ['Knowledge', 'Capture', 'Manage']) {
      await expect(
        navigation.getByRole('button', { name: label, exact: true }),
      ).toHaveAttribute('aria-expanded', 'true')
    }

    for (const label of [
      'Dashboard',
      'Browse',
      'Timeline',
      'Statistics',
      'New LeLe',
      'Collection',
      'Vault',
      'Duplicates',
      'System',
      'Diagnostics',
      'About',
    ]) {
      await expect(
        navigation.getByRole('link', { name: label }),
      ).toHaveCount(1)
    }
  })

  test('toggles independent inactive groups with accessible disclosure semantics', async ({
    page,
  }) => {
    await page.goto('/app/#/settings')

    const navigation = page.getByRole('navigation', {
      name: 'Primary',
    })
    const knowledge = navigation.getByRole('button', {
      name: 'Knowledge',
      exact: true,
    })
    const capture = navigation.getByRole('button', {
      name: 'Capture',
      exact: true,
    })
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

  test('opens the active group for deep links and stale stored state', async ({
    page,
  }) => {
    await page.addInitScript((key) => {
      window.localStorage.setItem(key, JSON.stringify({
        knowledge: true,
        capture: true,
        manage: false,
      }))
    }, navigationGroupsStorageKey)
    await page.goto('/app/#/settings')

    const navigation = page.getByRole('navigation', {
      name: 'Primary',
    })

    await expect(
      navigation.getByRole('button', { name: 'Manage', exact: true }),
    ).toHaveAttribute('aria-expanded', 'true')
    await expect(
      navigation.getByRole('link', { name: 'Diagnostics', exact: true }),
    ).toBeVisible()
    await expect(
      navigation.getByRole('link', { name: 'Diagnostics', exact: true }),
    ).toHaveAttribute('aria-current', 'page')
    await expect(navigation.locator('a[aria-current="page"]')).toHaveCount(1)

    await navigation.getByRole('button', {
      name: 'Manage',
      exact: true,
    }).click()
    await expect(
      navigation.getByRole('button', { name: 'Manage', exact: true }),
    ).toHaveAttribute('aria-expanded', 'true')
    await expect(
      navigation.getByRole('link', { name: 'Diagnostics', exact: true }),
    ).toBeVisible()
  })

  test('opens a newly active group without changing unrelated preferences', async ({
    page,
  }) => {
    await page.goto('/app/#/browse')

    const navigation = page.getByRole('navigation', {
      name: 'Primary',
    })
    const manage = navigation.getByRole('button', {
      name: 'Manage',
      exact: true,
    })

    await manage.click()
    await expect(manage).toHaveAttribute('aria-expanded', 'false')

    await navigation.getByRole('link', {
      name: 'New LeLe',
      exact: true,
    }).click()

    await expect(
      navigation.getByRole('button', { name: 'Capture', exact: true }),
    ).toHaveAttribute('aria-expanded', 'true')
    await expect(
      navigation.getByRole('link', { name: 'New LeLe', exact: true }),
    ).toHaveAttribute('aria-current', 'page')
    await expect(manage).toHaveAttribute('aria-expanded', 'false')
  })

  test('persists valid disclosure state and safely ignores malformed storage', async ({
    page,
  }) => {
    await page.goto('/app/#/settings')

    const knowledge = page.getByRole('button', {
      name: 'Knowledge',
      exact: true,
    })
    await knowledge.click()
    await expect(knowledge).toHaveAttribute('aria-expanded', 'false')
    await expect.poll(async () => page.evaluate((key) => (
      window.localStorage.getItem(key)
    ), navigationGroupsStorageKey)).toBe(JSON.stringify({
      knowledge: false,
      capture: true,
      manage: true,
    }))

    await page.reload()
    await expect.poll(async () => page.evaluate((key) => (
      window.localStorage.getItem(key)
    ), navigationGroupsStorageKey)).toBe(JSON.stringify({
      knowledge: false,
      capture: true,
      manage: true,
    }))
    await expect(knowledge).toHaveAttribute('aria-expanded', 'false')

    await page.evaluate((key) => {
      window.localStorage.setItem(key, '{not valid json')
    }, navigationGroupsStorageKey)
    await page.reload()

    for (const label of ['Knowledge', 'Capture', 'Manage']) {
      await expect(
        page.getByRole('button', { name: label, exact: true }),
      ).toHaveAttribute('aria-expanded', 'true')
    }

    await page.evaluate((key) => {
      window.localStorage.setItem(key, JSON.stringify({ obsolete: false }))
    }, navigationGroupsStorageKey)
    await page.reload()

    for (const label of ['Knowledge', 'Capture', 'Manage']) {
      await expect(
        page.getByRole('button', { name: label, exact: true }),
      ).toHaveAttribute('aria-expanded', 'true')
    }
  })

  test('uses deterministic local SVG navigation icons', async ({
    page,
  }) => {
    await page.goto('/app/#/')

    const navigation = page.getByRole('navigation', {
      name: 'Primary',
    })

    await expect(navigation.locator('svg[data-icon]')).toHaveCount(11)

    for (const emoji of [
      '🏠',
      '🕒',
      '📊',
      '✨',
      '🗂️',
      '🧠',
      '🧪',
      '⚙️',
    ]) {
      await expect(navigation).not.toContainText(emoji)
    }
  })

  test('maps every navigation destination to its distinct semantic icon', async ({
    page,
  }) => {
    await page.goto('/app/#/browse')

    const navigation = page.getByRole('navigation', {
      name: 'Primary',
    })
    const expectedIcons = [
      ['Dashboard', 'dashboard'],
      ['Browse', 'browse'],
      ['Timeline', 'timeline'],
      ['Statistics', 'stats'],
      ['New LeLe', 'new'],
      ['Collection', 'collection'],
      ['Vault', 'vault'],
      ['Duplicates', 'duplicates'],
      ['System', 'system'],
      ['Diagnostics', 'diagnostics'],
      ['About', 'about'],
    ] as const

    for (const [label, icon] of expectedIcons) {
      const link = navigation.getByRole('link', {
        name: label,
        exact: true,
      })
      const svg = link.locator('svg')

      await expect(svg).toHaveAttribute('data-icon', icon)
      await expect(svg).toHaveAttribute('aria-hidden', 'true')
    }

    expect(new Set(expectedIcons.map(([, icon]) => icon)).size).toBe(
      expectedIcons.length,
    )
    await expect(
      navigation.getByRole('link', { name: 'Browse', exact: true }),
    ).toHaveAttribute('aria-current', 'page')
    await expect(
      navigation.getByRole('link', { name: 'System', exact: true }),
    ).not.toHaveAttribute('aria-current')
    await expect(
      navigation.locator('a[aria-current="page"]'),
    ).toHaveCount(1)
  })

  test('keeps semantic icon identities stable when localized', async ({
    page,
  }) => {
    await page.goto('/app/#/')

    await page.getByLabel('Language').selectOption('it')

    const navigation = page.getByRole('navigation', {
      name: 'Primary',
    })
    const expectedIcons = [
      ['Sistema', 'system'],
      ['Diagnostica', 'diagnostics'],
      ['Informazioni', 'about'],
    ] as const

    for (const [label, icon] of expectedIcons) {
      await expect(
        navigation.getByRole('link', { name: label, exact: true }).locator('svg'),
      ).toHaveAttribute('data-icon', icon)
    }
  })

  test('shows bounded runtime and workspace context', async ({
    page,
  }) => {
    await page.goto('/app/#/')

    const context = page.getByTestId('shell-context')
    const version = page.getByTestId('shell-version')
    const workspace = page.getByTestId('shell-workspace')

    await expect(context).toBeVisible()
    await expect(version).toHaveText(/\S+/)
    await expect(workspace).toHaveText(/\S+/)

    const workspaceText = await workspace.textContent()

    expect(workspaceText).not.toContain('/')
    expect(workspaceText).not.toContain('\\')
  })

  test('localizes navigation group labels without changing routes', async ({
    page,
  }) => {
    await page.goto('/app/#/')

    await page
      .getByLabel('Language')
      .selectOption('it')

    const navigation = page.getByRole('navigation', {
      name: 'Primary',
    })

    await expect(
      navigation.getByRole('region', { name: 'Conoscenza' }),
    ).toBeVisible()
    await expect(
      navigation.getByRole('region', { name: 'Acquisizione' }),
    ).toBeVisible()
    await expect(
      navigation.getByRole('region', { name: 'Gestione' }),
    ).toBeVisible()

    await expect(
      navigation.getByRole('button', { name: 'Conoscenza', exact: true }),
    ).toHaveAttribute('aria-expanded', 'true')

    await expect(
      navigation.getByRole('link', { name: 'Dashboard' }),
    ).toHaveAttribute('href', '#/')
    await expect(
      navigation.getByRole('link', { name: 'Esplora' }),
    ).toHaveAttribute('href', '#/browse')
    await expect(
      navigation.getByRole('link', { name: 'Cronologia' }),
    ).toHaveAttribute('href', '#/timeline')
    await expect(
      navigation.getByRole('link', { name: 'Sistema' }),
    ).toHaveAttribute('href', '#/ops')
  })

  test('keeps disclosure state when the locale changes', async ({ page }) => {
    await page.goto('/app/#/settings')

    const knowledge = page.getByRole('button', {
      name: 'Knowledge',
      exact: true,
    })
    await knowledge.click()
    await expect(knowledge).toHaveAttribute('aria-expanded', 'false')

    await page.getByLabel('Language').selectOption('it')

    await expect(
      page.getByRole('button', { name: 'Conoscenza', exact: true }),
    ).toHaveAttribute('aria-expanded', 'false')
    await expect(
      page.getByRole('button', { name: 'Acquisizione', exact: true }),
    ).toHaveAttribute('aria-expanded', 'true')
  })
})

test.describe('product shell responsive layouts', () => {
  test('keeps grouped navigation usable on a narrow desktop', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 900, height: 600 })
    await page.goto('/app/#/')

    const navigation = page.getByRole('navigation', {
      name: 'Primary',
    })

    await expect(navigation).toBeVisible()
    await expect(
      navigation.getByRole('region', { name: 'Knowledge' }),
    ).toBeVisible()
    await expect(
      navigation.getByRole('link', { name: 'Browse' }),
    ).toBeVisible()
    await expect(
      navigation.getByRole('link', { name: 'System' }),
    ).toBeVisible()

    await expect(page.getByTestId('shell-context')).toBeVisible()
    await expect(
      page.getByTestId('giadaware-signature'),
    ).toBeVisible()

    const signatureBox = await page
      .getByTestId('giadaware-signature')
      .boundingBox()

    expect(signatureBox).not.toBeNull()

    if (signatureBox) {
      expect(signatureBox.y).toBeGreaterThanOrEqual(0)
      expect(signatureBox.y + signatureBox.height)
        .toBeLessThanOrEqual(600)
    }
  })

  test('keeps navigation deterministic on mobile width', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/app/#/')

    const navigation = page.getByRole('navigation', {
      name: 'Primary',
    })

    await expect(navigation).toBeVisible()

    for (const group of [
      'Knowledge',
      'Capture',
      'Manage',
    ]) {
      await expect(
        navigation.getByRole('region', { name: group }),
      ).toBeVisible()
    }

    for (const label of [
      'Browse',
      'Timeline',
      'Statistics',
      'New LeLe',
      'Collection',
      'Vault',
      'Duplicates',
      'System',
      'Diagnostics',
      'About',
    ]) {
      await expect(
        navigation.getByRole('link', { name: label }),
      ).toBeVisible()
    }

    await expect(
      page.getByTestId('shell-context'),
    ).toBeHidden()
    await expect(
      page.getByTestId('giadaware-signature'),
    ).toBeHidden()

    const viewportWidth = await page.evaluate(
      () => document.documentElement.clientWidth,
    )
    const scrollWidth = await page.evaluate(
      () => document.documentElement.scrollWidth,
    )

    expect(scrollWidth).toBeLessThanOrEqual(viewportWidth)
  })

  test('keeps mobile navigation keyboard reachable', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/app/#/')

    const system = page.getByRole('link', {
      name: 'System',
    })

    for (let step = 0; step < 24; step += 1) {
      if (
        await system.evaluate(
          (element) => document.activeElement === element,
        )
      ) {
        break
      }

      await page.keyboard.press('Tab')
    }

    await expect(system).toBeFocused()

    await page.keyboard.press('Enter')

    await expect(page).toHaveURL(/#\/ops$/)
    await expect(
      page.getByRole('heading', {
        name: 'Status and maintenance',
      }),
    ).toBeVisible()
  })
})
