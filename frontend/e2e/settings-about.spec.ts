import { expect, test, type Page } from '@playwright/test'
import { readFile } from 'node:fs/promises'

const settingsFixture = {
  version: '1.10.1',
  health: {
    status: 'ok',
    has_data: true,
    has_model: false,
  },
  paths: [
    {
      key: 'vault',
      path: '/fixture/LeLeVault',
      role: 'authoritative_user_data',
      exists: true,
      kind: 'directory',
      provenance: {
        kind: 'product_default',
        variable: null,
        deprecated: false,
      },
    },
    {
      key: 'application_data',
      path: '/fixture/data/lele-manager',
      role: 'persistent_application_state',
      exists: true,
      kind: 'directory',
      provenance: {
        kind: 'configuration_override',
        variable: 'LELE_DATA_DIR',
        deprecated: false,
      },
    },
    {
      key: 'lesson_projection',
      path: '/fixture/data/lele-manager/lessons.jsonl',
      role: 'derived_rebuildable_artifact',
      exists: true,
      kind: 'file',
      provenance: {
        kind: 'configuration_override',
        variable: 'LELE_DATA_DIR',
        deprecated: false,
      },
    },
    {
      key: 'candidate_staging',
      path: '/fixture/data/lele-manager/candidates.json',
      role: 'persistent_application_state',
      exists: false,
      kind: 'file',
      provenance: {
        kind: 'configuration_override',
        variable: 'LELE_DATA_DIR',
        deprecated: false,
      },
    },
    {
      key: 'cache',
      path: '/fixture/cache/lele-manager',
      role: 'cache_temporary_state',
      exists: true,
      kind: 'directory',
      provenance: {
        kind: 'platform_default',
        variable: null,
        deprecated: false,
      },
    },
    {
      key: 'topic_model',
      path: '/fixture/legacy/topic_model.joblib',
      role: 'derived_rebuildable_artifact',
      exists: false,
      kind: 'file',
      provenance: {
        kind: 'legacy_override',
        variable: 'LELE_MODEL_PATH',
        deprecated: true,
      },
    },
  ],
}

const diagnosticsFixture = {
  product_name: 'LeLe Manager',
  version: '1.10.1',
  python_version: '3.12.0',
  platform_system: 'Linux',
  platform_release: 'fixture',
  health: settingsFixture.health,
  paths: settingsFixture.paths,
}

async function mockSettings(page: Page): Promise<void> {
  await page.route('**/settings/runtime', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(settingsFixture),
    }),
  )
}

