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
      ['Dashboard', '#/'],
      ['Browse', '#/browse'],
      ['Timeline', '#/timeline'],
      ['Statistics', '#/stats'],
      ['New LeLe', '#/editor'],
      ['Collection', '#/tritalele'],
      ['Vault', '#/vault'],
      ['Duplicates', '#/duplicates'],
      ['System', '#/ops'],
      ['Diagnostics', '#/settings'],
      ['About', '#/about'],
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
      ['Dashboard', '#/'],
      ['Esplora', '#/browse'],
      ['Cronologia', '#/timeline'],
      ['Statistiche', '#/stats'],
      ['Nuova LeLe', '#/editor'],
      ['Raccolta', '#/tritalele'],
      ['Vault', '#/vault'],
      ['Duplicati', '#/duplicates'],
      ['Sistema', '#/ops'],
      ['Diagnostica', '#/settings'],
      ['Informazioni', '#/about'],
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

  test('localizes the first route tranche in both maintained languages', async ({
    page,
  }) => {
    await resetLocale(page)
    await page.goto('/app/#/browse')

    const navigation = page.getByRole('navigation')

    const browsePanel = page.getByRole('region', {
      name: 'Browse',
      exact: true,
    })

    await expect(browsePanel).toBeVisible()
    await expect(
      browsePanel.getByRole('button', {
        name: 'Search',
        exact: true,
      }),
    ).toBeVisible()

    await navigation
      .getByRole('link', {
        name: 'Statistics',
        exact: true,
      })
      .click()

    await expect(
      page.getByRole('region', {
        name: 'Statistics',
        exact: true,
      }),
    ).toBeVisible()

    await navigation
      .getByRole('link', {
        name: 'Timeline',
        exact: true,
      })
      .click()

    await expect(
      page.getByRole('heading', {
        name: 'Timeline',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByRole('button', {
        name: 'Month',
        exact: true,
      }),
    ).toBeVisible()

    await navigation
      .getByRole('link', {
        name: 'Vault',
        exact: true,
      })
      .click()

    const vaultPanel = page.getByRole('region', {
      name: 'Vault',
      exact: true,
    })

    await expect(vaultPanel).toBeVisible()
    await expect(
      vaultPanel.getByRole('button', {
        name: 'Refresh',
        exact: true,
      }),
    ).toBeVisible()

    await navigation
      .getByRole('link', {
        name: 'New LeLe',
        exact: true,
      })
      .click()

    const editorPanel = page.getByRole('region', {
      name: 'New LeLe',
      exact: true,
    })

    await expect(editorPanel).toBeVisible()
    await expect(
      editorPanel.getByRole('button', {
        name: 'Save to vault',
        exact: true,
      }),
    ).toBeVisible()

    await page
      .getByLabel('Language')
      .selectOption('it')

    await expect(
      page.getByRole('region', {
        name: 'Nuova LeLe',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByRole('button', {
        name: 'Salva nel vault',
        exact: true,
      }),
    ).toBeVisible()

    await navigation
      .getByRole('link', {
        name: 'Statistiche',
        exact: true,
      })
      .click()

    await expect(
      page.getByRole('region', {
        name: 'Statistiche',
        exact: true,
      }),
    ).toBeVisible()

    await navigation
      .getByRole('link', {
        name: 'Cronologia',
        exact: true,
      })
      .click()

    await expect(
      page.getByRole('heading', {
        name: 'Cronologia',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByRole('button', {
        name: 'Mese',
        exact: true,
      }),
    ).toBeVisible()

    await navigation
      .getByRole('link', {
        name: 'Esplora',
        exact: true,
      })
      .click()

    const italianBrowse = page.getByRole('region', {
      name: 'Esplora',
      exact: true,
    })

    await expect(italianBrowse).toBeVisible()
    await expect(
      italianBrowse.getByRole('button', {
        name: 'Cerca',
        exact: true,
      }),
    ).toBeVisible()
  })

  test('localizes Detail and shared similarity presentation immediately', async ({
    page,
  }) => {
    await resetLocale(page)
    await page.goto('/app/#/browse')

    const lessonId = 'e2e/python-lesson'
    const lessonCard = page
      .getByTestId(`lesson-result-${lessonId}`)
      .locator('.lesson-card')

    await expect(lessonCard).toBeVisible({
      timeout: 15_000,
    })

    await lessonCard.click()
    await expect(page).toHaveURL(
      new RegExp(`#\\/lesson\\/${encodeURIComponent(lessonId)}$`),
    )

    const detailPanel = page.getByRole('region', {
      name: lessonId,
      exact: true,
    })

    await expect(
      detailPanel.getByRole('button', {
        name: 'Modify',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByRole('heading', {
        name: 'Why is it similar?',
        exact: true,
      }),
    ).toBeVisible()

    await page
      .getByLabel('Language')
      .selectOption('it')

    await expect(
      detailPanel.getByRole('button', {
        name: 'Modifica',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByRole('heading', {
        name: 'Perché è simile?',
        exact: true,
      }),
    ).toBeVisible()
  })


  test('localizes Duplicates and System immediately', async ({
    page,
  }) => {
    await resetLocale(page)

    const navigation = page.getByRole('navigation')

    await navigation
      .getByRole('link', {
        name: 'Duplicates',
        exact: true,
      })
      .click()

    const duplicatesPanel = page.getByRole('region', {
      name: 'Duplicate review',
      exact: true,
    })

    await expect(duplicatesPanel).toBeVisible()

    await expect(
      duplicatesPanel.getByRole('button', {
        name: 'Run review',
        exact: true,
      }),
    ).toBeVisible()

    await navigation
      .getByRole('link', {
        name: 'System',
        exact: true,
      })
      .click()

    await expect(
      page.getByRole('heading', {
        name: 'Status and maintenance',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByRole('button', {
        name: 'Update search model',
        exact: true,
      }),
    ).toBeVisible()

    await page
      .getByLabel('Language')
      .selectOption('it')

    await expect(
      page.getByRole('heading', {
        name: 'Stato e manutenzione',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByRole('button', {
        name: 'Aggiorna il modello di ricerca',
        exact: true,
      }),
    ).toBeVisible()

    await navigation
      .getByRole('link', {
        name: 'Duplicati',
        exact: true,
      })
      .click()

    const italianDuplicates = page.getByRole('region', {
      name: 'Revisione duplicati',
      exact: true,
    })

    await expect(italianDuplicates).toBeVisible()

    await expect(
      italianDuplicates.getByRole('button', {
        name: 'Avvia controllo',
        exact: true,
      }),
    ).toBeVisible()
  })


  test('localizes TritaLeLe without changing workflow input', async ({
    page,
  }) => {
    await resetLocale(page)

    const navigation = page.getByRole('navigation')

    await navigation
      .getByRole('link', {
        name: 'Collection',
        exact: true,
      })
      .click()

    await expect(
      page.getByRole('heading', {
        name: 'Collect new LeLe',
        exact: true,
      }),
    ).toBeVisible()

    const ingestion = page.getByRole('region', {
      name: 'Collect new LeLe',
      exact: true,
    })

    const sourceName = ingestion.getByLabel('Source name')
    const sourceText = ingestion.getByLabel('Source text')

    await sourceName.fill('locale-preserved.txt')
    await sourceText.fill(
      'Workflow input must remain unchanged while locale changes.',
    )

    const hashBefore = await page.evaluate(
      () => window.location.hash,
    )

    await page
      .getByLabel('Language')
      .selectOption('it')

    await expect(
      page.getByRole('heading', {
        name: 'Raccogli nuove LeLe',
        exact: true,
      }),
    ).toBeVisible()

    const italianIngestion = page.getByRole('region', {
      name: 'Raccogli nuove LeLe',
      exact: true,
    })

    await expect(
      italianIngestion.getByLabel('Nome della fonte'),
    ).toHaveValue('locale-preserved.txt')

    await expect(
      italianIngestion.getByLabel('Testo sorgente'),
    ).toHaveValue(
      'Workflow input must remain unchanged while locale changes.',
    )

    await expect(
      page.getByRole('button', {
        name: 'Crea anteprima',
        exact: true,
      }),
    ).toBeVisible()

    expect(
      await page.evaluate(() => window.location.hash),
    ).toBe(hashBefore)

    await page
      .getByLabel('Lingua')
      .selectOption('en')

    await expect(sourceName).toHaveValue(
      'locale-preserved.txt',
    )

    await expect(sourceText).toHaveValue(
      'Workflow input must remain unchanged while locale changes.',
    )
  })


  test('presents healthy services with consistent status indicators', async ({
    page,
  }) => {
    await resetLocale(page)
    await page.goto('/app/#/browse')

    const healthBar = page.locator('.health-bar')

    await expect(healthBar).toBeVisible()

    await expect(
      healthBar.locator('[aria-label="API: ok"]'),
    ).toBeVisible()

    await expect(
      healthBar.locator('[aria-label="dataset: ok"]'),
    ).toBeVisible()

    await expect(
      healthBar.locator('[aria-label="model: ok"]'),
    ).toBeVisible()

    await expect(
      healthBar.locator('.dot.ok'),
    ).toHaveCount(3)

    await expect(healthBar).not.toContainText(
      'dataset ok',
    )

    await expect(healthBar).not.toContainText(
      'model ok',
    )

    await page
      .getByLabel('Language')
      .selectOption('it')

    await expect(
      healthBar.locator('[aria-label="API: ok"]'),
    ).toBeVisible()

    await expect(
      healthBar.locator('[aria-label="dataset: ok"]'),
    ).toBeVisible()

    await expect(
      healthBar.locator('[aria-label="modello: ok"]'),
    ).toBeVisible()

    await expect(
      healthBar.locator('.dot.ok'),
    ).toHaveCount(3)

    await expect(healthBar).not.toContainText(
      'modello ok',
    )
  })


  test('localizes the explicit editor similarity action', async ({
    page,
  }) => {
    await resetLocale(page)
    await page.goto('/app/#/editor')

    await expect(
      page.getByRole('button', {
        name: 'Check similarity',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.locator('.similar-panel'),
    ).toHaveCount(0)

    const advancedOptions = page.locator('.editor-pane details')
    await expect(advancedOptions.locator('summary')).toHaveText(
      'Advanced options',
    )
    await advancedOptions.locator('summary').click()
    await expect(
      page.getByLabel('Maximum results'),
    ).toBeVisible()
    await expect(
      page.getByLabel('Minimum similarity'),
    ).toBeVisible()

    await page
      .getByLabel('Language')
      .selectOption('it')

    await expect(
      page.getByRole('button', {
        name: 'Verifica similarità',
        exact: true,
      }),
    ).toBeVisible()

    await expect(advancedOptions.locator('summary')).toHaveText(
      'Opzioni avanzate',
    )
    await expect(
      page.getByLabel('Risultati massimi'),
    ).toBeVisible()
    await expect(
      page.getByLabel('Similarità minima'),
    ).toBeVisible()

    await expect(
      page.locator('.similar-panel'),
    ).toHaveCount(0)
  })

})
