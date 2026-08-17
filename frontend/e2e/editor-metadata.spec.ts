import { expect, test, type Page } from '@playwright/test'

const options = {
  topics: [{ value: 'Python', count: 4 }, { value: 'linux', count: 2 }],
  tags: [{ value: 'pytest', count: 4 }, { value: 'Python', count: 2 }],
  sources: [{ value: 'note', count: 4 }, { value: 'Book', count: 1 }],
}

async function mockOptions(page: Page) {
  await page.route('**/editor/metadata-options', route => route.fulfill({ json: options }))
}

function watchWrites(page: Page) {
  const payloads: unknown[] = []
  page.on('request', request => {
    const path = new URL(request.url()).pathname
    if ((request.method() === 'POST' && path === '/vault/lessons') || (request.method() === 'PUT' && path.startsWith('/lessons/'))) {
      payloads.push(request.postDataJSON())
    }
  })
  return payloads
}

async function fillRequiredBody(page: Page) {
  await page.locator('textarea').fill('A sufficiently complete body for explicit authoring.')
}

test('catalogues are discoverable, advisory, and only explicit Save creates a lesson', async ({ page }) => {
  await mockOptions(page)
  const writes = watchWrites(page)
  await page.route('**/vault/lessons', async route => {
    await route.fulfill({ status: 201, json: { id: 'python/test', ...(route.request().postDataJSON() as object) } })
  })
  await page.goto('/app/#/editor')

  await expect(page.getByLabel('Topic')).toHaveValue('')
  expect(await page.locator('#known-topics option').evaluateAll(items => items.map(item => item.getAttribute('value')))).toEqual(['Python', 'linux'])
  expect(await page.locator('#known-sources option').evaluateAll(items => items.map(item => item.getAttribute('value')))).toEqual(['note', 'Book'])
  expect(await page.locator('#known-tags option').evaluateAll(items => items.map(item => item.getAttribute('value')))).toEqual(['pytest', 'Python'])
  expect(writes).toHaveLength(0)

  await page.getByLabel('Topic').fill('Python')
  await page.getByLabel('Source').fill('Book')
  await page.getByPlaceholder('Add a tag').fill('pytest')
  await page.getByRole('button', { name: 'Add tag' }).click()
  await page.getByPlaceholder('Add a tag').fill('PyTest')
  await page.keyboard.press('Enter')
  await page.getByPlaceholder('Add a tag').fill('new-tag')
  await page.keyboard.press('Enter')
  await page.getByPlaceholder('Add a tag').fill('remove-me')
  await page.keyboard.press('Enter')
  await expect(page.getByRole('button', { name: 'Remove tag: pytest' })).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Remove tag: new-tag' })).toBeVisible()
  await page.getByRole('button', { name: 'Remove tag: remove-me' }).click()
  await expect(page.getByRole('button', { name: 'Remove tag: remove-me' })).toHaveCount(0)
  expect(await page.locator('#known-tags option').evaluateAll(items => items.map(item => item.getAttribute('value')))).toEqual(['pytest'])
  expect(writes).toHaveLength(0)

  await fillRequiredBody(page)
  await page.getByRole('button', { name: 'Save to vault' }).click()
  await expect.poll(() => writes.length).toBe(1)
  expect(writes[0]).toMatchObject({ topic: 'Python', source: 'Book', importance: 3, tags: ['pytest', 'new-tag'] })
})

test('new lessons author active lifecycle explicitly and no supersession', async ({ page }) => {
  await mockOptions(page)
  const writes = watchWrites(page)
  await page.route('**/vault/lessons', async route => {
    await route.fulfill({
      status: 201,
      json: {
        id: 'lifecycle/new',
        ...(route.request().postDataJSON() as object),
      },
    })
  })

  await page.goto('/app/#/editor')

  await expect(page.getByLabel('Lifecycle')).toHaveValue('active')
  await expect(page.getByLabel('Superseded by')).toHaveValue('')

  await page.getByLabel('Topic').fill('lifecycle')
  await fillRequiredBody(page)
  await page.getByRole('button', { name: 'Save to vault' }).click()

  await expect.poll(() => writes.length).toBe(1)
  expect(writes[0]).toMatchObject({
    lifecycle: 'active',
    superseded_by: null,
  })
})

