import { expect, test, type Page } from '@playwright/test'

type RelationshipType =
  | 'derives-from'
  | 'corrects'
  | 'extends'
  | 'contradicts'
  | 'see-also'

type Relationships = Partial<Record<RelationshipType, string[]>>

type Lesson = {
  id: string
  title: string
  text: string
  topic: string
  source: string
  importance: number
  tags: string[]
  date: string
  lifecycle?: 'active' | 'review-needed' | 'deprecated' | 'archived'
  superseded_by?: string | null
  supersedes?: string[]
  relationships?: Relationships
  incoming_relationships?: Relationships
  canonical_revision?: string | null
}

const first: Lesson = {
  id: 'distributed-systems/2026-08-10.retry-a',
  title: 'Retry semantics A',
  text: 'The first lesson remains visible after another exact lesson is deleted.',
  topic: 'distributed-systems', source: 'note', importance: 3, tags: ['retry'], date: '2026-08-10',
  lifecycle: 'deprecated',
  superseded_by: 'distributed-systems/2026-08-10.retry-b',
  supersedes: [],
  relationships: {
    extends: ['distributed-systems/2026-08-10.retry-b'],
  },
  incoming_relationships: {
    'see-also': ['distributed-systems/2026-08-10.retry-b'],
  },
}
const second: Lesson = {
  id: 'distributed-systems/2026-08-10.retry-b',
  title: 'Retry semantics B',
  text: 'The second lesson is the exact target for every action.',
  topic: 'distributed-systems', source: 'note', importance: 4, tags: ['retry'], date: '2026-08-10',
  lifecycle: 'active',
  superseded_by: null,
  supersedes: ['distributed-systems/2026-08-10.retry-a'],
  relationships: {
    'see-also': ['distributed-systems/2026-08-10.retry-a'],
  },
  incoming_relationships: {
    extends: ['distributed-systems/2026-08-10.retry-a'],
  },
}

type DeleteMode = 'success' | 'partial-refresh' | 'canonical-failure'

