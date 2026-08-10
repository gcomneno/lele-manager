import { expect, test } from '@playwright/test'

test.describe('LeLe mascot motion', () => {
  test('keeps the independent wandering cameo decorative and non-looping', async ({ page }) => {
    await page.goto('/app/#/')

    const cameo = page.getByTestId('lele-monkey-cameo')
    const character = page.getByTestId('lele-monkey-cameo-character')
    const balloon = page.getByTestId('lele-monkey-cameo-balloon')

    await expect(cameo).toHaveAttribute('aria-hidden', 'true')
    await expect(cameo).toHaveCSS('pointer-events', 'none')
    await expect(cameo).toHaveCSS('animation-name', /lele-cameo-path$/)
    await expect(cameo).toHaveCSS('animation-duration', '12s')
    await expect(cameo).toHaveCSS('animation-delay', '8s')
    await expect(cameo).toHaveCSS('animation-iteration-count', '1')
    await expect(character.locator('img')).toHaveCount(7)
    await expect(character.locator('img').nth(0)).toHaveAttribute(
      'src',
      '/app/brand/lele-cameo/01-enter.png',
    )
    await expect(character.locator('img').nth(6)).toHaveAttribute(
      'src',
      '/app/brand/lele-cameo/07-exit.png',
    )
    await expect(balloon).toHaveText('LeLe!!')
  })

  test('keeps the cameo off compact layouts and disables decorative motion when requested', async ({ page }) => {
    await page.setViewportSize({ width: 700, height: 700 })
    await page.goto('/app/#/')
    await expect(page.getByTestId('lele-monkey-cameo')).toHaveCSS('display', 'none')

    await page.emulateMedia({ reducedMotion: 'reduce' })
    await expect(page.getByTestId('lele-monkey-cameo')).toHaveCSS('display', 'none')
  })
})

test('keeps the GiadaWare signature tongue decorative and motion-safe', async ({ page }) => {
  await page.goto('/app/#/')

  const tongue = page.getByTestId('giadaware-signature-tongue')
  const thought = page.getByTestId('giadaware-signature-thought')
  const mascot = page.getByTestId('giadaware-signature-mascot')

  await expect(thought).toBeAttached()
  await expect(tongue).toHaveAttribute('aria-hidden', 'true')
  await expect(tongue).toHaveCSS('animation-name', /lele-signature-tongue$/)
  await expect(tongue).toHaveCSS('animation-duration', '31s')
  await expect(tongue).toHaveCSS('left', '18px')
  await expect(mascot).toHaveCSS('animation-name', /lele-signature-think$/)
  await expect(thought).toHaveCSS('animation-name', /lele-thought-bubble$/)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await expect(tongue).toHaveCSS('animation-name', 'none')
  await expect(tongue).toHaveCSS('opacity', '0')
  await expect(mascot).toHaveCSS('animation-name', 'none')
  await expect(thought).toHaveCSS('animation-name', 'none')
  await expect(thought).toHaveCSS('opacity', '0')
})
