import { expect, test, type Page, type Route } from '@playwright/test'

const fp0 = `sha256:${'0'.repeat(64)}`
const fp1 = `sha256:${'1'.repeat(64)}`
const fp2 = `sha256:${'2'.repeat(64)}`

function lesson(
  id: string,
  text: string,
  canonicalRevision: string,
) {
  return {
    id,
    text,
    topic: 'revision',
    source: 'note',
    importance: 3,
    tags: ['history'],
    date: '2026-08-15',
    title: 'Revision history test',
    lifecycle: 'active',
    superseded_by: null,
    supersedes: [],
    canonical_revision: canonicalRevision,
  }
}

function revision(
  number: number,
  fingerprint: string,
  action: 'baseline' | 'edit' | 'rollback',
  extras: Record<string, unknown> = {},
) {
  return {
    revision: number,
    canonical_fingerprint: fingerprint,
    occurred_at: `2026-08-15T1${number}:00:00+00:00`,
    action,
    relative_path: 'revision/test.md',
    reason: null,
    rollback_from_revision: null,
    ...extras,
  }
}

async function mockCommon(page: Page) {
  await page.route(
    '**/editor/metadata-options',
    route => route.fulfill({
      json: { topics: [], tags: [], sources: [] },
    }),
  )
}

async function fulfillEmptySimilarity(route: Route) {
  await route.fulfill({
    json: {
      query: 'query',
      results: [],
      meta: { top_k: 8, min_score: 0.05 },
    },
  })
}

test('Editor sends the canonical revision token with an explicit update', async ({ page }) => {
  await mockCommon(page)

  const id = 'revision/editor-token'
  const encoded = encodeURIComponent(id)
  const writes: Record<string, unknown>[] = []

  await page.route(`**/lessons/${encoded}`, async route => {
    if (route.request().method() === 'GET') {
      return route.fulfill({ json: lesson(id, 'Original body', fp1) })
    }

    if (route.request().method() === 'PUT') {
      const payload = route.request().postDataJSON() as Record<string, unknown>
      writes.push(payload)
      return route.fulfill({
        json: {
          ...lesson(id, String(payload.text), fp2),
          ...payload,
        },
      })
    }

    return route.fallback()
  })

  await page.route(
    `**/lessons/${encoded}/similar*`,
    fulfillEmptySimilarity,
  )

  await page.route('**/lesson-history*', route =>
    route.fulfill({
      json: {
        lesson_id: id,
        current_canonical_revision: fp2,
        revisions: [],
      },
    }),
  )

  await page.goto(`/app/#/editor/${encoded}`)
  await expect(page.getByRole('heading', { name: 'Edit LeLe' })).toBeVisible()

  await page.getByPlaceholder('Write the lesson learned…').fill('Updated body')
  await page.getByRole('button', { name: 'Save to vault' }).click()

  await expect.poll(() => writes.length).toBe(1)
  expect(writes[0]).toMatchObject({
    text: 'Updated body',
    expected_revision: fp1,
  })
})



test('Editor adopts the new canonical token after a saved update whose refresh fails', async ({ page }) => {
  await mockCommon(page)

  const id = 'revision/editor-partial'
  const encoded = encodeURIComponent(id)
  const writes: Record<string, unknown>[] = []

  await page.route(`**/lessons/${encoded}`, async route => {
    if (route.request().method() === 'GET') {
      return route.fulfill({ json: lesson(id, 'Original body', fp1) })
    }

    if (route.request().method() === 'PUT') {
      const payload = route.request().postDataJSON() as Record<string, unknown>
      writes.push(payload)

      if (writes.length === 1) {
        return route.fulfill({
          status: 503,
          json: {
            detail: {
              code: 'lesson_update_refresh_failed',
              message: 'refresh failed',
              recovery: {
                canonical_saved: true,
                canonical_revision: fp2,
                revision: 1,
                refresh_outcome: {
                  attempted: true,
                  refreshed: false,
                },
              },
            },
          },
        })
      }

      return route.fulfill({
        json: {
          ...lesson(id, String(payload.text), fp0),
          ...payload,
        },
      })
    }

    return route.fallback()
  })

  await page.goto(`/app/#/editor/${encoded}`)

  const body = page.getByPlaceholder('Write the lesson learned…')
  await body.fill('First saved body')
  await page.getByRole('button', { name: 'Save to vault' }).click()

  await expect(
    page.getByText(
      'The canonical LeLe was saved with revision history, but derived data could not be refreshed. Search and similarity results may be stale.',
    ),
  ).toBeVisible()

  await expect.poll(() => writes.length).toBe(1)
  expect(writes[0]).toMatchObject({
    expected_revision: fp1,
  })

  // A second explicit save must use the recovered canonical token, not the
  // stale token that was loaded before the successful canonical write.
  await body.fill('Second saved body')
  await page.getByRole('button', { name: 'Save to vault' }).click()

  await expect.poll(() => writes.length).toBe(2)
  expect(writes[1]).toMatchObject({
    expected_revision: fp2,
    text: 'Second saved body',
  })
})