async function mockLessons(page: Page, mode: DeleteMode = 'success') {
  let lessons = [first, second]
  const deletes: string[] = []
  const similar: string[] = []

  await page.route('**/editor/metadata-options', route => route.fulfill({ json: { topics: [], tags: [], sources: [] } }))
  await page.route('**/lessons/search', route => route.fulfill({ json: lessons }))
  await page.route('**/lessons?*', route => route.fulfill({ json: lessons }))
  await page.route('**/lessons/**', async route => {
    const request = route.request()
    const pathname = new URL(request.url()).pathname
    if (pathname === '/lessons/search') {
      return route.fulfill({ json: lessons })
    }
    const encodedId = pathname.replace(/^\/lessons\//, '').replace(/\/similar$/, '')
    const id = decodeURIComponent(encodedId)
    if (pathname.endsWith('/similar')) {
      similar.push(id)
      return route.fulfill({ json: { query: 'query', results: [], meta: { top_k: 8, min_score: 0.05 } } })
    }
    if (request.method() === 'DELETE') {
      deletes.push(id)
      if (mode === 'canonical-failure') {
        return route.fulfill({
          status: 503,
          json: {
            detail: {
              code: 'lesson_delete_storage_failed',
              message: 'The canonical lesson could not be deleted.',
            },
          },
        })
      }
      lessons = lessons.filter((lesson) => lesson.id !== id)
      if (mode === 'partial-refresh') {
        return route.fulfill({
          status: 503,
          json: { detail: { code: 'lesson_deleted_refresh_failed', message: 'refresh failed', recovery: { canonical_deleted: true, lesson_id: id, relative_vault_path: 'archive/retry-b.md' } } },
        })
      }
      return route.fulfill({ json: { lesson_id: id, relative_vault_path: 'archive/retry-b.md', canonical_deleted: true, refresh_outcome: { refreshed: true } } })
    }
    const lesson = lessons.find((item) => item.id === id) ?? second
    return route.fulfill({ json: lesson })
  })
  return { deletes, similar, lessons: () => lessons }
}

test('Browse actions target the exact card and confirm before deleting', async ({ page }) => {
  const calls = await mockLessons(page)
  await page.goto('/app/#/browse')
  const target = page.getByTestId(`lesson-result-${second.id}`)

  await expect(target.getByRole('button', { name: 'Modify' })).toBeVisible()
  await expect(target.getByRole('button', { name: 'Inspect' })).toBeVisible()
  await expect(target.getByRole('button', { name: 'Delete' })).toBeVisible()

  await target.getByRole('button', { name: 'Modify' }).click()
  await expect(page).toHaveURL(new RegExp(encodeURIComponent(second.id)))
  await expect(
    page.getByRole('textbox', { name: 'ID', exact: true }),
  ).toHaveValue(second.id)

  await page.goto('/app/#/browse')
  await target.getByRole('button', { name: 'Inspect' }).click()
  await expect(page).toHaveURL(new RegExp(`#\/lesson\/${encodeURIComponent(second.id)}`))
  await expect.poll(() => calls.similar).toContain(second.id)

  await page.goto('/app/#/browse')
  await target.getByRole('button', { name: 'Delete' }).click()
  const dialog = page.getByRole('dialog', { name: 'Delete LeLe?' })
  await expect(dialog).toContainText(second.title)
  await expect(dialog).toContainText(second.id)
  await dialog.getByRole('button', { name: 'Cancel' }).click()
  expect(calls.deletes).toEqual([])

  await target.getByRole('button', { name: 'Delete' }).click()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  expect(calls.deletes).toEqual([])

  await target.getByRole('button', { name: 'Delete' }).click()
  await dialog.getByRole('button', { name: 'Delete' }).click()
  await expect.poll(() => calls.deletes).toEqual([second.id])
  await expect(page.getByTestId(`lesson-result-${first.id}`)).toBeVisible()
  await expect(page.getByTestId(`lesson-result-${second.id}`)).toHaveCount(0)
  await expect(page.getByText('LeLe deleted.')).toBeVisible()
})

test('Detail exposes actions, focuses its existing inspection surface, and returns to Browse after delete', async ({ page }) => {
  const calls = await mockLessons(page)
  await page.goto(`/app/#/lesson/${encodeURIComponent(second.id)}`)
  await expect(page.getByRole('button', { name: 'Modify' })).toBeVisible()
  await page.getByRole('button', { name: 'Inspect' }).click()
  await expect(page.locator('#lesson-similarity')).toBeFocused()
  await expect.poll(() => calls.similar).toContain(second.id)
  await page.getByRole('button', { name: 'Delete' }).click()
  await page.getByRole('dialog', { name: 'Delete LeLe?' }).getByRole('button', { name: 'Delete' }).click()
  await expect(page).toHaveURL(/#\/browse$/)
  await expect(page.getByText('LeLe deleted.')).toBeVisible()
})

test('Detail navigates supersession in both directions and marks non-active knowledge', async ({ page }) => {
  await mockLessons(page)

  await page.goto(`/app/#/lesson/${encodeURIComponent(second.id)}`)
  await expect(
    page.getByRole('button', {
      name: `Supersedes: ${first.id}`,
      exact: true,
    }),
  ).toBeVisible()

  await page.getByRole('button', {
    name: `Supersedes: ${first.id}`,
    exact: true,
  }).click()

  await expect(page).toHaveURL(
    new RegExp(`#\\/lesson\\/${encodeURIComponent(first.id)}$`),
  )
  await expect(page.getByTestId('detail-lifecycle')).toContainText('Deprecated')
  await expect(
    page.getByRole('button', {
      name: `Superseded by: ${second.id}`,
      exact: true,
    }),
  ).toBeVisible()

  await page.getByRole('button', {
    name: `Superseded by: ${second.id}`,
    exact: true,
  }).click()

  await expect(page).toHaveURL(
    new RegExp(`#\\/lesson\\/${encodeURIComponent(second.id)}$`),
  )
})


test('Detail keeps outgoing and incoming typed relationships distinct and navigable', async ({ page }) => {
  await mockLessons(page)

  await page.goto(`/app/#/lesson/${encodeURIComponent(second.id)}`)

  const relationships = page.getByTestId('detail-relationships')
  await expect(relationships).toBeVisible()
  await expect(relationships).toContainText('Outgoing')
  await expect(relationships).toContainText('Incoming')

  await expect(
    relationships.getByRole('button', {
      name: `See also: ${first.id}`,
      exact: true,
    }),
  ).toBeVisible()
  await expect(
    relationships.getByRole('button', {
      name: `Extends ← ${first.id}`,
      exact: true,
    }),
  ).toBeVisible()

  // Supersession remains a separate semantic surface.
  await expect(
    page.getByRole('button', {
      name: `Supersedes: ${first.id}`,
      exact: true,
    }),
  ).toBeVisible()

  await relationships.getByRole('button', {
    name: `See also: ${first.id}`,
    exact: true,
  }).click()

  await expect(page).toHaveURL(
    new RegExp(`#\/lesson\/${encodeURIComponent(first.id)}$`),
  )

  const reverseRelationships = page.getByTestId('detail-relationships')
  await expect(
    reverseRelationships.getByRole('button', {
      name: `See also ← ${second.id}`,
      exact: true,
    }),
  ).toBeVisible()

  await reverseRelationships.getByRole('button', {
    name: `See also ← ${second.id}`,
    exact: true,
  }).click()

  await expect(page).toHaveURL(
    new RegExp(`#\/lesson\/${encodeURIComponent(second.id)}$`),
  )
})


test('Detail remains usable when canonical deletion fails', async ({ page }) => {
  const calls = await mockLessons(page, 'canonical-failure')
  const detailUrl = new RegExp(`#\\/lesson\\/${encodeURIComponent(second.id)}$`)
  await page.goto(`/app/#/lesson/${encodeURIComponent(second.id)}`)

  const detailPanel = page.getByRole('region', {
    name: second.id,
    exact: true,
  })
  await expect(detailPanel).toBeVisible()
  await expect(detailPanel.getByRole('heading', { name: second.title })).toBeVisible()

  await detailPanel.getByRole('button', { name: 'Delete' }).click()
  const dialog = page.getByRole('dialog', { name: 'Delete LeLe?' })
  await expect(dialog).toContainText(second.title)
  await expect(dialog).toContainText(second.id)
  await dialog.getByRole('button', { name: 'Delete' }).click()

  await expect.poll(() => calls.deletes).toEqual([second.id])
  await expect(page).toHaveURL(detailUrl)
  await expect(detailPanel).toBeVisible()
  await expect(detailPanel.getByRole('button', { name: 'Modify' })).toBeVisible()
  await expect(page.getByText('LeLe could not be deleted.')).toBeVisible()
  await expect(page.getByText('LeLe deleted.')).toHaveCount(0)
  await expect(page.getByText(/canonical LeLe was deleted/i)).toHaveCount(0)
  expect(calls.lessons()).toContainEqual(second)
})

test('Editor shows Delete only for an existing lesson and partial refresh is not presented as a failed delete', async ({ page }) => {
  const calls = await mockLessons(page, 'partial-refresh')
  await page.goto('/app/#/editor')
  await expect(page.getByRole('button', { name: 'Delete' })).toHaveCount(0)

  await page.goto(`/app/#/editor/${encodeURIComponent(second.id)}`)
  await expect(page.getByRole('button', { name: 'Delete' })).toBeVisible()
  await page.getByRole('button', { name: 'Delete' }).click()
  await page.getByRole('dialog', { name: 'Delete LeLe?' }).getByRole('button', { name: 'Delete' }).click()
  await expect.poll(() => calls.deletes).toEqual([second.id])
  await expect(page).toHaveURL(/#\/browse$/)
  await expect(page.getByText(/canonical LeLe was deleted/i)).toBeVisible()
  await expect(page.getByText('LeLe could not be deleted.')).toHaveCount(0)
})

test('Italian confirmation and partial-success notice preserve the canonical outcome', async ({ page }) => {
  await mockLessons(page, 'partial-refresh')
  await page.goto('/app/#/browse')
  await page.getByLabel('Language').selectOption('it')
  const target = page.getByTestId(`lesson-result-${second.id}`)
  await target.getByRole('button', { name: 'Elimina' }).click()
  const dialog = page.getByRole('dialog', { name: 'Eliminare la LeLe?' })
  await expect(dialog).toContainText('Questa operazione elimina la LeLe Markdown canonica.')
  await dialog.getByRole('button', { name: 'Elimina' }).click()
  await expect(page.getByText(/LeLe canonica è stata eliminata/i)).toBeVisible()
  await expect(page.getByText(/temporaneamente obsoleti/i)).toBeVisible()
})
