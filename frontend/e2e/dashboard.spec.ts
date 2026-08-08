import { expect, test, type Page } from '@playwright/test'

interface DashboardFixture {
  health_status: string
  vault_exists: boolean
  vault_markdown_files: number | null
  projection_exists: boolean
  model_exists: boolean
  stats: {
    n_lessons: number
    n_topics: number
    n_unique_tags: number
    avg_text_length: number
    avg_importance: number | null
    top_tags: { tag: string; count: number }[]
    by_topic: { topic: string; count: number }[]
  } | null
  candidates: {
    total: number
    staged: number
    in_review: number
    rejected: number
    approved: number
  } | null
}

const baseSummary: DashboardFixture = {
  health_status: 'ok',
  vault_exists: true,
  vault_markdown_files: 4,
  projection_exists: true,
  model_exists: true,
  stats: {
    n_lessons: 4,
    n_topics: 2,
    n_unique_tags: 3,
    avg_text_length: 120,
    avg_importance: 3.5,
    top_tags: [],
    by_topic: [],
  },
  candidates: {
    total: 3,
    staged: 1,
    in_review: 1,
    rejected: 0,
    approved: 1,
  },
}

async function mockDashboard(
  page: Page,
  summary: DashboardFixture,
): Promise<void> {
  await page.route('**/dashboard/summary', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(summary),
    }),
  )
}

