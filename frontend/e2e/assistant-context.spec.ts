import { expect, test } from '@playwright/test'

const alpha = {
  id: 'python/alpha',
  text: 'Alpha body',
  title: 'Alpha',
  lifecycle: 'active',
}

const beta = {
  id: 'python/beta',
  text: 'Beta body',
  title: 'Beta',
  lifecycle: 'review-needed',
}

test('Browse assistant context is explicit, local-only and preserves exact visible/selected scope', async ({
  page,
}) => {
  const requests: unknown[] = []

  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: async (text: string) =>
          localStorage.setItem(
            'assistant-context-clipboard',
            text,
          ),
      },
    })
  })

  await page.route('**/context-packs', route =>
    route.fulfill({ json: [] }),
  )

  await page.route('**/lessons/search', route =>
    route.fulfill({
      json: [alpha, beta],
    }),
  )

  await page.route('**/assistant-context', async route => {
    const body = route.request().postDataJSON()
    requests.push(body)

    const lessonIds = body.lesson_ids as string[]

    await route.fulfill({
      json: {
        markdown:
          '# LeLe Assistant Context\n\n'
          + lessonIds.join('\n'),
        n_lessons: lessonIds.length,
        lesson_ids: lessonIds,
      },
    })
  })

  await page.goto('/app/#/browse')

  expect(requests).toEqual([])

  await page
    .getByRole('button', {
      name: 'Search',
      exact: true,
    })
    .click()

  const results = page.getByTestId(
    'assistant-context-results',
  )

  await expect(results).toContainText(
    'Assistant scope: 2 LeLe',
  )
  await expect(results).toContainText(
    'Nothing is sent to an assistant automatically.',
  )

  expect(requests).toEqual([])

  await results
    .getByRole('button', {
      name: 'Copy for assistant',
    })
    .click()

  expect(requests).toEqual([
    {
      lesson_ids: [
        'python/alpha',
        'python/beta',
      ],
    },
  ])

  await expect.poll(
    () => page.evaluate(
      () => localStorage.getItem(
        'assistant-context-clipboard',
      ),
    ),
  ).toContain('python/alpha')

  await page
    .getByLabel(/Select LeLe Beta/)
    .check()

  const selected = page.getByTestId(
    'assistant-context-selected',
  )

  await expect(selected).toContainText(
    'Assistant scope: 1 LeLe',
  )

  const downloadPromise = page.waitForEvent('download')

  await selected
    .getByRole('button', {
      name: 'Export for assistant',
    })
    .click()

  const download = await downloadPromise

  expect(download.suggestedFilename()).toBe(
    'lele-assistant-selected.md',
  )

  expect(requests).toEqual([
    {
      lesson_ids: [
        'python/alpha',
        'python/beta',
      ],
    },
    {
      lesson_ids: ['python/beta'],
    },
  ])
})

test('Context Pack uses the maintained assistant-context boundary', async ({
  page,
}) => {
  const requests: unknown[] = []

  await page.route('**/context-packs', route =>
    route.fulfill({
      json: [
        {
          id: 'pack-1',
          name: 'Release pack',
          vault_id: 'vault-1',
          lesson_ids: [
            'python/alpha',
            'python/beta',
          ],
          created_at: '2026-09-23T08:00:00+00:00',
          updated_at: '2026-09-23T08:00:00+00:00',
        },
      ],
    }),
  )

  await page.route(
    '**/context-packs/pack-1',
    route =>
      route.fulfill({
        json: {
          id: 'pack-1',
          name: 'Release pack',
          vault_id: 'vault-1',
          lesson_ids: [
            'python/alpha',
            'python/beta',
          ],
          created_at: '2026-09-23T08:00:00+00:00',
          updated_at: '2026-09-23T08:00:00+00:00',
          members: [
            {
              lesson_id: 'python/alpha',
              position: 0,
              resolved: true,
              lesson: alpha,
            },
            {
              lesson_id: 'python/beta',
              position: 1,
              resolved: true,
              lesson: beta,
            },
          ],
        },
      }),
  )

  await page.route(
    '**/assistant-context',
    async route => {
      const body = route.request().postDataJSON()
      requests.push(body)

      await route.fulfill({
        json: {
          markdown:
            '# LeLe Assistant Context\n\npack',
          n_lessons: 2,
          lesson_ids: [
            'python/alpha',
            'python/beta',
          ],
        },
      })
    },
  )

  await page.goto('/app/#/browse')

  await page
    .getByRole('button', { name: /Release pack/ })
    .click()

  const actions = page.getByTestId(
    'assistant-context-pack',
  )

  await expect(actions).toContainText(
    'Assistant scope: 2 LeLe',
  )

  expect(requests).toEqual([])

  await actions
    .getByRole('button', {
      name: 'Copy for assistant',
    })
    .click()

  expect(requests).toEqual([
    { context_pack_id: 'pack-1' },
  ])
})

test('Assistant context controls localize in Italian without changing machine scope', async ({
  page,
}) => {
  await page.addInitScript(() => {
    localStorage.setItem(
      'lele-manager.locale',
      'it',
    )

    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: async () => undefined,
      },
    })
  })

  await page.route('**/context-packs', route =>
    route.fulfill({ json: [] }),
  )

  await page.route('**/lessons/search', route =>
    route.fulfill({ json: [alpha] }),
  )

  await page.route(
    '**/assistant-context',
    route =>
      route.fulfill({
        json: {
          markdown: '# LeLe Assistant Context',
          n_lessons: 1,
          lesson_ids: ['python/alpha'],
        },
      }),
  )

  await page.goto('/app/#/browse')

  await page
    .getByRole('button', {
      name: 'Cerca',
      exact: true,
    })
    .click()

  const actions = page.getByTestId(
    'assistant-context-results',
  )

  await expect(actions).toContainText(
    'Ambito assistente: 1 LeLe',
  )

  await expect(
    actions.getByRole('button', {
      name: 'Copia per assistente',
    }),
  ).toBeVisible()

  await expect(actions).toContainText(
    'Nulla viene inviato automaticamente',
  )
})