test('new Topic and Source values are deliberately preserved', async ({ page }) => {
  await mockOptions(page)
  const writes = watchWrites(page)
  await page.route('**/vault/lessons', async route => route.fulfill({ status: 201, json: { id: 'manual/test', ...(route.request().postDataJSON() as object) } }))
  await page.goto('/app/#/editor')

  await page.getByLabel('Topic').fill('Uncatalogued Topic')
  await expect(page.getByText('Use new topic: Uncatalogued Topic')).toBeVisible()
  await page.getByLabel('Source').fill('manual-source')
  await fillRequiredBody(page)
  await page.getByRole('button', { name: 'Save to vault' }).click()
  await expect.poll(() => writes.length).toBe(1)
  expect(writes[0]).toMatchObject({ topic: 'Uncatalogued Topic', source: 'manual-source' })
})

test('an empty Source deliberately uses the canonical note default', async ({ page }) => {
  await mockOptions(page)
  const writes = watchWrites(page)
  await page.route('**/vault/lessons', async route => route.fulfill({ status: 201, json: { id: 'source/test', ...(route.request().postDataJSON() as object) } }))
  // The writer's documented default is intentional even when the visible field is cleared.
  await page.goto('/app/#/editor')
  await page.getByLabel('Topic').fill('Uncatalogued Topic')
  await page.getByLabel('Source').fill('')
  await fillRequiredBody(page)
  await page.getByRole('button', { name: 'Save to vault' }).click()
  await expect.poll(() => writes.length).toBe(1)
  expect(writes[0]).toMatchObject({ source: 'note' })
})

test('similarity topic advice is strict-majority, advisory, and applied only on request', async ({ page }) => {
  await mockOptions(page)
  const writes = watchWrites(page)
  let suggestions = 0
  await page.route('**/editor/suggest?*', async route => {
    suggestions += 1
    await route.fulfill({ json: { query: 'query', results: [
      { id: '1', score: 0.9, text_preview: 'one', topic: 'linux' },
      { id: '2', score: 0.8, text_preview: 'two', topic: 'linux' },
      { id: '3', score: 0.7, text_preview: 'three', topic: 'python' },
    ] } })
  })
  await page.goto('/app/#/editor')
  await page.getByLabel('Topic').fill('user-controlled')
  await fillRequiredBody(page)
  await expect(page.getByRole('button', { name: 'Check similarity' })).toBeEnabled()
  expect(suggestions).toBe(0)
  await page.getByRole('button', { name: 'Check similarity' }).click()
  await expect.poll(() => suggestions).toBe(1)
  await expect(page.getByText('Suggested topic:')).toContainText('linux')
  await expect(page.getByLabel('Topic')).toHaveValue('user-controlled')
  expect(writes).toHaveLength(0)
  await page.getByRole('button', { name: 'Apply' }).click()
  await expect(page.getByLabel('Topic')).toHaveValue('linux')
  expect(writes).toHaveLength(0)
})

test('weak or too-small similarity topic sets never present authoritative advice', async ({ page }) => {
  await mockOptions(page)
  let response = [{ id: '1', score: 0.9, text_preview: 'one', topic: 'linux' }, { id: '2', score: 0.8, text_preview: 'two', topic: 'python' }]
  await page.route('**/editor/suggest?*', route => route.fulfill({ json: { query: 'query', results: response } }))
  await page.goto('/app/#/editor')
  await page.getByLabel('Topic').fill('user-controlled')
  await fillRequiredBody(page)
  await page.getByRole('button', { name: 'Check similarity' }).click()
  await expect(page.locator('.similar-panel')).toBeVisible()
  await expect(page.getByText('Suggested topic:')).toHaveCount(0)

  response = [{ id: '1', score: 0.9, text_preview: 'one', topic: 'linux' }]
  await page.getByPlaceholder('Write the lesson learned…').fill('A changed sufficiently complete body for another explicit check.')
  await page.getByRole('button', { name: 'Check similarity' }).click()
  await expect(page.locator('.similar-panel')).toBeVisible()
  await expect(page.getByText('Suggested topic:')).toHaveCount(0)
})