test.describe('product dashboard', () => {
  test('opens at the root route and keeps Browse explicit', async ({
    page,
  }) => {
    await page.goto('/app/#/')

    await expect(
      page.getByRole('heading', {
        name: 'Dashboard',
        exact: true,
      }),
    ).toBeVisible()

    const navigation = page.getByRole('navigation', {
      name: 'Primary',
    })

    await expect(
      navigation.getByRole('link', {
        name: 'Dashboard',
        exact: true,
      }),
    ).toHaveAttribute('href', '#/')

    await expect(
      navigation.getByRole('link', {
        name: 'Browse',
        exact: true,
      }),
    ).toHaveAttribute('href', '#/browse')

    await navigation
      .getByRole('link', {
        name: 'Browse',
        exact: true,
      })
      .click()

    await expect(page).toHaveURL(/#\/browse$/)
    await expect(
      page.getByRole('heading', {
        name: 'Browse',
        exact: true,
      }),
    ).toBeVisible()
  })

  test('renders bounded workspace state without passive operations', async ({
    page,
  }) => {
    const forbiddenRequests: string[] = []

    page.on('request', (request) => {
      const url = new URL(request.url())

      if (
        [
          '/duplicates',
          '/vault/doctor',
          '/vault/import',
          '/ops/refresh',
          '/train/topic',
        ].some((path) => url.pathname.startsWith(path))
      ) {
        forbiddenRequests.push(
          `${request.method()} ${url.pathname}`,
        )
      }
    })

    await page.goto('/app/#/')

    await expect(
      page.getByRole('region', {
        name: 'Workspace readiness',
      }),
    ).toBeVisible()

    await expect(
      page.getByRole('region', {
        name: 'Workspace summary',
      }),
    ).toBeVisible()

    expect(forbiddenRequests).toEqual([])
  })

  test('shows a deterministic loading state', async ({ page }) => {
    await page.route('**/dashboard/summary', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 500))
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(baseSummary),
      })
    })

    await page.goto('/app/#/')

    await expect(
      page.getByText('Loading workspace status…', {
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByText('Workspace ready', {
        exact: true,
      }),
    ).toBeVisible()
  })

  test('shows fresh first-run state when no vault exists', async ({
    page,
  }) => {
    await mockDashboard(page, {
      ...baseSummary,
      vault_exists: false,
      vault_markdown_files: null,
      projection_exists: false,
      model_exists: false,
      stats: null,
      candidates: {
        total: 0,
        staged: 0,
        in_review: 0,
        rejected: 0,
        approved: 0,
      },
    })

    await page.goto('/app/#/')

    await expect(
      page.getByText('Workspace setup required', {
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByRole('button', {
        name: 'Open Vault',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByText(
        /Markdown vault is the authoritative source/,
      ),
    ).toBeVisible()
  })

  test('shows empty-vault state with useful first actions', async ({
    page,
  }) => {
    await mockDashboard(page, {
      ...baseSummary,
      vault_markdown_files: 0,
      projection_exists: false,
      model_exists: false,
      stats: null,
      candidates: {
        total: 0,
        staged: 0,
        in_review: 0,
        rejected: 0,
        approved: 0,
      },
    })

    await page.goto('/app/#/')

    await expect(
      page.getByText(
        'Vault ready, no approved knowledge yet',
        { exact: true },
      ),
    ).toBeVisible()

    await expect(
      page.getByRole('button', {
        name: 'New LeLe',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByRole('button', {
        name: 'Collection',
        exact: true,
      }),
    ).toBeVisible()
  })

  test('shows partial state and delegates recovery to System', async ({
    page,
  }) => {
    await mockDashboard(page, {
      ...baseSummary,
      model_exists: false,
    })

    await page.goto('/app/#/')

    await expect(
      page.getByText('Workspace partially ready', {
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByText('missing', { exact: true }),
    ).toHaveCount(1)

    await page
      .getByRole('button', {
        name: 'Open System',
        exact: true,
      })
      .click()

    await expect(page).toHaveURL(/#\/ops$/)
  })

  test('shows ready state with bounded knowledge and candidate summaries', async ({
    page,
  }) => {
    await mockDashboard(page, baseSummary)

    await page.goto('/app/#/')

    await expect(
      page.getByText('Workspace ready', {
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByRole('heading', {
        name: 'Approved knowledge',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByRole('heading', {
        name: 'Collection attention',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByText('4', { exact: true }).first(),
    ).toBeVisible()
  })

  test('shows a recoverable dashboard error', async ({ page }) => {
    await page.route('**/dashboard/summary', (route) =>
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'dashboard fixture failure',
        }),
      }),
    )

    await page.goto('/app/#/')

    await expect(
      page.getByText(
        /Workspace status could not be loaded/,
      ),
    ).toBeVisible()

    await expect(
      page.getByRole('button', {
        name: 'Retry',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByRole('button', {
        name: 'Open System',
        exact: true,
      }),
    ).toBeVisible()
  })

  test('keeps the dashboard usable on mobile width', async ({
    page,
  }) => {
    await mockDashboard(page, baseSummary)
    await page.setViewportSize({
      width: 390,
      height: 844,
    })

    await page.goto('/app/#/')

    await expect(
      page.getByRole('heading', {
        name: 'Dashboard',
        exact: true,
      }),
    ).toBeVisible()

    const summary = page.getByRole('region', {
      name: 'Workspace summary',
    })

    await expect(summary).toBeVisible()

    const geometry = await summary.evaluate((element) => {
      const box = element.getBoundingClientRect()
      return {
        left: box.left,
        right: box.right,
        viewport: window.innerWidth,
      }
    })

    expect(geometry.left).toBeGreaterThanOrEqual(0)
    expect(geometry.right).toBeLessThanOrEqual(
      geometry.viewport + 0.5,
    )

    await expect(
      page.getByRole('navigation', {
        name: 'Primary',
      }).getByRole('link', {
        name: 'Dashboard',
        exact: true,
      }),
    ).toBeVisible()
  })

  test('localizes dashboard state without changing the root route', async ({
    page,
  }) => {
    await page.goto('/app/#/')

    await page
      .getByLabel('Language')
      .selectOption('it')

    await expect(
      page.getByRole('heading', {
        name: 'Dashboard',
        exact: true,
      }),
    ).toBeVisible()

    await expect(
      page.getByRole('region', {
        name: 'Disponibilità dello spazio di lavoro',
      }),
    ).toBeVisible()

    await expect(page).toHaveURL(/#\/$/)
  })
})
