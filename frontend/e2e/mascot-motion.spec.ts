import { expect, test } from '@playwright/test'

test.describe('LeLe monkey motion', () => {
  test('keeps motion restrained and scoped to the New LeLe mascot', async ({
    page,
  }) => {
    await page.goto('/app/#/')

    const action = page.getByTestId('new-lesson-cta')
    const face = page.getByTestId('lele-monkey-motion')
    const image = face.locator('img')
    const signatureMascot = page.getByTestId(
      'giadaware-signature-mascot',
    )
    const signatureThought = page.getByTestId(
      'giadaware-signature-thought',
    )

    await expect(action).toHaveAccessibleName('New LeLe')
    await expect(action.getByText('+ New')).toBeVisible()
    await expect(action.getByText('LeLe')).toBeVisible()

    await expect(face).toHaveCSS(
      'animation-name',
      /lele-monkey-idle$/,
    )
    await expect(face).toHaveCSS('animation-duration', '18s')

    await expect(signatureMascot).toHaveCSS(
      'animation-name',
      /lele-signature-think$/,
    )
    await expect(signatureThought).toHaveCSS(
      'animation-name',
      /lele-thought-bubble$/,
    )

    await action.hover()

    await expect(face).toHaveCSS(
      'animation-play-state',
      'paused',
    )
    await expect(image).toHaveCSS(
      'animation-name',
      /lele-monkey-react$/,
    )
    await expect(image).toHaveCSS(
      'animation-iteration-count',
      '2',
    )
  })

  test('reacts to keyboard focus without changing CTA semantics', async ({
    page,
  }) => {
    await page.goto('/app/#/')

    const action = page.getByTestId('new-lesson-cta')
    const image = page
      .getByTestId('lele-monkey-motion')
      .locator('img')

    for (let step = 0; step < 16; step += 1) {
      if (
        await action.evaluate(
          (element) => document.activeElement === element,
        )
      ) {
        break
      }

      await page.keyboard.press('Tab')
    }

    await expect(action).toBeFocused()
    await expect(action).toHaveAccessibleName('New LeLe')
    await expect(image).toHaveCSS(
      'animation-name',
      /lele-monkey-react$/,
    )
    await expect(image).toHaveCSS(
      'animation-iteration-count',
      '2',
    )
  })

  test('runs one decorative wandering cameo without looping', async ({
    page,
  }) => {
    await page.goto('/app/#/')

    const cameo = page.getByTestId('lele-monkey-cameo')
    const character = page.getByTestId(
      'lele-monkey-cameo-character',
    )
    const balloon = page.getByTestId(
      'lele-monkey-cameo-balloon',
    )

    await expect(cameo).toHaveAttribute('aria-hidden', 'true')
    await expect(cameo).toHaveCSS('pointer-events', 'none')
    await expect(cameo).toHaveCSS(
      'animation-name',
      /lele-cameo-path$/,
    )
    await expect(cameo).toHaveCSS(
      'animation-duration',
      '12s',
    )
    await expect(cameo).toHaveCSS('animation-delay', '8s')
    await expect(cameo).toHaveCSS(
      'animation-iteration-count',
      '1',
    )

    await expect(character.locator('img')).toHaveCount(7)
    await expect(
      character.locator('img').nth(0),
    ).toHaveAttribute(
      'src',
      '/app/brand/lele-cameo/01-enter.png',
    )
    await expect(
      character.locator('img').nth(6),
    ).toHaveAttribute(
      'src',
      '/app/brand/lele-cameo/07-exit.png',
    )
    await expect(balloon).toHaveText('LeLe!!')
    await expect(balloon).toHaveCSS(
      'animation-name',
      /lele-cameo-balloon$/,
    )
  })

  test('keeps the wandering cameo off compact layouts', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 700, height: 700 })
    await page.goto('/app/#/')

    await expect(
      page.getByTestId('lele-monkey-cameo'),
    ).toHaveCSS('display', 'none')
  })

  test('disables non-essential mascot motion for reduced motion', async ({
    page,
  }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/app/#/')

    const action = page.getByTestId('new-lesson-cta')
    const face = page.getByTestId('lele-monkey-motion')
    const image = face.locator('img')
    const signatureMascot = page.getByTestId(
      'giadaware-signature-mascot',
    )
    const signatureThought = page.getByTestId(
      'giadaware-signature-thought',
    )
    const cameo = page.getByTestId('lele-monkey-cameo')

    await expect(face).toHaveCSS('animation-name', 'none')
    await expect(signatureMascot).toHaveCSS(
      'animation-name',
      'none',
    )
    await expect(signatureThought).toHaveCSS(
      'animation-name',
      'none',
    )
    await expect(signatureThought).toHaveCSS('opacity', '0')
    await expect(cameo).toHaveCSS('display', 'none')

    await action.hover()

    await expect(image).toHaveCSS('animation-name', 'none')
    await expect(action).toHaveAccessibleName('New LeLe')
  })
})


test('keeps the GiadaWare signature tongue decorative and motion-safe', async ({
  page,
}) => {
  await page.goto('/app/#/')

  const tongue = page.getByTestId('giadaware-signature-tongue')
  const thought = page.getByTestId('giadaware-signature-thought')

  await expect(thought).toBeAttached()
  await expect(tongue).toBeAttached()
  await expect(tongue).toHaveAttribute('aria-hidden', 'true')
  await expect(tongue).toHaveCSS(
    'animation-name',
    /lele-signature-tongue$/,
  )
  await expect(tongue).toHaveCSS('animation-duration', '31s')

  await page.emulateMedia({ reducedMotion: 'reduce' })

  await expect(tongue).toHaveCSS('animation-name', 'none')
  await expect(tongue).toHaveCSS('opacity', '0')
})


test('gives the Vault safe the same two-step reaction without changing navigation semantics', async ({
  page,
}) => {
  await page.goto('/app/#/')

  const vaultLink = page
    .getByRole('navigation')
    .getByRole('link', {
      name: 'Vault',
      exact: true,
    })

  const monkey = page.getByTestId('vault-monkey-icon')

  await expect(vaultLink).toHaveAccessibleName('Vault')
  await expect(vaultLink).toHaveAttribute('href', '#/vault')
  await expect(monkey).toBeVisible()
  await expect(monkey).toHaveAttribute('aria-hidden', 'true')

  await vaultLink.hover()

  await expect(monkey).toHaveCSS(
    'animation-name',
    /lele-monkey-react$/,
  )
  await expect(monkey).toHaveCSS(
    'animation-iteration-count',
    '2',
  )

  await vaultLink.focus()

  await expect(vaultLink).toBeFocused()
  await expect(monkey).toHaveCSS(
    'animation-name',
    /lele-monkey-react$/,
  )
  await expect(monkey).toHaveCSS(
    'animation-iteration-count',
    '2',
  )

  await page.emulateMedia({ reducedMotion: 'reduce' })
  await vaultLink.hover()

  await expect(monkey).toHaveCSS('animation-name', 'none')
})