test('Editor reports a stale write without retrying or discarding the draft', async ({ page }) => {
  await mockCommon(page)

  const id = 'revision/editor-stale'
  const encoded = encodeURIComponent(id)
  let writes = 0

  await page.route(`**/lessons/${encoded}`, async route => {
    if (route.request().method() === 'GET') {
      return route.fulfill({ json: lesson(id, 'Original body', fp1) })
    }

    if (route.request().method() === 'PUT') {
      writes += 1
      return route.fulfill({
        status: 409,
        json: {
          detail: {
            code: 'lesson_revision_stale',
            message: 'stale',
          },
        },
      })
    }

    return route.fallback()
  })

  await page.goto(`/app/#/editor/${encoded}`)

  const body = page.getByPlaceholder('Write the lesson learned…')
  await body.fill('Unsaved human draft')
  await page.getByRole('button', { name: 'Save to vault' }).click()

  await expect(
    page.getByText(
      'This LeLe changed after you opened it. Reload it before saving; your current draft was not written.',
    ),
  ).toBeVisible()

  await expect(body).toHaveValue('Unsaved human draft')
  expect(writes).toBe(1)
})


test('Detail exposes timeline, readable diff, confirmed append-only rollback and localization', async ({ page }) => {
  const id = 'revision/detail'
  const encoded = encodeURIComponent(id)

  let currentLesson = lesson(id, 'After body', fp1)
  let revisions = [
    revision(0, fp0, 'baseline'),
    revision(1, fp1, 'edit', { reason: 'Editorial update' }),
  ]
  const rollbackRequests: Record<string, unknown>[] = []

  await page.route(`**/lessons/${encoded}`, route =>
    route.fulfill({ json: currentLesson }),
  )

  await page.route(
    `**/lessons/${encoded}/similar*`,
    fulfillEmptySimilarity,
  )

  await page.route(/\/lesson-history(?:\/[^?]+)?(?:\?.*)?$/, async route => {
    const url = new URL(route.request().url())

    if (url.pathname === '/lesson-history/diff') {
      return route.fulfill({
        json: {
          lesson_id: id,
          from_revision: 0,
          to_revision: 1,
          unified_diff:
            '--- revision-0.md\n+++ revision-1.md\n@@ -1 +1 @@\n-Before body\n+After body\n',
        },
      })
    }

    if (url.pathname === '/lesson-history/rollback') {
      const payload = route.request().postDataJSON() as Record<string, unknown>
      rollbackRequests.push(payload)

      currentLesson = lesson(id, 'Before body', fp0)
      revisions = [
        ...revisions,
        revision(2, fp0, 'rollback', {
          reason: 'Restore baseline',
          rollback_from_revision: 0,
        }),
      ]

      return route.fulfill({
        json: {
          lesson_id: id,
          revision: 2,
          canonical_revision: fp0,
          canonical_changed: true,
          refresh_outcome: { refreshed: true },
        },
      })
    }

    if (url.pathname === '/lesson-history') {
      return route.fulfill({
        json: {
          lesson_id: id,
          current_canonical_revision: currentLesson.canonical_revision,
          revisions,
        },
      })
    }

    return route.fallback()
  })

  await page.goto(`/app/#/lesson/${encoded}`)

  const historyPanel = page.getByRole('region', {
    name: 'Revision history',
    exact: true,
  })
  await expect(historyPanel).toBeVisible()
  await expect(historyPanel).toContainText('#0')
  await expect(historyPanel).toContainText('#1')
  await expect(historyPanel).toContainText('Editorial update')

  await historyPanel.getByRole('button', { name: 'Compare' }).click()
  await expect(historyPanel.locator('pre.revision-diff')).toContainText('-Before body')
  await expect(historyPanel.locator('pre.revision-diff')).toContainText('+After body')

  await historyPanel
    .getByRole('button', { name: 'Restore this revision' })
    .first()
    .click()

  const dialog = page.getByRole('dialog', {
    name: 'Restore historical revision?',
  })
  await expect(dialog).toContainText('#0')
  await expect(dialog).toContainText(
    'The existing history will be preserved and a new rollback revision will be created.',
  )

  await dialog
    .getByPlaceholder('Why are you restoring this revision?')
    .fill('Restore baseline')
  await dialog.getByRole('button', { name: 'Restore revision' }).click()

  await expect.poll(() => rollbackRequests.length).toBe(1)
  expect(rollbackRequests[0]).toMatchObject({
    lesson_id: id,
    target_revision: 0,
    expected_revision: fp1,
    reason: 'Restore baseline',
  })

  await expect(historyPanel).toContainText('#2')
  await expect(historyPanel).toContainText('Restored from revision #0')
  await expect(page.locator('.markdown-body')).toContainText('Before body')

  // Revision #2 is current, but it intentionally has the same exact content
  // fingerprint as historical revision #0. Currentness is revision identity,
  // not content equality: both #0 and #1 remain valid rollback targets.
  await expect(
    historyPanel.getByRole('button', { name: 'Restore this revision' }),
  ).toHaveCount(2)

  await page.getByLabel('Language').selectOption('it')
  await expect(
    page.getByRole('region', {
      name: 'Cronologia revisioni',
      exact: true,
    }),
  ).toBeVisible()
})


