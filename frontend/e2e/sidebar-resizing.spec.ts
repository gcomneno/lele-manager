import { expect, test, type Page } from '@playwright/test'

const widthKey = 'lele-manager.sidebar-width.v1'
const handle = (page: Page) => page.getByRole('separator', { name: 'Resize navigation' })

async function expectWidth(page: Page, width: number) {
  await expect(handle(page)).toHaveAttribute('aria-valuenow', String(width))
  await expect.poll(async () => (await page.locator('#primary-sidebar').boundingBox())?.width).toBe(width)
  await expect.poll(async () => (await page.locator('main.main').boundingBox())?.x).toBe(width)
}

async function startDrag(page: Page) {
  const box = await handle(page).boundingBox()
  expect(box).not.toBeNull()
  await page.mouse.move(box!.x + box!.width / 2, 200)
  await page.mouse.down()
}

test.beforeEach(async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/app/#/')
})

test('drags horizontally, prevents selection, releases outside the handle, and persists across routes and reloads', async ({ page }) => {
  await expectWidth(page, 220)
  await expect(handle(page)).toHaveAttribute('aria-orientation', 'vertical')
  await expect(handle(page)).toHaveAttribute('aria-controls', 'primary-sidebar')
  await startDrag(page)
  await page.mouse.move(330, 400, { steps: 8 })
  await expectWidth(page, 330)
  expect(await page.locator('main.main').evaluate((el) => getComputedStyle(el).userSelect)).toBe('none')
  expect(await page.evaluate(() => window.getSelection()?.toString())).toBe('')
  await page.mouse.up()
  await page.mouse.move(500, 450)
  await expectWidth(page, 330)
  expect(await page.locator('main.main').evaluate((el) => getComputedStyle(el).userSelect)).not.toBe('none')
  await expect.poll(() => page.evaluate((key) => localStorage.getItem(key), widthKey)).toBe('330')

  for (const route of ['browse', 'settings', 'about', '']) {
    await page.goto(`/app/#/${route}`)
    await expectWidth(page, 330)
    await expect.poll(async () => (await page.locator('main.main').boundingBox())?.width).toBe(950)
  }
  await page.reload()
  await expectWidth(page, 330)
})

test('clamps pointer movement to both bounds', async ({ page }) => {
  await expect(handle(page)).toHaveAttribute('aria-valuemin', '220')
  await expect(handle(page)).toHaveAttribute('aria-valuemax', '400')
  await startDrag(page)
  await page.mouse.move(650, 200)
  await expectWidth(page, 400)
  await page.mouse.move(20, 200)
  await expectWidth(page, 220)
  await page.mouse.up()
  await page.reload()
  await expectWidth(page, 220)
})

test('is keyboard reachable and supports arrows, Home, End, and bounds', async ({ page }) => {
  await page.getByRole('link', { name: 'About', exact: true }).focus()
  await page.keyboard.press('Tab')
  await expect(handle(page)).toBeFocused()
  await page.keyboard.press('ArrowRight')
  await expectWidth(page, 230)
  await page.keyboard.press('ArrowLeft')
  await expectWidth(page, 220)
  await page.keyboard.press('ArrowLeft')
  await expectWidth(page, 220)
  await page.keyboard.press('End')
  await expectWidth(page, 400)
  await page.keyboard.press('ArrowRight')
  await expectWidth(page, 400)
  await page.keyboard.press('Home')
  await expectWidth(page, 220)
  await page.keyboard.press('ArrowRight')
  await page.reload()
  await expectWidth(page, 230)
  await page.getByLabel('Language').selectOption('it')
  await expect(page.getByRole('separator', { name: 'Ridimensiona navigazione' })).toHaveAttribute('aria-valuenow', '230')
})

test('validates persisted types and clamps finite numeric values', async ({ page }) => {
  for (const [stored, expected] of [
    ['{invalid', 220], ['null', 220], ['"320"', 220], ['true', 220],
    ['{}', 220], ['[]', 220], ['1e999', 220], ['-100', 220],
    ['900', 400], ['310.4', 310], ['350', 350],
  ] as const) {
    await page.evaluate(([key, value]) => localStorage.setItem(key, value), [widthKey, stored])
    await page.reload()
    await expectWidth(page, expected)
  }
})

for (const reason of ['cancel', 'capture loss', 'blur', 'hide', 'mobile'] as const) {
  test(`cleans up drag state and listeners on ${reason}`, async ({ page }) => {
    await startDrag(page)
    await page.mouse.move(300, 200)
    await expectWidth(page, 300)
    if (reason === 'cancel') {
      await page.evaluate(() => window.dispatchEvent(new PointerEvent('pointercancel', { pointerId: 1 })))
    } else if (reason === 'capture loss') {
      await handle(page).evaluate((el) => el.releasePointerCapture(1))
      // The browser processes pending capture changes on the next pointer event.
      await page.mouse.move(300, 210)
    } else if (reason === 'blur') {
      await page.evaluate(() => window.dispatchEvent(new Event('blur')))
    } else if (reason === 'hide') {
      await page.getByTestId('sidebar-toggle').evaluate((el) => (el as HTMLElement).click())
    } else {
      await page.setViewportSize({ width: 390, height: 844 })
    }
    await expect(page.locator('.shell')).not.toHaveClass(/resizing-sidebar/)
    await page.mouse.move(370, 250)
    await page.mouse.up()
    if (reason === 'hide') await page.getByTestId('sidebar-toggle').click()
    if (reason === 'mobile') await page.setViewportSize({ width: 1280, height: 800 })
    await expectWidth(page, 300)
    await startDrag(page)
    await page.mouse.move(320, 200)
    await page.mouse.up()
    await expectWidth(page, 320)
  })
}

test('preserves width and group preferences through hiding and mobile layout', async ({ page }) => {
  await page.goto('/app/#/settings')
  await page.getByRole('button', { name: 'Knowledge', exact: true }).click()
  await handle(page).focus()
  await page.keyboard.press('End')
  await page.getByTestId('sidebar-toggle').click()
  await expect(handle(page)).toHaveCount(0)
  await expect.poll(async () => (await page.locator('main.main').boundingBox())?.x).toBe(0)
  await page.reload()
  await expect(page.locator('#primary-sidebar')).toBeHidden()
  await page.getByTestId('sidebar-toggle').click()
  await expectWidth(page, 400)
  await expect(page.getByRole('button', { name: 'Knowledge', exact: true })).toHaveAttribute('aria-expanded', 'false')
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(handle(page)).toHaveCount(0)
  await expect.poll(async () => (await page.locator('#primary-sidebar').boundingBox())?.width).toBe(390)
  await expect.poll(async () => (await page.locator('main.main').boundingBox())?.x).toBe(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390)
  await page.setViewportSize({ width: 1280, height: 800 })
  await expectWidth(page, 400)
})

test('resizing still works when local storage is unavailable', async ({ page }) => {
  await page.addInitScript(() => {
    Storage.prototype.getItem = () => { throw new Error('Storage unavailable') }
    Storage.prototype.setItem = () => { throw new Error('Storage unavailable') }
  })
  await page.reload()
  await expectWidth(page, 220)
  await handle(page).focus()
  await page.keyboard.press('ArrowRight')
  await expectWidth(page, 230)
  await startDrag(page)
  await page.mouse.move(300, 200)
  await page.mouse.up()
  await expectWidth(page, 300)
})
