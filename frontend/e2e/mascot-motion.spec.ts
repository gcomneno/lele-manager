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
    await expect(cameo).toHaveCSS('animation-duration', '13.8s')
    await expect(cameo).toHaveCSS('animation-delay', '8s')
    await expect(cameo).toHaveCSS('animation-iteration-count', '1')
    await expect(character.locator('img')).toHaveCount(7)

    const enter = character.locator('.lele-cameo-enter')
    const scratch = character.locator('.lele-cameo-scratch')
    await expect(enter).toHaveCSS('animation-duration', '13.8s')
    await expect(enter).toHaveCSS('animation-name', /lele-cameo-enter-frame$/)
    await expect(scratch).toHaveCSS('animation-duration', '13.8s')
    await expect(scratch).toHaveCSS('animation-name', /lele-cameo-scratch-frame$/)

    const holds = await character.evaluate((stage) => {
      const visibleHoldMs = (selector: string) => {
        const element = stage.querySelector<HTMLElement>(selector)
        if (!element) throw new Error(`Missing cameo frame: ${selector}`)

        const animation = element.getAnimations()[0]
        if (!animation || !(animation.effect instanceof KeyframeEffect)) {
          throw new Error(`Missing keyframe animation: ${selector}`)
        }

        const duration = Number(animation.effect.getTiming().duration)
        const visibleOffsets = animation.effect
          .getKeyframes()
          .filter((frame) => Number(frame.opacity) === 1 && frame.offset !== null)
          .map((frame) => Number(frame.offset))

        return duration * (Math.max(...visibleOffsets) - Math.min(...visibleOffsets))
      }

      return {
        enter: visibleHoldMs('.lele-cameo-enter'),
        scratch: visibleHoldMs('.lele-cameo-scratch'),
      }
    })

    expect(holds.enter).toBeGreaterThanOrEqual(2950)
    expect(holds.enter).toBeLessThanOrEqual(3050)
    expect(holds.scratch).toBeGreaterThanOrEqual(3050)
    expect(holds.scratch).toBeLessThanOrEqual(3200)
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
