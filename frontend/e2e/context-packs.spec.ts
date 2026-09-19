import { expect, test, type Page } from '@playwright/test'

type Pack = {
  id: string
  name: string
  vault_id: string
  lesson_ids: string[]
  created_at: string
  updated_at: string
}

const alpha = {
  id: 'ctx/alpha',
  text: 'Alpha body',
  title: 'Alpha',
  lifecycle: 'active',
}

const beta = {
  id: 'ctx/beta',
  text: 'Beta body',
  title: 'Beta',
  lifecycle: 'deprecated',
}

async function mockContextPacks(page: Page) {
  let pack: Pack | null = {
    id: 'pack-1',
    name: 'Release pack',
    vault_id: 'vault-1',
    lesson_ids: [
      'ctx/alpha',
      'ctx/missing',
    ],
    created_at: '2026-09-19T10:00:00+00:00',
    updated_at: '2026-09-19T10:00:00+00:00',
  }

  const calls = {
    rename: [] as unknown[],
    add: [] as unknown[],
    remove: [] as unknown[],
    deleted: 0,
    exports: 0,
  }

  await page.route('**/lessons/search', route =>
    route.fulfill({
      json: [alpha, beta],
    }),
  )

  await page.route('**/context-packs', async route => {
    if (route.request().method() === 'GET') {
      return route.fulfill({
        json: pack ? [pack] : [],
      })
    }

    return route.fallback()
  })

  await page.route('**/context-packs/pack-1/export?*', async route => {
    calls.exports += 1
    return route.fulfill({
      status: 200,
      contentType: 'text/markdown; charset=utf-8',
      body: '# LeLe export\n\nALPHA CONTEXT PACK BODY\n',
    })
  })

  await page.route('**/context-packs/pack-1/members', async route => {
    if (!pack) {
      return route.fulfill({ status: 404 })
    }

    const body = route.request().postDataJSON() as {
      lesson_ids: string[]
    }

    if (route.request().method() === 'POST') {
      calls.add.push(body)

      for (const id of body.lesson_ids) {
        if (!pack.lesson_ids.includes(id)) {
          pack.lesson_ids.push(id)
        }
      }

      return route.fulfill({ json: pack })
    }

    if (route.request().method() === 'DELETE') {
      calls.remove.push(body)
      pack.lesson_ids = pack.lesson_ids.filter(
        id => !body.lesson_ids.includes(id),
      )
      return route.fulfill({ json: pack })
    }

    return route.fallback()
  })

  await page.route('**/context-packs/pack-1', async route => {
    if (!pack) {
      return route.fulfill({ status: 404 })
    }

    if (route.request().method() === 'GET') {
      return route.fulfill({
        json: {
          ...pack,
          members: pack.lesson_ids.map((lessonId, position) => {
            if (lessonId === 'ctx/missing') {
              return {
                lesson_id: lessonId,
                position,
                resolved: false,
                lesson: null,
              }
            }

            const lesson =
              lessonId === 'ctx/beta'
                ? beta
                : alpha

            return {
              lesson_id: lessonId,
              position,
              resolved: true,
              lesson,
            }
          }),
        },
      })
    }

    if (route.request().method() === 'PATCH') {
      const body = route.request().postDataJSON() as {
        name: string
      }
      calls.rename.push(body)
      pack.name = body.name
      return route.fulfill({ json: pack })
    }

    if (route.request().method() === 'DELETE') {
      calls.deleted += 1
      pack = null
      return route.fulfill({
        status: 204,
        body: '',
      })
    }

    return route.fallback()
  })

  return calls
}

test('Context Packs support inspect, current lifecycle, broken refs, membership, rename, copy/export and delete', async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: async (text: string) =>
          localStorage.setItem('context-pack-clipboard', text),
      },
    })
  })

  page.on('dialog', dialog => dialog.accept())

  const calls = await mockContextPacks(page)

  await page.goto('/app/#/browse')

  const manager = page.getByTestId('context-packs-manager')
  await expect(manager).toContainText('Release pack')

  await manager
    .getByRole('button', { name: /Release pack/ })
    .click()

  await expect(
    page.getByTestId('context-pack-member-ctx/alpha'),
  ).toContainText('Active')

  await expect(
    page.getByTestId('context-pack-member-ctx/missing'),
  ).toContainText('Missing canonical reference')

  await manager
    .getByLabel('Context Pack name')
    .fill('Release final')

  await manager
    .getByRole('button', { name: 'Rename', exact: true })
    .click()

  await expect(manager).toContainText('Release final')
  expect(calls.rename).toEqual([
    { name: 'Release final' },
  ])

  await page
    .getByLabel(/Select LeLe Beta/)
    .check()

  await manager
    .getByRole('button', { name: 'Add selected' })
    .click()

  await expect(
    page.getByTestId('context-pack-member-ctx/beta'),
  ).toContainText('Deprecated')

  expect(calls.add).toEqual([
    { lesson_ids: ['ctx/beta'] },
  ])

  await page
    .getByTestId('context-pack-member-ctx/missing')
    .getByRole('button', { name: 'Remove' })
    .click()

  await expect(
    page.getByTestId('context-pack-member-ctx/missing'),
  ).toHaveCount(0)

  expect(calls.remove).toEqual([
    { lesson_ids: ['ctx/missing'] },
  ])

  await manager
    .getByRole('button', { name: 'Copy', exact: true })
    .click()

  await expect.poll(
    () => page.evaluate(
      () => localStorage.getItem('context-pack-clipboard'),
    ),
  ).toContain('ALPHA CONTEXT PACK BODY')

  const downloadPromise = page.waitForEvent('download')
  await manager
    .getByRole('button', { name: 'Export .md', exact: true })
    .click()
  const download = await downloadPromise

  expect(download.suggestedFilename()).toBe(
    'context-pack-pack-1.md',
  )
  expect(calls.exports).toBe(2)

  await manager
    .getByRole('button', { name: 'Delete pack' })
    .click()

  await expect(manager).toContainText(
    'No Context Packs yet.',
  )
  expect(calls.deleted).toBe(1)
})

test('Context Pack management is localized in Italian', async ({
  page,
}) => {
  await page.addInitScript(() => {
    localStorage.setItem('lele-manager.locale', 'it')
  })

  await mockContextPacks(page)
  await page.goto('/app/#/browse')

  const manager = page.getByTestId('context-packs-manager')

  await expect(manager).toContainText(
    'Insiemi di lavoro riutilizzabili',
  )

  await manager
    .getByRole('button', { name: /Release pack/ })
    .click()

  await expect(
    page.getByTestId('context-pack-member-ctx/missing'),
  ).toContainText('Riferimento canonico mancante')

  await expect(
    manager.getByRole('button', {
      name: 'Aggiungi selezionate',
    }),
  ).toBeVisible()

  await expect(
    manager.getByRole('button', {
      name: 'Elimina pack',
    }),
  ).toBeVisible()
})
