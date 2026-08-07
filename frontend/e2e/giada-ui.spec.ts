import { expect, test } from '@playwright/test'

test('renders Browse with direct Giada UI primitives', async ({ page }) => {
  await page.setViewportSize({ width: 1800, height: 900 })
  await page.goto('/app/')

  const panel = page.locator('.giu-panel')
  await expect(panel).toHaveCount(1)
  await expect(
    panel.getByRole('heading', { name: 'Browse', exact: true }),
  ).toBeVisible()


  const fullWidthGeometry = await panel.evaluate((browsePanel) => {
    const content = browsePanel.closest('.content')

    if (!(content instanceof HTMLElement)) {
      throw new Error('Shell content container not found')
    }

    const contentBox = content.getBoundingClientRect()
    const panelBox = browsePanel.getBoundingClientRect()
    const contentStyle = getComputedStyle(content)
    const paddingLeft = Number.parseFloat(contentStyle.paddingLeft)
    const paddingRight = Number.parseFloat(contentStyle.paddingRight)

    return {
      leftGap:
        panelBox.left -
        (contentBox.left + paddingLeft),
      rightGap:
        contentBox.right -
        paddingRight -
        panelBox.right,
      usableWidth:
        contentBox.width -
        paddingLeft -
        paddingRight,
      panelWidth: panelBox.width,
    }
  })

  expect(Math.abs(fullWidthGeometry.leftGap)).toBeLessThanOrEqual(1)
  expect(Math.abs(fullWidthGeometry.rightGap)).toBeLessThanOrEqual(1)
  expect(
    Math.abs(
      fullWidthGeometry.panelWidth -
      fullWidthGeometry.usableWidth,
    ),
  ).toBeLessThanOrEqual(2)

  const buttons = panel.locator('button[data-giu-variant]')
  await expect(buttons).toHaveCount(4)

  for (let index = 0; index < 4; index += 1) {
    await expect(buttons.nth(index)).toHaveAttribute(
      'data-giu-size',
      'compact',
    )
  }
  await expect(buttons.nth(0)).toHaveAttribute(
    'data-giu-variant',
    'primary',
  )
  await expect(buttons.nth(1)).toHaveAttribute(
    'data-giu-variant',
    'secondary',
  )

  await expect(panel.locator('.giu-form-actions')).toBeVisible()
  await expect(panel.locator('.giu-field-label')).toHaveCount(6)

  const resultStatus = panel.getByRole('status')
  await expect(resultStatus).toBeVisible()
  await expect(resultStatus).toHaveText('4 results')
  await expect(resultStatus).toHaveCSS(
    'background-color',
    'rgba(0, 0, 0, 0)',
  )
})

test('System view fills the available content width', async ({ page }) => {
  await page.setViewportSize({ width: 1800, height: 900 })
  await page.goto('/app/#/ops')

  const ops = page.locator('.ops')
  await expect(ops).toBeVisible()

  const geometry = await ops.evaluate((opsElement) => {
    const content = opsElement.closest('.content')

    if (!(content instanceof HTMLElement)) {
      throw new Error('Shell content container not found')
    }

    const contentBox = content.getBoundingClientRect()
    const opsBox = opsElement.getBoundingClientRect()
    const style = getComputedStyle(content)
    const paddingLeft = Number.parseFloat(style.paddingLeft)
    const paddingRight = Number.parseFloat(style.paddingRight)

    return {
      leftGap: opsBox.left - (contentBox.left + paddingLeft),
      rightGap: contentBox.right - paddingRight - opsBox.right,
      usableWidth: contentBox.width - paddingLeft - paddingRight,
      opsWidth: opsBox.width,
    }
  })

  expect(Math.abs(geometry.leftGap)).toBeLessThanOrEqual(1)
  expect(Math.abs(geometry.rightGap)).toBeLessThanOrEqual(1)
  expect(
    Math.abs(geometry.opsWidth - geometry.usableWidth),
  ).toBeLessThanOrEqual(2)
})

test('renders Stats and Vault with Giada UI primitives', async ({
  page,
}) => {
  await page.goto('/app/#/stats')

  const statsPanel = page.getByRole('region', {
    name: 'Statistics',
    exact: true,
  })

  await expect(statsPanel).toBeVisible()
  await expect(statsPanel.locator('.giu-surface')).toHaveCount(5)

  await page.goto('/app/#/vault')

  const vaultPanel = page.getByRole('region', {
    name: 'Vault',
    exact: true,
  })

  await expect(vaultPanel).toBeVisible()
  await expect(
    vaultPanel.locator('.giu-form-actions'),
  ).toBeVisible()

  const vaultButtons = vaultPanel.locator(
    'button[data-giu-size="compact"]',
  )

  await expect(vaultButtons).toHaveCount(3)
  await expect(
    vaultPanel.locator(
      'button[data-giu-variant="primary"]',
    ),
  ).toHaveCount(1)
  await expect(
    vaultPanel.locator(
      'button[data-giu-variant="secondary"]',
    ),
  ).toHaveCount(2)
})

test('renders Detail, Editor, and duplicate controls with Giada UI', async ({
  page,
}) => {
  await page.goto('/app/#/')

  const firstCard = page.locator('.lesson-card').first()
  await expect(firstCard).toBeVisible({
    timeout: 15_000,
  })
  await firstCard.click()

  const detailPanel = page.locator(
    '.detail-layout > .giu-panel',
  )

  await expect(detailPanel).toBeVisible()

  const editButton = detailPanel.getByRole('button', {
    name: 'Edit',
    exact: true,
  })

  await expect(editButton).toHaveAttribute(
    'data-giu-variant',
    'secondary',
  )
  await expect(editButton).toHaveAttribute(
    'data-giu-size',
    'compact',
  )

  await editButton.click()

  const editorPanel = page.getByRole('region', {
    name: 'Edit LeLe',
    exact: true,
  })

  await expect(editorPanel).toBeVisible()
  await expect(
    editorPanel.locator('.giu-field-label'),
  ).toHaveCount(10)

  const similarityButton = editorPanel.getByRole('button', {
    name: 'Check similarity',
    exact: true,
  })

  await expect(similarityButton).toHaveAttribute(
    'data-giu-variant',
    'secondary',
  )
  await expect(similarityButton).toHaveAttribute(
    'data-giu-size',
    'compact',
  )

  const saveButton = editorPanel.getByRole('button', {
    name: 'Save to vault',
    exact: true,
  })

  await expect(saveButton).toHaveAttribute(
    'data-giu-variant',
    'primary',
  )
  await expect(saveButton).toHaveAttribute(
    'data-giu-size',
    'compact',
  )

  await page.goto('/app/#/duplicates')

  const duplicatesPanel = page.getByRole('region', {
    name: 'Duplicate review',
    exact: true,
  })

  await expect(duplicatesPanel).toBeVisible()
  await expect(
    duplicatesPanel.locator('.giu-field-label'),
  ).toHaveCount(3)
  await expect(
    duplicatesPanel.locator('.giu-form-actions'),
  ).toBeVisible()

  const reviewButton = duplicatesPanel.getByRole(
    'button',
    {
      name: 'Run review',
      exact: true,
    },
  )

  await expect(reviewButton).toHaveAttribute(
    'data-giu-variant',
    'primary',
  )
  await expect(reviewButton).toHaveAttribute(
    'data-giu-size',
    'compact',
  )
})
