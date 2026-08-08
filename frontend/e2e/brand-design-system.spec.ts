import { expect, test } from '@playwright/test'

test.describe('brand foundation', () => {
  test('shows the packaged mark and consistent core control states', async ({ page }) => {
    await page.goto('/app/#/')

    const brand = page.getByRole('link', { name: 'LeLe Manager, browse' })
    await expect(brand).toBeVisible()
    await expect(brand.locator('img')).toHaveAttribute('src', '/app/brand/lele-manager-mark.svg')
    const browsePanel = page.getByRole('region', {
      name: 'Browse',
      exact: true,
    })
    const searchButton = browsePanel.getByRole('button', {
      name: 'Search',
      exact: true,
    })

    await expect(searchButton).toHaveAttribute(
      'data-giu-variant',
      'primary',
    )
    await expect(searchButton).toHaveAttribute(
      'data-giu-size',
      'compact',
    )
    await expect(
      page.getByPlaceholder('pytest, git, pandas…'),
    ).toBeVisible()
    await expect(browsePanel).toBeVisible()
  })

  test('uses default English product labels while preserving navigation hashes', async ({ page }) => {
    await page.goto('/app/#/')

    const navigation = [
      ['Browse', '#/'],
      ['Timeline', '#/timeline'],
      ['Statistics', '#/stats'],
      ['New LeLe', '#/editor'],
      ['Collection', '#/tritalele'],
      ['Vault', '#/vault'],
      ['Duplicates', '#/duplicates'],
      ['System', '#/ops'],
    ] as const

    const primaryNavigation = page.getByRole('navigation')

    for (const [label, hash] of navigation) {
      const navigationLink = primaryNavigation.getByRole('link', {
        name: label,
        exact: true,
      })

      await expect(navigationLink).toHaveCount(1)
      await expect(navigationLink).toHaveAttribute('href', hash)
    }
  })

  test('makes keyboard focus visible on navigation and controls', async ({ page }) => {
    await page.goto('/app/#/')

    const timeline = page.getByRole('link', { name: 'Timeline' })
    await timeline.focus()
    await expect(timeline).toBeFocused()
    await expect(timeline).toHaveCSS('box-shadow', /rgb/)

    const query = page.getByPlaceholder('pytest, git, pandas…')
    await query.focus()
    await expect(query).toBeFocused()
    await expect(query).toHaveCSS('box-shadow', /rgb/)
  })
})

test('shows the GiadaWare product signature without crowding the product brand', async ({ page }) => {
  await page.goto('/app/')

  await expect(page.getByTestId('brand-tagline')).toHaveText(
    'Your local space for your “Lessons Learned”',
  )

  const signature = page.getByTestId('giadaware-signature')
  await expect(signature).toBeVisible()
  await expect(signature.getByText('GiadaWare™')).toBeVisible()
  await expect(signature.getByText('Open-source software')).toBeVisible()
  await expect(signature.locator('img')).toHaveAttribute(
    'src',
    '/app/brand/lele-cameo/05-walk-right-a.png',
  )
})


test('pins the maker signature to the desktop viewport across routes', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 600 })
  await page.goto('/app/')

  const signature = page.getByTestId('giadaware-signature')
  const title = page.locator('.brand strong')
  const tagline = page.getByTestId('brand-tagline')

  await expect(signature).toBeVisible()
  await expect(tagline).toBeVisible()

  const titleBox = await title.boundingBox()
  const taglineBox = await tagline.boundingBox()

  expect(titleBox).not.toBeNull()
  expect(taglineBox).not.toBeNull()

  if (titleBox && taglineBox) {
    expect(taglineBox.y).toBeGreaterThanOrEqual(
      titleBox.y + titleBox.height,
    )
  }

  const expectSignatureInsideViewport = async () => {
    const box = await signature.boundingBox()

    expect(box).not.toBeNull()

    if (box) {
      expect(box.y).toBeGreaterThanOrEqual(0)
      expect(box.y + box.height).toBeLessThanOrEqual(600)
    }
  }

  await expectSignatureInsideViewport()

  await page.getByRole('link', { name: 'Timeline' }).click()
  await expect(
    page.getByRole('heading', { name: 'Timeline' }),
  ).toBeVisible()
  await expect(signature).toBeVisible()
  await expectSignatureInsideViewport()

  await page.getByRole('link', {
    name: 'Browse',
    exact: true,
  }).click()
  await expect(
    page.getByRole('heading', { name: 'Browse' }),
  ).toBeVisible()
  await expect(signature).toBeVisible()
  await expectSignatureInsideViewport()

  await page.setViewportSize({ width: 800, height: 600 })
  await expect(signature).toBeHidden()
})


test('keeps browse filter controls clear of the right edge', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/app/')

  const grid = page.getByTestId('browse-filter-grid')
  await expect(grid).toBeVisible()

  const geometry = await grid.evaluate((element) => {
    const gridBox = element.getBoundingClientRect()
    const parentBox = element.parentElement?.getBoundingClientRect()

    const controls = Array.from(
      element.querySelectorAll('input, select'),
    ).map((control) => control.getBoundingClientRect())

    return {
      rightGap: parentBox
        ? parentBox.right - gridBox.right
        : 0,
      controlsInside: controls.every(
        (control) => control.right <= gridBox.right + 0.5,
      ),
    }
  })

  expect(geometry.rightGap).toBeGreaterThanOrEqual(16)
  expect(geometry.controlsInside).toBe(true)
})


test('presents the new lesson action with the LeLe monkey balloon', async ({ page }) => {
  await page.goto('/app/')

  const action = page.getByTestId('new-lesson-cta')

  await expect(action).toBeVisible()
  await expect(action).toHaveAccessibleName('New LeLe')
  await expect(action.getByText('+ New')).toBeVisible()
  await expect(action.getByText('LeLe')).toBeVisible()
  await expect(action.locator('img')).toHaveAttribute(
    'src',
    '/app/brand/lele-cameo/05-walk-right-a.png',
  )
})
