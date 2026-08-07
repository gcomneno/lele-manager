import { expect, test } from '@playwright/test'

const storageKey = 'lele-manager.locale'

async function resetLocale(
  page: import('@playwright/test').Page,
) {
  await page.goto('/app/')
  await page.evaluate((key) => {
    window.localStorage.removeItem(key)
  }, storageKey)
  await page.reload()
}

test.describe('GUI localization', () => {
  test('starts in English with no explicit locale', async ({
    page,
  }) => {
    await resetLocale(page)

    await expect(
      page.getByTestId('brand-tagline'),
    ).toHaveText(
      'Your local space for your “Lessons Learned”',
    )

    await expect(
      page.getByRole('navigation').getByRole('link', {
        name: 'Browse',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByTestId('new-lesson-cta'),
    ).toHaveAccessibleName('New LeLe')

    await expect(
      page.getByLabel('Language'),
    ).toHaveValue('en')
  })

  test('switches immediately to Italian and persists it', async ({
    page,
  }) => {
    await resetLocale(page)

    await page.evaluate(() => {
      ;(window as Window & {
        __localeReloadMarker?: string
      }).__localeReloadMarker = 'alive'
    })

    await page
      .getByLabel('Language')
      .selectOption('it')

    await expect(
      page.getByTestId('brand-tagline'),
    ).toHaveText(
      "Lo spazio locale per le tue 'Lessons Learned'",
    )

    await expect(
      page.getByRole('navigation').getByRole('link', {
        name: 'Esplora',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByTestId('new-lesson-cta'),
    ).toHaveAccessibleName('Nuova LeLe')

    expect(
      await page.evaluate(() => {
        return (
          window as Window & {
            __localeReloadMarker?: string
          }
        ).__localeReloadMarker
      }),
    ).toBe('alive')

    await page.reload()

    await expect(
      page.getByLabel('Lingua'),
    ).toHaveValue('it')

    await expect(
      page.getByRole('navigation').getByRole('link', {
        name: 'Esplora',
        exact: true,
      }),
    ).toBeVisible()
  })

  test('switches back to English', async ({ page }) => {
    await resetLocale(page)

    await page
      .getByLabel('Language')
      .selectOption('it')

    await page
      .getByLabel('Lingua')
      .selectOption('en')

    await expect(
      page.getByLabel('Language'),
    ).toHaveValue('en')

    await expect(
      page.getByTestId('new-lesson-cta'),
    ).toHaveAccessibleName('New LeLe')

    await page.reload()

    await expect(
      page.getByLabel('Language'),
    ).toHaveValue('en')
  })

  test('falls back safely from an unsupported stored locale', async ({
    page,
  }) => {
    await page.goto('/app/')

    await page.evaluate((key) => {
      window.localStorage.setItem(
        key,
        'xx-invalid-locale',
      )
    }, storageKey)

    await page.reload()

    await expect(
      page.getByLabel('Language'),
    ).toHaveValue('en')

    await expect(
      page.getByRole('navigation').getByRole('link', {
        name: 'Browse',
        exact: true,
      }),
    ).toBeVisible()
  })

  test('keeps navigation hashes locale-independent', async ({
    page,
  }) => {
    await resetLocale(page)

    const expected = [
      ['Browse', '#/'],
      ['Timeline', '#/timeline'],
      ['Statistics', '#/stats'],
      ['New LeLe', '#/editor'],
      ['Collection', '#/tritalele'],
      ['Vault', '#/vault'],
      ['Duplicates', '#/duplicates'],
      ['System', '#/ops'],
    ] as const

    const navigation = page.getByRole('navigation')

    for (const [label, hash] of expected) {
      await expect(
        navigation.getByRole('link', {
          name: label,
          exact: true,
        }),
      ).toHaveAttribute('href', hash)
    }

    await page
      .getByLabel('Language')
      .selectOption('it')

    const italianExpected = [
      ['Esplora', '#/'],
      ['Cronologia', '#/timeline'],
      ['Statistiche', '#/stats'],
      ['Nuova LeLe', '#/editor'],
      ['Raccolta', '#/tritalele'],
      ['Vault', '#/vault'],
      ['Duplicati', '#/duplicates'],
      ['Sistema', '#/ops'],
    ] as const

    for (const [label, hash] of italianExpected) {
      await expect(
        navigation.getByRole('link', {
          name: label,
          exact: true,
        }),
      ).toHaveAttribute('href', hash)
    }
  })
})