test('Importance exposes exactly 1..5 and serializes the low endpoint', async ({ page }) => {
  await mockOptions(page)
  const writes = watchWrites(page)
  await page.route('**/vault/lessons', async route => route.fulfill({ status: 201, json: { id: 'importance/test', ...(route.request().postDataJSON() as object) } }))
  await page.goto('/app/#/editor')
  const importance = page.getByLabel('Importance')
  await expect(importance).toHaveValue('3')
  expect(await importance.locator('option').evaluateAll(items => items.map(item => item.getAttribute('value')))).toEqual(['1', '2', '3', '4', '5'])
  await importance.selectOption('1')
  await page.getByLabel('Topic').fill('topic-one')
  await fillRequiredBody(page)
  await page.getByRole('button', { name: 'Save to vault' }).click()
  await expect.poll(() => writes.length).toBe(1)
  expect(writes[0]).toMatchObject({ importance: 1 })
})

test('Importance serializes the high endpoint', async ({ page }) => {
  await mockOptions(page)
  const writes = watchWrites(page)
  await page.route('**/vault/lessons', async route => route.fulfill({ status: 201, json: { id: 'importance/high', ...(route.request().postDataJSON() as object) } }))
  await page.goto('/app/#/editor')
  await page.getByLabel('Importance').selectOption('5')
  await page.getByLabel('Topic').fill('topic-five')
  await fillRequiredBody(page)
  await page.getByRole('button', { name: 'Save to vault' }).click()
  await expect.poll(() => writes.length).toBe(1)
  expect(writes[0]).toMatchObject({ importance: 5 })
})

test('tampered Importance values are rejected before writing', async ({ page }) => {
  await mockOptions(page)
  const writes = watchWrites(page)
  await page.route('**/vault/lessons', route => route.fulfill({ status: 500, body: 'unexpected write' }))
  await page.goto('/app/#/editor')
  const importance = page.getByLabel('Importance')
  await page.getByLabel('Topic').fill('invalid-topic')
  await fillRequiredBody(page)
  for (const invalid of ['0', '6']) {
    await importance.evaluate((select, value) => {
      const option = new Option(value, value, true, true)
      select.add(option)
      select.dispatchEvent(new Event('change', { bubbles: true }))
    }, invalid)
    await page.getByRole('button', { name: 'Save to vault' }).click()
    await expect(page.getByText('Importance must be a whole number from 1 to 5.')).toBeVisible()
    expect(writes).toHaveLength(0)
  }
})

test('metadata-options failure still permits a manual save', async ({ page }) => {
  const writes = watchWrites(page)
  await page.route('**/editor/metadata-options', route => route.fulfill({ status: 500, body: 'offline' }))
  await page.route('**/vault/lessons', async route => route.fulfill({ status: 201, json: { id: 'manual/test', ...(route.request().postDataJSON() as object) } }))
  await page.goto('/app/#/editor')
  await expect(page.getByText('Metadata suggestions are unavailable. You can still enter values manually.')).toBeVisible()
  await page.getByLabel('Topic').fill('handwritten')
  await page.getByLabel('Source').fill('manual-source')
  await page.getByPlaceholder('Add a tag').fill('manual-tag')
  await page.keyboard.press('Enter')
  await fillRequiredBody(page)
  await page.getByRole('button', { name: 'Save to vault' }).click()
  await expect.poll(() => writes.length).toBe(1)
  expect(writes[0]).toMatchObject({ topic: 'handwritten', source: 'manual-source', tags: ['manual-tag'] })
})