test('rollback stale conflict remains explicit and does not retry', async ({ page }) => {
  const id = 'revision/rollback-stale'
  const encoded = encodeURIComponent(id)
  let rollbackCalls = 0

  await page.route(`**/lessons/${encoded}`, route =>
    route.fulfill({ json: lesson(id, 'After body', fp1) }),
  )
  await page.route(
    `**/lessons/${encoded}/similar*`,
    fulfillEmptySimilarity,
  )

  await page.route(/\/lesson-history(?:\/[^?]+)?(?:\?.*)?$/, async route => {
    const url = new URL(route.request().url())

    if (url.pathname === '/lesson-history/rollback') {
      rollbackCalls += 1
      return route.fulfill({
        status: 409,
        json: {
          detail: {
            code: 'lesson_revision_stale',
            message: 'stale',
          },
        },
      })
    }

    return route.fulfill({
      json: {
        lesson_id: id,
        current_canonical_revision: fp1,
        revisions: [
          revision(0, fp0, 'baseline'),
          revision(1, fp1, 'edit'),
        ],
      },
    })
  })

  await page.goto(`/app/#/lesson/${encoded}`)

  const historyPanel = page.getByRole('region', {
    name: 'Revision history',
    exact: true,
  })

  await historyPanel
    .getByRole('button', { name: 'Restore this revision' })
    .click()

  await page
    .getByRole('dialog', { name: 'Restore historical revision?' })
    .getByRole('button', { name: 'Restore revision' })
    .click()

  await expect(
    historyPanel.getByText(
      'The canonical LeLe changed. Reload before restoring a revision.',
    ),
  ).toBeVisible()

  expect(rollbackCalls).toBe(1)
})


test('rollback partial refresh tells the truth and reloads canonical history', async ({ page }) => {
  const id = 'revision/rollback-partial'
  const encoded = encodeURIComponent(id)

  let currentLesson = lesson(id, 'After body', fp1)
  let revisions = [
    revision(0, fp0, 'baseline'),
    revision(1, fp1, 'edit'),
  ]

  await page.route(`**/lessons/${encoded}`, route =>
    route.fulfill({ json: currentLesson }),
  )
  await page.route(
    `**/lessons/${encoded}/similar*`,
    fulfillEmptySimilarity,
  )

  await page.route(/\/lesson-history(?:\/[^?]+)?(?:\?.*)?$/, async route => {
    const url = new URL(route.request().url())

    if (url.pathname === '/lesson-history/rollback') {
      currentLesson = lesson(id, 'Before body', fp0)
      revisions = [
        ...revisions,
        revision(2, fp0, 'rollback', {
          rollback_from_revision: 0,
        }),
      ]

      return route.fulfill({
        status: 503,
        json: {
          detail: {
            code: 'lesson_rollback_refresh_failed',
            message: 'refresh failed',
            recovery: {
              canonical_saved: true,
              canonical_revision: fp0,
              revision: 2,
              refresh_outcome: {
                attempted: true,
                refreshed: false,
              },
            },
          },
        },
      })
    }

    return route.fulfill({
      json: {
        lesson_id: id,
        current_canonical_revision: currentLesson.canonical_revision,
        revisions,
      },
    })
  })

  await page.goto(`/app/#/lesson/${encoded}`)

  const historyPanel = page.getByRole('region', {
    name: 'Revision history',
    exact: true,
  })

  await historyPanel
    .getByRole('button', { name: 'Restore this revision' })
    .first()
    .click()

  await page
    .getByRole('dialog', { name: 'Restore historical revision?' })
    .getByRole('button', { name: 'Restore revision' })
    .click()

  await expect(
    historyPanel.getByText(
      'The canonical rollback succeeded, but derived data could not be refreshed. Search and similarity results may be stale.',
    ),
  ).toBeVisible()

  await expect(historyPanel).toContainText('#2')
  await expect(page.locator('.markdown-body')).toContainText('Before body')
})