test.describe('Diagnostics and About', () => {
  test('renders support status first and keeps runtime paths secondary', async ({
    page,
  }) => {
    await mockSettings(page)
    await page.goto('/app/#/settings')

    await expect(
      page.getByRole('heading', {
        name: 'Diagnostics',
        exact: true,
      }),
    ).toBeVisible()

    const headings = await page.getByRole('heading').allTextContents()
    expect(headings.indexOf('Status')).toBeLessThan(headings.indexOf('Diagnostic package'))
    expect(headings.indexOf('Diagnostic package')).toBeLessThan(headings.indexOf('Request support'))
    await expect(page.getByTestId('technical-details')).not.toHaveAttribute('open', '')
    await page.getByTestId('technical-details').locator('summary').click()
    await expect(page.getByText('Authoritative user data')).toBeVisible()
    await expect(
      page.getByText('Persistent application state'),
    ).toHaveCount(2)
    await expect(
      page.getByText('Derived / rebuildable artifact'),
    ).toHaveCount(2)
    await expect(
      page.getByText('Cache / temporary state'),
    ).toBeVisible()

    await expect(
      page.getByText('Missing', { exact: true }),
    ).toHaveCount(2)

    await expect(
      page.getByText('LELE_MODEL_PATH', { exact: true }),
    ).toBeVisible()
    await expect(
      page.locator('dd').filter({
        hasText: 'LELE_MODEL_PATH',
      }),
    ).toContainText('deprecated')
  })

  test('does not request diagnostics until the user explicitly asks', async ({
    page,
  }) => {
    await mockSettings(page)

    let diagnosticRequests = 0

    await page.route('**/diagnostics/preview', (route) => {
      diagnosticRequests += 1
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(diagnosticsFixture),
      })
    })

    await page.goto('/app/#/settings')

    await expect(
      page.getByRole('button', {
        name: 'Generate preview',
        exact: true,
      }),
    ).toBeVisible()

    await page.waitForTimeout(300)
    expect(diagnosticRequests).toBe(0)
    await expect(page.getByTestId('diagnostic-preview')).toHaveCount(0)

    await page.getByRole('button', {
      name: 'Generate preview',
      exact: true,
    }).click()

    await expect(page.getByTestId('diagnostic-preview')).toBeVisible()
    expect(diagnosticRequests).toBe(1)
  })

  test('uses Diagnostics terminology in Italian navigation and page content', async ({ page }) => {
    await mockSettings(page)
    await page.goto('/app/#/settings')
    await page.getByLabel('Language').selectOption('it')

    await expect(page.getByRole('link', { name: 'Diagnostica', exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Diagnostica', exact: true })).toBeVisible()
    await expect(page.getByText('Impostazioni', { exact: true })).toHaveCount(0)
  })

  test('opens the maintained support form without generating diagnostics', async ({ page }) => {
    await mockSettings(page)
    let diagnosticRequests = 0
    await page.route('**/diagnostics/preview', (route) => {
      diagnosticRequests += 1
      return route.fulfill({ status: 200, body: JSON.stringify(diagnosticsFixture) })
    })

    await page.goto('/app/#/settings')
    const support = page.getByRole('link', { name: 'Request support', exact: true })
    await expect(support).toHaveAttribute(
      'href',
      'https://github.com/gcomneno/lele-manager/issues/new?template=bug_report.yml',
    )
    await expect(support).toHaveAttribute('target', '_blank')
    expect(diagnosticRequests).toBe(0)
    await expect(page.getByText(/Generating a preview first is recommended/)).toBeVisible()

    await page.getByRole('button', { name: 'Generate preview', exact: true }).click()
    await expect(page.getByText('lele-manager-diagnostics-1.10.1.json')).toBeVisible()
    expect(diagnosticRequests).toBe(1)
  })

  test('copies and exports exactly the JSON displayed in the diagnostic preview', async ({
    page,
  }) => {
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'clipboard', {
        configurable: true,
        value: {
          writeText: async (text: string) => localStorage.setItem('clipboard', text),
        },
      })
    })
    await mockSettings(page)

    await page.route('**/diagnostics/preview', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(diagnosticsFixture),
      }),
    )

    await page.goto('/app/#/settings')

    await expect(page.getByRole('button', { name: 'Copy JSON', exact: true })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Download JSON', exact: true })).toBeDisabled()

    await page.getByRole('button', {
      name: 'Generate preview',
      exact: true,
    }).click()

    const preview = page.getByTestId('diagnostic-preview').locator('pre')
    await expect(preview).toBeVisible()

    const previewText = await preview.textContent()
    expect(previewText).toBe(JSON.stringify(diagnosticsFixture, null, 2))

    await page.getByRole('button', { name: 'Copy JSON', exact: true }).click()
    expect(await page.evaluate(() => localStorage.getItem('clipboard'))).toBe(previewText)

    const downloadPromise = page.waitForEvent('download')

    await page.getByRole('button', {
        name: 'Download JSON',
      exact: true,
    }).click()

    const download = await downloadPromise
    expect(download.suggestedFilename()).toBe(
      'lele-manager-diagnostics-1.10.1.json',
    )

    const downloadPath = await download.path()
    expect(downloadPath).not.toBeNull()

    const saved = await readFile(downloadPath!, 'utf-8')
    expect(saved).toBe(previewText)
  })

  test('shows bounded About identity and support links', async ({ page }) => {
    await page.route('**/about', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          product_name: 'LeLe Manager',
          version: '1.10.1',
          tagline: 'Your local-first lessons learned workspace',
          attribution: 'GiadaWare',
          license_id: 'MIT',
          license_summary:
            'Open-source software distributed under the MIT License.',
          license_url: '/app/LICENSE',
          local_first_statement:
            'LeLe Manager itself introduces no account, telemetry, cloud storage, or remote knowledge service.',
          repository_url: 'https://github.com/gcomneno/lele-manager',
          issue_tracker_url: 'https://github.com/gcomneno/lele-manager/issues',
          releases_url: 'https://github.com/gcomneno/lele-manager/releases',
          changelog_url:
            'https://github.com/gcomneno/lele-manager/blob/main/CHANGELOG.md',
          documentation_url:
            'https://github.com/gcomneno/lele-manager/blob/main/docs/gui-user-guide.md',
          python_version: '3.12.0',
          platform_system: 'Linux',
          platform_release: 'fixture',
        }),
      }),
    )

    await page.goto('/app/#/about')

    await expect(
      page.getByRole('heading', {
        name: 'About',
        exact: true,
      }),
    ).toBeVisible()
    await expect(
      page.getByRole('heading', {
        name: 'LeLe Manager',
        exact: true,
      }),
    ).toBeVisible()
    await expect(page.getByText('MIT', { exact: true })).toBeVisible()
    await expect(page.getByText('GiadaWare', { exact: true })).toBeVisible()
    await expect(
      page.getByText(/no account, telemetry, cloud storage/),
    ).toBeVisible()

    await expect(
      page.getByRole('link', {
        name: 'Full license',
        exact: true,
      }),
    ).toHaveAttribute('href', '/app/LICENSE')

    await expect(
      page.getByRole('link', {
        name: 'Repository',
        exact: true,
      }),
    ).toHaveAttribute(
      'href',
      'https://github.com/gcomneno/lele-manager',
    )

    await expect(
      page.getByRole('link', {
        name: 'Changelog',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByRole('link', {
        name: 'Documentation',
        exact: true,
      }),
    ).toBeVisible()
  })
})