test('edit mode preserves uncatalogued metadata until an explicit update', async ({ page }) => {
  await mockOptions(page)
  const writes = watchWrites(page)
  const legacy = { id: 'legacy-special', text: '---\ntopic: legacy-special\n---\nLegacy body.', topic: 'legacy-special', source: 'old-import', importance: 4, tags: ['RareTag', 'AnotherTag'], date: '2026-01-02', canonical_revision: `sha256:${'a'.repeat(64)}`, supersedes: [] }
  await page.route('**/lessons/legacy-special', async route => {
    if (route.request().method() === 'GET') await route.fulfill({ json: legacy })
    else await route.fulfill({ json: { ...legacy, ...(route.request().postDataJSON() as object) } })
  })
  await page.goto('/app/#/editor/legacy-special')
  await expect(page.getByLabel('Topic')).toHaveValue('legacy-special')
  await expect(page.getByLabel('Source')).toHaveValue('old-import')
  await expect(page.getByLabel('Importance')).toHaveValue('4')
  await expect(page.getByRole('button', { name: 'Remove tag: RareTag' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Remove tag: AnotherTag' })).toBeVisible()
  expect(writes).toHaveLength(0)
  await page.getByRole('button', { name: 'Save to vault' }).click()
  await expect.poll(() => writes.length).toBe(1)
  expect(writes[0]).toMatchObject({ topic: 'legacy-special', source: 'old-import', importance: 4, tags: ['RareTag', 'AnotherTag'] })
})

test('edit mode hydrates lifecycle and can explicitly clear lifecycle metadata', async ({ page }) => {
  await mockOptions(page)
  const writes = watchWrites(page)

  let current = {
    id: 'legacy/deprecated',
    text: 'Deprecated body.',
    topic: 'legacy',
    source: 'note',
    importance: 3,
    tags: [],
    date: '2026-01-02',
    lifecycle: 'deprecated',
    superseded_by: 'legacy/replacement',
    canonical_revision: `sha256:${'b'.repeat(64)}`,
    supersedes: [],
  }

  await page.route('**/lessons/legacy%2Fdeprecated', async route => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: current })
      return
    }

    const update = route.request().postDataJSON() as typeof current
    current = { ...current, ...update }
    await route.fulfill({ json: current })
  })

  await page.goto('/app/#/editor/legacy%2Fdeprecated')

  await expect(page.getByLabel('Lifecycle')).toHaveValue('deprecated')
  await expect(page.getByLabel('Superseded by')).toHaveValue('legacy/replacement')
  expect(writes).toHaveLength(0)

  await page.getByRole('button', { name: 'Save to vault' }).click()
  await expect.poll(() => writes.length).toBe(1)
  expect(writes[0]).toMatchObject({
    lifecycle: 'deprecated',
    superseded_by: 'legacy/replacement',
  })

  await expect(
    page.getByRole('region', {
      name: 'legacy/deprecated',
      exact: true,
    }),
  ).toBeVisible()

  await page.getByRole('button', { name: 'Modify' }).click()

  await expect(page).toHaveURL(
    /#\/editor\/legacy%2Fdeprecated$/,
  )
  await expect(page.getByLabel('Lifecycle')).toHaveValue('deprecated')
  await expect(page.getByLabel('Superseded by')).toHaveValue('legacy/replacement')

  await page.getByLabel('Lifecycle').selectOption('active')
  await page.getByLabel('Superseded by').fill('')
  await page.getByRole('button', { name: 'Save to vault' }).click()

  await expect.poll(() => writes.length).toBe(2)
  expect(writes[1]).toMatchObject({
    lifecycle: 'active',
    superseded_by: null,
  })
})

