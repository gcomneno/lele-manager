import { expect, test } from '@playwright/test'

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

  test('uses deterministic local SVG navigation icons', async ({
    page,
  }) => {
    await page.goto('/app/#/')

    const navigation = page.getByRole('navigation', {
      name: 'Primary',
    })

    await expect(navigation.locator('svg')).toHaveCount(11)

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
