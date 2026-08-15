import { expect, test, type Page } from '@playwright/test'

interface SearchRequest {
  q: string | null
  topic_in: string[] | null
  source_in: string[] | null
  importance_gte: number | null
  importance_lte: number | null
  limit: number
  include_frontmatter: boolean
}

async function watchSearchRequests(page: Page): Promise<SearchRequest[]> {
  const requests: SearchRequest[] = []

  await page.route('**/lessons/search', async (route) => {
    requests.push(route.request().postDataJSON() as SearchRequest)
    await route.fulfill({
      contentType: 'application/json',
      body: '[]',
    })
  })

  return requests
}

async function openBrowse(page: Page): Promise<SearchRequest[]> {
  const requests = await watchSearchRequests(page)
  await page.goto('/app/#/browse')
  await expect.poll(() => requests.length).toBe(1)
  await expect(
    page.getByRole('button', { name: 'Search', exact: true }),
  ).toBeEnabled()
  return requests
}

async function expectOneSearchAfterEnter(
  page: Page,
  requests: SearchRequest[],
  label: string,
  value: string,
  expected: Partial<SearchRequest>,
): Promise<void> {
  const requestCount = requests.length
  await page.getByLabel(label).fill(value)
  await page.getByLabel(label).press('Enter')

  await expect.poll(() => requests.length).toBe(requestCount + 1)
  expect(requests[requestCount]).toMatchObject(expected)
  expect(requests).toHaveLength(requestCount + 1)
}

test.describe('Browse filter form', () => {
  test('submits Search once with Enter and with the Search button', async ({
    page,
  }) => {
    const requests = await openBrowse(page)

    await expectOneSearchAfterEnter(page, requests, 'Query', 'pytest', {
      q: 'pytest',
    })

    await page.getByLabel('Query').fill('pandas')
    await page.getByRole('button', { name: 'Search', exact: true }).click()

    await expect.poll(() => requests.length).toBe(3)
    expect(requests[2]).toMatchObject({ q: 'pandas' })
  })

  test('submits Topic and Source with Enter', async ({ page }) => {
    const requests = await openBrowse(page)

    await expectOneSearchAfterEnter(page, requests, 'Topic', 'python', {
      topic_in: ['python'],
    })

    await expectOneSearchAfterEnter(page, requests, 'Source', 'note', {
      source_in: ['note'],
    })
  })

  test('submits numeric filters with Enter', async ({ page }) => {
    const requests = await openBrowse(page)

    await expectOneSearchAfterEnter(page, requests, 'Importance ≥', '3', {
      importance_gte: 3,
    })
    await expectOneSearchAfterEnter(page, requests, 'Importance ≤', '4', {
      importance_lte: 4,
    })
    await expectOneSearchAfterEnter(page, requests, 'Limit', '10', {
      limit: 10,
    })
  })

  test('defaults to active lifecycle and submits explicit lifecycle scope', async ({
    page,
  }) => {
    const requests = await openBrowse(page)

    expect(requests[0].lifecycle_in).toEqual(['active'])
    await expect(page.getByLabel('Lifecycle')).toHaveValue('active')

    await page.getByLabel('Lifecycle').selectOption('deprecated')
    await page.getByRole('button', { name: 'Search', exact: true }).click()

    await expect.poll(() => requests.length).toBe(2)
    expect(requests[1].lifecycle_in).toEqual(['deprecated'])

    await page.getByLabel('Lifecycle').selectOption('all')
    await page.getByRole('button', { name: 'Search', exact: true }).click()

    await expect.poll(() => requests.length).toBe(3)
    expect(requests[2].lifecycle_in).toEqual([
      'active',
      'review-needed',
      'deprecated',
      'archived',
    ])
  })


  test('keeps secondary Browse actions out of form submission', async ({
    page,
  }) => {
    const requests = await openBrowse(page)
    const form = page.locator('.filters form')

    await expect(form).toHaveCount(1)
    await expect(
      page.getByRole('button', { name: 'Search', exact: true }),
    ).toHaveAttribute('type', 'submit')

    for (const name of ['List all', 'Export .md', 'Reset']) {
      await expect(
        page.getByRole('button', { name, exact: true }),
      ).toHaveAttribute('type', 'button')
    }

    await page.getByLabel('Query').fill('to reset')
    await page.getByRole('button', { name: 'Reset', exact: true }).click()

    expect(requests).toHaveLength(1)
    await expect(page.getByLabel('Query')).toHaveValue('')

    const listRequest = page.waitForRequest((request) =>
      request.method() === 'GET' &&
      new URL(request.url()).pathname === '/lessons',
    )
    await page.getByRole('button', { name: 'List all', exact: true }).click()
    await listRequest
    expect(requests).toHaveLength(1)
  })
})