test('edit mode explicitly adds and removes typed relationships and sends the complete mapping', async ({ page }) => {
  await mockOptions(page)
  const writes = watchWrites(page)

  const id = 'relationships/source'
  const encoded = encodeURIComponent(id)
  let current = {
    id,
    text: 'Relationship body.',
    topic: 'relationships',
    source: 'note',
    importance: 3,
    tags: [],
    date: '2026-08-17',
    lifecycle: 'active' as const,
    superseded_by: null,
    relationships: {
      extends: ['knowledge/base'],
      'see-also': ['knowledge/related'],
    },
    incoming_relationships: {},
    supersedes: [],
    canonical_revision: `sha256:${'c'.repeat(64)}`,
  }

  await page.route(`**/lessons/${encoded}`, async route => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: current })
      return
    }

    const update = route.request().postDataJSON() as Record<string, unknown>
    current = {
      ...current,
      ...update,
      canonical_revision: `sha256:${'d'.repeat(64)}`,
    }
    await route.fulfill({ json: current })
  })

  await page.route(
    `**/lessons/${encoded}/similar*`,
    route => route.fulfill({
      json: {
        query: 'query',
        results: [],
        meta: { top_k: 8, min_score: 0.05 },
      },
    }),
  )

  await page.goto(`/app/#/editor/${encoded}`)

  await expect(
    page.getByRole('button', {
      name: 'Remove relationship: Extends knowledge/base',
    }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', {
      name: 'Remove relationship: See also knowledge/related',
    }),
  ).toBeVisible()
  expect(writes).toHaveLength(0)

  await page.getByRole('button', {
    name: 'Remove relationship: Extends knowledge/base',
  }).click()

  const corrects = page.getByLabel('Corrects — Target stable ID')
  await corrects.fill('knowledge/correction')
  await corrects.press('Enter')

  await expect(
    page.getByRole('button', {
      name: 'Remove relationship: Corrects knowledge/correction',
    }),
  ).toBeVisible()
  await expect(
    page.getByRole('button', {
      name: 'Remove relationship: Extends knowledge/base',
    }),
  ).toHaveCount(0)

  await page.getByRole('button', { name: 'Save to vault' }).click()

  await expect.poll(() => writes.length).toBe(1)
  expect(writes[0]).toMatchObject({
    relationships: {
      corrects: ['knowledge/correction'],
      'see-also': ['knowledge/related'],
    },
  })

  expect(
    (writes[0] as { relationships: Record<string, string[]> })
      .relationships.extends,
  ).toBeUndefined()
})

test('Italian metadata labels localize without changing author-controlled values', async ({ page }) => {
  await mockOptions(page)
  const writes = watchWrites(page)
  await page.route('**/vault/lessons', route => route.fulfill({ status: 500, body: 'unexpected write' }))
  await page.route('**/editor/suggest?*', route => route.fulfill({ json: { query: 'query', results: [
    { id: '1', score: 0.9, text_preview: 'one', topic: 'linux' },
    { id: '2', score: 0.8, text_preview: 'two', topic: 'linux' },
    { id: '3', score: 0.7, text_preview: 'three', topic: 'python' },
  ] } }))
  await page.goto('/app/#/editor')
  await page.getByLabel('Topic').fill('Python')
  await page.getByLabel('Source').fill('Book')
  await page.getByPlaceholder('Add a tag').fill('pytest')
  await page.keyboard.press('Enter')
  await page.getByLabel('Language').selectOption('it')
  await expect(page.getByPlaceholder('Scegli o scrivi un topic')).toBeVisible()
  await expect(page.getByPlaceholder('Aggiungi un tag')).toBeVisible()
  await expect(page.getByLabel('Importanza').locator('option').first()).toHaveText('1 Bassa')
  await expect(page.getByRole('button', { name: 'Rimuovi tag: pytest' })).toBeVisible()
  await expect(page.getByLabel('Topic')).toHaveValue('Python')
  await expect(page.getByLabel('Fonte')).toHaveValue('Book')
  await expect(page.getByText('Usa nuovo topic: Python')).toHaveCount(0)
  await fillRequiredBody(page)
  await page.getByRole('button', { name: 'Verifica similarità' }).click()
  await expect(page.getByText('Topic suggerito:')).toContainText('linux')
  await page.getByRole('button', { name: 'Applica' }).click()
  await expect(page.getByLabel('Topic')).toHaveValue('linux')

  await page.getByLabel('Importanza').evaluate(select => {
    select.add(new Option('0', '0', true, true))
    select.dispatchEvent(new Event('change', { bubbles: true }))
  })
  await page.getByRole('button', { name: 'Salva nel vault' }).click()
  await expect(page.getByText("L'importanza deve essere un intero da 1 a 5.")).toBeVisible()
  expect(writes).toHaveLength(0)
})

test('Italian metadata-options warning keeps manual authoring available', async ({ page }) => {
  await page.route('**/editor/metadata-options', route => route.fulfill({ status: 500, body: 'offline' }))
  await page.goto('/app/#/editor')
  await page.getByLabel('Language').selectOption('it')
  await expect(page.getByText('I suggerimenti dei metadati non sono disponibili. Puoi comunque inserire valori manualmente.')).toBeVisible()
})
